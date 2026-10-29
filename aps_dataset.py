"""
Benchmark CTG-CPM's data-driven anomaly and game-theory components on UCI's
measured APS Failure at Scania Trucks dataset.

The APS data are real operational records, not 5G optical telemetry. This
module deliberately does not fabricate counterfactual repair outcomes.
"""

import argparse
import csv
import math
import random
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from game_engine import (
    ShapleyAttributor,
    VCGAuctionAllocator,
)


DATASET_URL = (
    "https://archive.ics.uci.edu/static/public/421/"
    "aps+failure+at+scania+trucks.zip"
)
DATASET_NAME = "APS Failure at Scania Trucks"
DATASET_DOI = "10.24432/C51S51"
MISSING_TOKEN = "na"
CLASS_COLUMN = "class"


def _read_aps_csv(path: Path) -> Tuple[List[str], np.ndarray, np.ndarray]:
    """Read UCI's CSV, skipping the 20-line licence/description preamble."""
    header = None
    records = []
    labels = []

    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        for row in reader:
            if row and row[0].strip().lower() == CLASS_COLUMN:
                header = [item.strip() for item in row]
                break

        if header is None:
            raise ValueError(f"No '{CLASS_COLUMN}' header found in {path}")

        if len(header) < 2:
            raise ValueError(f"No feature columns found in {path}")

        for line_number, row in enumerate(reader, start=1):
            if not row:
                continue
            if len(row) != len(header):
                raise ValueError(
                    f"Malformed row {line_number} in {path}: "
                    f"expected {len(header)} columns, got {len(row)}"
                )
            label = row[0].strip().lower()
            if label not in ("neg", "pos"):
                raise ValueError(f"Unknown APS class label {row[0]!r} in {path}")

            try:
                values = [
                    np.nan if value.strip().lower() == MISSING_TOKEN
                    else float(value)
                    for value in row[1:]
                ]
            except ValueError as exc:
                raise ValueError(
                    f"Non-numeric feature in {path}, data row {line_number}"
                ) from exc

            records.append(values)
            labels.append(label == "pos")

    if not records:
        raise ValueError(f"No data rows found in {path}")

    return header[1:], np.asarray(records, dtype=np.float32), np.asarray(labels, dtype=bool)


def ensure_dataset(data_dir: Path) -> Tuple[Path, Path]:
    """Download and extract the original UCI archive when either CSV is missing."""
    data_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir = data_dir / "raw"
    training_file = extracted_dir / "aps_failure_training_set.csv"
    test_file = extracted_dir / "aps_failure_test_set.csv"

    if training_file.is_file() and test_file.is_file():
        return training_file, test_file

    archive_path = data_dir / "aps_failure_at_scania_trucks.zip"
    if not archive_path.is_file():
        print(f"Downloading {DATASET_NAME} from the UCI Machine Learning Repository...")
        request = urllib.request.Request(
            DATASET_URL,
            headers={"User-Agent": "CTG-CPM educational benchmark"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                with archive_path.open("wb") as target:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        target.write(chunk)
        except Exception:
            archive_path.unlink(missing_ok=True)
            raise

    extracted_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
            expected = {
                "aps_failure_training_set.csv",
                "aps_failure_test_set.csv",
            }
            missing = expected.difference(names)
            if missing:
                raise ValueError(
                    "UCI archive is missing expected files: "
                    + ", ".join(sorted(missing))
                )
            for name in sorted(expected):
                with archive.open(name) as source, (extracted_dir / name).open("wb") as target:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        target.write(chunk)
    except Exception:
        raise

    return training_file, test_file


def _stratified_split(labels: np.ndarray, validation_fraction: float, seed: int):
    rng = random.Random(seed)
    train_indices = []
    validation_indices = []
    for label in (False, True):
        indices = np.flatnonzero(labels == label).tolist()
        rng.shuffle(indices)
        validation_count = max(1, int(round(len(indices) * validation_fraction)))
        validation_indices.extend(indices[:validation_count])
        train_indices.extend(indices[validation_count:])
    rng.shuffle(train_indices)
    rng.shuffle(validation_indices)
    return np.asarray(train_indices), np.asarray(validation_indices)


def _fit_normal_profile(
    features: np.ndarray,
    labels: np.ndarray,
    max_missing_fraction: float,
) -> Dict[str, np.ndarray]:
    """Fit robust medians and IQR scales using only labelled non-failure rows."""
    normal_rows = features[~labels]
    if normal_rows.size == 0:
        raise ValueError("Training split has no negative-class records")

    missing_fraction = np.mean(~np.isfinite(normal_rows), axis=0)
    usable = missing_fraction <= max_missing_fraction
    if not np.any(usable):
        raise ValueError(
            "No features satisfy the missing-value limit; increase "
            "--max-missing-fraction or inspect the input dataset."
        )

    usable_indices = np.flatnonzero(usable)
    filtered = normal_rows[:, usable_indices]
    with np.errstate(all="ignore"):
        medians = np.nanmedian(filtered, axis=0)
        lower = np.nanpercentile(filtered, 25, axis=0)
        upper = np.nanpercentile(filtered, 75, axis=0)

    scale = upper - lower
    finite_profile = np.isfinite(medians) & np.isfinite(scale) & (scale > 0)
    usable_indices = usable_indices[finite_profile]
    medians = medians[finite_profile]
    scale = scale[finite_profile] / 1.349
    if not len(usable_indices):
        raise ValueError("No varying, non-missing features remain for the model.")

    return {
        "feature_indices": usable_indices,
        "median": medians.astype(np.float32),
        "scale": scale.astype(np.float32),
        "missing_fraction": missing_fraction[usable_indices].astype(np.float32),
    }


def _score_rows(
    features: np.ndarray,
    profile: Dict[str, np.ndarray],
    top_feature_count: int,
) -> np.ndarray:
    selected = features[:, profile["feature_indices"]]
    deviations = np.abs(selected - profile["median"]) / profile["scale"]
    deviations[~np.isfinite(deviations)] = 0.0
    count = min(max(1, top_feature_count), deviations.shape[1])
    top = np.partition(deviations, deviations.shape[1] - count, axis=1)
    return np.mean(top[:, -count:], axis=1)


def _best_cost_threshold(scores: np.ndarray, labels: np.ndarray) -> Tuple[float, int]:
    """Choose a validation threshold minimizing UCI's 10:500 FP:FN challenge cost."""
    order = np.argsort(scores)[::-1]
    sorted_scores = scores[order]
    sorted_labels = labels[order]
    positives = 0
    negatives = 0
    total_positives = int(np.sum(labels))
    best_threshold = float(np.nextafter(sorted_scores[0], np.inf))
    best_cost = 500 * total_positives
    start = 0

    while start < len(sorted_scores):
        end = start + 1
        while end < len(sorted_scores) and sorted_scores[end] == sorted_scores[start]:
            end += 1
        group = sorted_labels[start:end]
        positives += int(np.sum(group))
        negatives += len(group) - int(np.sum(group))
        false_negatives = total_positives - positives
        cost = 10 * negatives + 500 * false_negatives
        threshold = float(sorted_scores[start])
        if (cost, -threshold) < (best_cost, -best_threshold):
            best_cost = cost
            best_threshold = threshold
        start = end

    return best_threshold, best_cost


def _metrics(labels: np.ndarray, predictions: np.ndarray) -> Dict[str, float]:
    tp = int(np.sum(labels & predictions))
    fp = int(np.sum(~labels & predictions))
    fn = int(np.sum(labels & ~predictions))
    tn = int(np.sum(~labels & ~predictions))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall else 0.0
    )
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
        "challenge_cost": 10 * fp + 500 * fn,
    }


def run_benchmark(
    data_dir: Path,
    max_missing_fraction: float = 0.5,
    validation_fraction: float = 0.2,
    seed: int = 42,
) -> Dict[str, object]:
    training_path, test_path = ensure_dataset(data_dir)
    feature_names, training_features, training_labels = _read_aps_csv(training_path)
    test_names, test_features, test_labels = _read_aps_csv(test_path)
    if feature_names != test_names:
        raise ValueError("Training and test CSV feature columns do not match")
    if not 0 < validation_fraction < 1:
        raise ValueError("validation_fraction must be between zero and one")
    if not 0 <= max_missing_fraction < 1:
        raise ValueError("max_missing_fraction must be in [0, 1)")

    fit_indices, validation_indices = _stratified_split(
        training_labels, validation_fraction, seed
    )
    profile = _fit_normal_profile(
        training_features[fit_indices],
        training_labels[fit_indices],
        max_missing_fraction,
    )
    top_feature_count = max(1, round(math.sqrt(len(profile["feature_indices"]))))
    validation_scores = _score_rows(
        training_features[validation_indices], profile, top_feature_count
    )
    threshold, validation_cost = _best_cost_threshold(
        validation_scores, training_labels[validation_indices]
    )
    test_scores = _score_rows(test_features, profile, top_feature_count)
    test_predictions = test_scores >= threshold
    results = _metrics(test_labels, test_predictions)
    all_negative_cost = 500 * int(np.sum(test_labels))
    results["all_negative_baseline_cost"] = all_negative_cost
    results["challenge_cost_reduction_percent"] = (
        100.0 * (all_negative_cost - results["challenge_cost"]) / all_negative_cost
        if all_negative_cost else 0.0
    )

    most_anomalous_index = int(np.argmax(test_scores))
    row = test_features[most_anomalous_index]
    deviations = np.abs(row[profile["feature_indices"]] - profile["median"]) / profile["scale"]
    deviations[~np.isfinite(deviations)] = 0.0
    top_indices = np.argsort(deviations)[-min(4, len(deviations)):][::-1]
    attribution_features = [
        profile["feature_indices"][index] for index in top_indices
    ]
    attribution_names = [feature_names[index] for index in attribution_features]
    telemetry = {
        feature_names[index]: float(row[index])
        for index in attribution_features
        if np.isfinite(row[index])
    }
    baseline_means = {
        feature_names[profile["feature_indices"][index]]:
        float(profile["median"][index])
        for index in top_indices
    }
    baseline_stds = {
        feature_names[profile["feature_indices"][index]]:
        float(profile["scale"][index])
        for index in top_indices
    }
    shapley = ShapleyAttributor.calculate_shapley_values(
        attribution_names,
        ShapleyAttributor.build_dynamic_characteristic_fn(
            telemetry,
            baseline_means=baseline_means,
            baseline_stds=baseline_stds,
            directions={feature: "absolute" for feature in attribution_names},
        ),
    )
    validation_midpoint = float(np.percentile(validation_scores, 50))
    validation_upper = float(np.percentile(validation_scores, 99))
    stress_span = max(validation_upper - validation_midpoint, np.finfo(float).eps)
    telemetry["anomaly_stress"] = float(np.clip(
        (test_scores[most_anomalous_index] - validation_midpoint) / stress_span,
        0.0,
        1.0,
    ))

    agents = [
        "Agent1_Diagnostician",
        "Agent2_Bargainer",
        "Agent3_Executor",
    ]
    tasks = [
        "RootCauseAttribution",
        "GameTheoreticNegotiation",
        "CounterfactualProjection",
    ]
    bids = VCGAuctionAllocator.compute_dynamic_bids(agents, tasks, telemetry)
    allocation = VCGAuctionAllocator().allocate_tasks(agents, tasks, bids)

    return {
        "dataset": DATASET_NAME,
        "doi": DATASET_DOI,
        "training_rows": len(training_labels),
        "test_rows": len(test_labels),
        "feature_count": len(feature_names),
        "usable_features": len(profile["feature_indices"]),
        "normal_training_rows": int(np.sum(~training_labels[fit_indices])),
        "validation_rows": len(validation_indices),
        "top_feature_count": top_feature_count,
        "threshold": threshold,
        "validation_challenge_cost": validation_cost,
        "metrics": results,
        "representative_record": {
            "test_row_index": most_anomalous_index,
            "true_failure_label": bool(test_labels[most_anomalous_index]),
            "anomaly_score": float(test_scores[most_anomalous_index]),
            "feature_attribution_percent": shapley,
        },
        "vcg_task_assignment": allocation["assignment"],
        "limitations": [
            "This is labelled operational data, but its feature names are anonymized.",
            "The UCI dataset is distributed under GPL-3.0; see the archive's included description.",
            "This dataset describes air-pressure-system failures, not optical 5G links.",
            "The detector is a robust-statistics baseline, not the repository's GNN or diffusion model.",
            "The held-out set is the dataset's labelled test file; the validation threshold is selected from a stratified training split.",
            "No intervention outcome or counterfactual repair label is provided; this benchmark makes no repair-effect claim.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate a data-derived CTG-CPM baseline on UCI Scania APS data."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data") / "aps_failure",
        help="Dataset cache directory (default: data/aps_failure)",
    )
    parser.add_argument(
        "--max-missing-fraction",
        type=float,
        default=0.5,
        help="Drop features with greater missingness among normal training rows.",
    )
    parser.add_argument(
        "--validation-fraction",
        type=float,
        default=0.2,
        help="Stratified training fraction used to select the threshold.",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    result = run_benchmark(
        args.data_dir,
        max_missing_fraction=args.max_missing_fraction,
        validation_fraction=args.validation_fraction,
        seed=args.seed,
    )
    metrics = result["metrics"]
    print(f"\n{result['dataset']} (UCI DOI: {result['doi']})")
    print(
        f"Records: train={result['training_rows']}, "
        f"test={result['test_rows']}; "
        f"features={result['feature_count']}, "
        f"usable after data-derived checks={result['usable_features']}"
    )
    print(
        f"Data-derived threshold={result['threshold']:.6g}; "
        f"top features averaged per row={result['top_feature_count']}"
    )
    print(
        f"Held-out test confusion matrix: "
        f"TP={metrics['tp']} FP={metrics['fp']} "
        f"FN={metrics['fn']} TN={metrics['tn']}"
    )
    print(
        f"Precision={metrics['precision']:.4f} "
        f"Recall={metrics['recall']:.4f} "
        f"Specificity={metrics['specificity']:.4f} "
        f"F1={metrics['f1']:.4f}"
    )
    print(
        f"UCI challenge cost (10*FP + 500*FN)="
        f"{metrics['challenge_cost']} vs "
        f"{metrics['all_negative_baseline_cost']} for always-negative "
        f"({metrics['challenge_cost_reduction_percent']:.1f}% lower); "
        f"validation cost={result['validation_challenge_cost']}"
    )
    representative = result["representative_record"]
    print(
        f"\nHighest-scoring held-out row #{representative['test_row_index']}: "
        f"score={representative['anomaly_score']:.4f}, "
        f"label={'pos' if representative['true_failure_label'] else 'neg'}"
    )
    print("Feature attribution for this record (not causal proof):")
    for feature, percentage in representative["feature_attribution_percent"].items():
        print(f"  {feature}: {percentage:.2f}%")
    print("VCG task allocation from this record's data-derived stress:")
    for task, agent in result["vcg_task_assignment"].items():
        print(f"  {task}: {agent}")
    print("\nLimitations:")
    for limitation in result["limitations"]:
        print(f"  - {limitation}")


if __name__ == "__main__":
    main()
