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
import torch
from torch import nn

from agentic_remediator import MultiAgentRemediator


DATASET_URL = (
    "https://archive.ics.uci.edu/static/public/421/"
    "aps+failure+at+scania+trucks.zip"
)
DATASET_NAME = "APS Failure at Scania Trucks"
DATASET_DOI = "10.24432/C51S51"
MISSING_TOKEN = "na"
CLASS_COLUMN = "class"
DEFAULT_MODEL_PATH = Path("models") / "aps_risk_model.pt"


class _ApsRiskClassifier(nn.Module):
    """Small supervised classifier for the labelled APS feature table."""

    def __init__(self, input_features: int):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(input_features, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(32, 1),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.layers(features).squeeze(1)


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


def _prepare_supervised_features(
    features: np.ndarray,
    profile: Dict[str, np.ndarray],
) -> np.ndarray:
    """Impute with training-only normal medians and append missingness indicators."""
    selected = features[:, profile["feature_indices"]]
    missing = ~np.isfinite(selected)
    filled = np.where(missing, profile["median"], selected)
    scaled = (filled - profile["median"]) / profile["scale"]
    scaled = np.clip(scaled, -10.0, 10.0)
    return np.concatenate((scaled, missing.astype(np.float32)), axis=1).astype(
        np.float32
    )


def _train_supervised_classifier(
    training_features: np.ndarray,
    training_labels: np.ndarray,
    validation_features: np.ndarray,
    validation_labels: np.ndarray,
    seed: int,
    max_epochs: int = 40,
    patience: int = 6,
) -> Tuple[_ApsRiskClassifier, np.ndarray, int]:
    """Train a class-imbalance-aware PyTorch detector with validation early stopping."""
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    model = _ApsRiskClassifier(training_features.shape[1])
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)

    positive_count = int(np.sum(training_labels))
    negative_count = len(training_labels) - positive_count
    if positive_count == 0 or negative_count == 0:
        raise ValueError("Supervised training requires both APS classes.")
    positive_weight = float(np.sqrt(negative_count / positive_count))
    loss_fn = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor(positive_weight, dtype=torch.float32)
    )
    train_x = torch.from_numpy(training_features)
    train_y = torch.from_numpy(training_labels.astype(np.float32))
    validation_x = torch.from_numpy(validation_features)
    validation_y = torch.from_numpy(validation_labels.astype(np.float32))

    best_loss = float("inf")
    best_state = None
    best_epoch = 0
    stale_epochs = 0
    batch_size = 2048

    for epoch in range(max_epochs):
        model.train()
        shuffled_indices = rng.permutation(len(train_y))
        for start in range(0, len(shuffled_indices), batch_size):
            batch_indices = shuffled_indices[start:start + batch_size]
            batch_x = train_x[batch_indices]
            batch_y = train_y[batch_indices]
            optimizer.zero_grad(set_to_none=True)
            loss = loss_fn(model(batch_x), batch_y)
            loss.backward()
            optimizer.step()

        model.eval()
        with torch.no_grad():
            validation_loss = float(
                loss_fn(model(validation_x), validation_y).item()
            )
        if validation_loss < best_loss - 1e-5:
            best_loss = validation_loss
            best_state = {
                name: value.detach().clone()
                for name, value in model.state_dict().items()
            }
            best_epoch = epoch + 1
            stale_epochs = 0
        else:
            stale_epochs += 1
            if stale_epochs >= patience:
                break

    if best_state is None:
        raise RuntimeError("APS classifier training did not produce a valid model.")
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        validation_probabilities = torch.sigmoid(model(validation_x)).numpy()
    return model, validation_probabilities, best_epoch


def _best_f1_threshold(
    probabilities: np.ndarray,
    labels: np.ndarray,
) -> Tuple[float, Dict[str, float]]:
    """Choose a validation-only threshold maximizing F1, preferring precision on ties."""
    order = np.argsort(probabilities)[::-1]
    sorted_probabilities = probabilities[order]
    sorted_labels = labels[order]
    total_positives = int(np.sum(labels))
    true_positives = 0
    false_positives = 0
    best_key = (-1.0, -1.0, -1.0)
    best_threshold = float(np.nextafter(sorted_probabilities[0], np.inf))
    best_metrics = _metrics(labels, np.zeros(len(labels), dtype=bool))

    start = 0
    while start < len(sorted_probabilities):
        end = start + 1
        while (
            end < len(sorted_probabilities)
            and sorted_probabilities[end] == sorted_probabilities[start]
        ):
            end += 1
        group = sorted_labels[start:end]
        true_positives += int(np.sum(group))
        false_positives += len(group) - int(np.sum(group))
        predictions = probabilities >= sorted_probabilities[start]
        candidate_metrics = _metrics(labels, predictions)
        key = (
            candidate_metrics["f1"],
            candidate_metrics["precision"],
            candidate_metrics["specificity"],
        )
        if key > best_key:
            best_key = key
            best_threshold = float(sorted_probabilities[start])
            best_metrics = candidate_metrics
        start = end

    return best_threshold, best_metrics


def _predict_probabilities(
    model: _ApsRiskClassifier,
    features: np.ndarray,
) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        return torch.sigmoid(model(torch.from_numpy(features))).numpy()


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
    accuracy = (tp + tn) / len(labels) if len(labels) else 0.0
    balanced_accuracy = (recall + specificity) / 2.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "balanced_accuracy": balanced_accuracy,
        "f1": f1,
        "challenge_cost": 10 * fp + 500 * fn,
    }


def _average_precision(scores: np.ndarray, labels: np.ndarray) -> float:
    if not np.any(labels):
        return 0.0
    order = np.argsort(scores)[::-1]
    sorted_labels = labels[order].astype(np.float64)
    cumulative_true_positives = np.cumsum(sorted_labels)
    ranks = np.arange(1, len(sorted_labels) + 1)
    precision_at_rank = cumulative_true_positives / ranks
    return float(np.sum(precision_at_rank * sorted_labels) / np.sum(sorted_labels))


def train_and_save_model(
    data_dir: Path,
    model_path: Path = DEFAULT_MODEL_PATH,
    validation_fraction: float = 0.2,
    seed: int = 42,
) -> Dict[str, object]:
    """Train once using the official training file and save an inference checkpoint."""
    training_path, _ = ensure_dataset(data_dir)
    feature_names, features, labels = _read_aps_csv(training_path)
    fit_indices, validation_indices = _stratified_split(
        labels, validation_fraction, seed
    )
    profile = _fit_normal_profile(features[fit_indices], labels[fit_indices], 0.5)
    training_x = _prepare_supervised_features(features[fit_indices], profile)
    validation_x = _prepare_supervised_features(features[validation_indices], profile)
    model, validation_probabilities, best_epoch = _train_supervised_classifier(
        training_x,
        labels[fit_indices],
        validation_x,
        labels[validation_indices],
        seed,
    )
    threshold, validation_metrics = _best_f1_threshold(
        validation_probabilities,
        labels[validation_indices],
    )

    checkpoint = {
        "format_version": 1,
        "dataset": DATASET_NAME,
        "doi": DATASET_DOI,
        "feature_names": feature_names,
        "feature_indices": profile["feature_indices"].tolist(),
        "median": profile["median"].tolist(),
        "scale": profile["scale"].tolist(),
        "threshold": threshold,
        "validation_metrics": validation_metrics,
        "training_rows": len(labels),
        "validation_rows": len(validation_indices),
        "best_epoch": best_epoch,
        "model_state_dict": model.state_dict(),
    }
    model_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = model_path.with_suffix(model_path.suffix + ".tmp")
    try:
        torch.save(checkpoint, temporary_path)
        temporary_path.replace(model_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return {
        "model_path": str(model_path),
        "feature_count": len(feature_names),
        "usable_features": len(profile["feature_indices"]),
        "threshold": threshold,
        "validation_metrics": validation_metrics,
        "best_epoch": best_epoch,
    }


def load_saved_model(model_path: Path) -> Dict[str, object]:
    """Load a trusted CTG-CPM APS inference checkpoint."""
    if not model_path.is_file():
        raise FileNotFoundError(
            f"APS model checkpoint not found at {model_path}. "
            "Train it once with `py train_aps_model.py`."
        )
    checkpoint = torch.load(
        model_path, map_location=torch.device("cpu"), weights_only=True
    )
    if checkpoint.get("format_version") != 1:
        raise ValueError(f"Unsupported APS checkpoint format in {model_path}.")
    required = {
        "feature_names",
        "feature_indices",
        "median",
        "scale",
        "threshold",
        "model_state_dict",
    }
    missing = required.difference(checkpoint)
    if missing:
        raise ValueError(
            "APS checkpoint is missing fields: " + ", ".join(sorted(missing))
        )

    feature_indices = np.asarray(checkpoint["feature_indices"], dtype=np.int64)
    medians = np.asarray(checkpoint["median"], dtype=np.float32)
    scales = np.asarray(checkpoint["scale"], dtype=np.float32)
    if (
        len(feature_indices) == 0
        or len(medians) != len(feature_indices)
        or len(scales) != len(feature_indices)
        or np.any(scales <= 0)
    ):
        raise ValueError("APS checkpoint has an invalid preprocessing profile.")

    model = _ApsRiskClassifier(input_features=2 * len(feature_indices))
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    checkpoint["feature_indices"] = feature_indices
    checkpoint["median"] = medians
    checkpoint["scale"] = scales
    checkpoint["model"] = model
    return checkpoint


def predict_aps_record(
    model_bundle: Dict[str, object],
    record: Dict[str, float],
    llm_consent: bool = False,
) -> Dict[str, object]:
    """Predict one user-supplied APS record using a saved model and CTG-CPM agents."""
    feature_names = model_bundle["feature_names"]
    unknown_features = set(record).difference(feature_names)
    if unknown_features:
        raise ValueError(
            "Unknown APS feature names: " + ", ".join(sorted(unknown_features)[:10])
        )

    raw_values = np.asarray(
        [record.get(name, np.nan) for name in feature_names], dtype=np.float32
    )
    feature_indices = model_bundle["feature_indices"]
    medians = model_bundle["median"]
    scales = model_bundle["scale"]
    selected = raw_values[feature_indices]
    missing = ~np.isfinite(selected)
    if np.all(missing):
        raise ValueError("Provide at least one numeric value for a model feature.")
    filled = np.where(missing, medians, selected)
    standardized = np.clip((filled - medians) / scales, -10.0, 10.0)
    model_input = np.concatenate((standardized, missing.astype(np.float32)))
    probability = float(_predict_probabilities(
        model_bundle["model"],
        model_input.reshape(1, -1),
    )[0])
    threshold = float(model_bundle["threshold"])

    deviations = np.abs(selected - medians) / scales
    deviations[~np.isfinite(deviations)] = -np.inf
    top_count = min(8, int(np.sum(np.isfinite(deviations))))
    if top_count:
        top_positions = np.argsort(deviations)[-top_count:][::-1]
    else:
        top_positions = np.asarray([], dtype=np.int64)
    telemetry = {
        feature_names[feature_indices[index]]: float(selected[index])
        for index in top_positions
        if np.isfinite(selected[index])
    }
    baseline_means = {
        feature_names[feature_indices[index]]: float(medians[index])
        for index in top_positions
    }
    baseline_stds = {
        feature_names[feature_indices[index]]: float(scales[index])
        for index in top_positions
    }
    decision = MultiAgentRemediator.analyze_aps_failure_risk(
        telemetry,
        probability,
        baseline_means,
        baseline_stds,
        threshold,
    )
    return {
        "dataset": DATASET_NAME,
        "model": "CTG-CPM supervised PyTorch APS classifier",
        "failure_probability": probability,
        "threshold": threshold,
        "anomaly_detected": decision["anomaly_detected"],
        "severity": (
            "High" if probability >= threshold else "Low"
        ),
        "input_feature_count": int(np.sum(np.isfinite(raw_values))),
        "usable_feature_count": int(np.sum(~missing)),
        "selected_feature_count": len(feature_indices),
        "feature_attribution_percent": decision[
            "shapley_root_cause_attribution"
        ],
        "top_feature_values": telemetry,
        "vcg_task_allocation": decision["vcg_task_allocation"]["assignment"],
        "llm_consent": bool(llm_consent),
        "repair_effect_claim": False,
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
    baseline_test_scores = _score_rows(test_features, profile, top_feature_count)
    baseline_test_predictions = baseline_test_scores >= threshold
    baseline_metrics = _metrics(test_labels, baseline_test_predictions)

    supervised_training_features = _prepare_supervised_features(
        training_features[fit_indices], profile
    )
    supervised_validation_features = _prepare_supervised_features(
        training_features[validation_indices], profile
    )
    supervised_test_features = _prepare_supervised_features(test_features, profile)
    supervised_model, validation_probabilities, best_epoch = (
        _train_supervised_classifier(
            supervised_training_features,
            training_labels[fit_indices],
            supervised_validation_features,
            training_labels[validation_indices],
            seed,
        )
    )
    supervised_threshold, validation_metrics = _best_f1_threshold(
        validation_probabilities,
        training_labels[validation_indices],
    )
    test_probabilities = _predict_probabilities(
        supervised_model, supervised_test_features
    )
    supervised_test_predictions = test_probabilities >= supervised_threshold
    results = _metrics(test_labels, supervised_test_predictions)
    results["average_precision"] = _average_precision(test_probabilities, test_labels)
    all_negative_cost = 500 * int(np.sum(test_labels))
    results["all_negative_baseline_cost"] = all_negative_cost
    results["challenge_cost_reduction_percent"] = (
        100.0 * (all_negative_cost - results["challenge_cost"]) / all_negative_cost
        if all_negative_cost else 0.0
    )
    baseline_metrics["average_precision"] = _average_precision(
        baseline_test_scores, test_labels
    )
    baseline_metrics["all_negative_baseline_cost"] = all_negative_cost
    baseline_metrics["challenge_cost_reduction_percent"] = (
        100.0
        * (all_negative_cost - baseline_metrics["challenge_cost"])
        / all_negative_cost
        if all_negative_cost else 0.0
    )

    most_anomalous_index = int(np.argmax(test_probabilities))
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
    ctg_cpm_decision = MultiAgentRemediator.analyze_aps_failure_risk(
        telemetry,
        float(test_probabilities[most_anomalous_index]),
        baseline_means,
        baseline_stds,
        supervised_threshold,
    )

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
        "selected_model": "CTG-CPM supervised PyTorch APS classifier",
        "selected_threshold": supervised_threshold,
        "selected_threshold_objective": "maximum validation F1; precision and specificity break ties",
        "selected_model_epochs": best_epoch,
        "validation_metrics": validation_metrics,
        "baseline_metrics": baseline_metrics,
        "metrics": results,
        "representative_record": {
            "test_row_index": most_anomalous_index,
            "true_failure_label": bool(test_labels[most_anomalous_index]),
            "failure_probability": float(test_probabilities[most_anomalous_index]),
            "feature_attribution_percent": ctg_cpm_decision[
                "shapley_root_cause_attribution"
            ],
        },
        "vcg_task_assignment": ctg_cpm_decision[
            "vcg_task_allocation"
        ]["assignment"],
        "ctg_cpm_decision": ctg_cpm_decision,
        "limitations": [
            "This is labelled operational data, but its feature names are anonymized.",
            "The UCI dataset is distributed under GPL-3.0; see the archive's included description.",
            "This dataset describes air-pressure-system failures, not optical 5G links.",
            "APS detection is a trained PyTorch tabular classifier; the repository's GNN expects synthetic optical-topology inputs and is not trained or validated on APS.",
            "The robust-statistics detector is retained as a comparison baseline; the supervised threshold is selected on validation data to maximize F1.",
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
        f"Supervised model={result['selected_model']}; "
        f"validation-selected threshold={result['selected_threshold']:.6g}; "
        f"training epochs={result['selected_model_epochs']}"
    )
    print(
        "Validation metrics at selected threshold: "
        f"Precision={result['validation_metrics']['precision']:.4f} "
        f"Recall={result['validation_metrics']['recall']:.4f} "
        f"Specificity={result['validation_metrics']['specificity']:.4f} "
        f"F1={result['validation_metrics']['f1']:.4f}"
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
        f"F1={metrics['f1']:.4f} "
        f"Accuracy={metrics['accuracy']:.4f} "
        f"AveragePrecision={metrics['average_precision']:.4f}"
    )
    baseline = result["baseline_metrics"]
    print(
        "Robust-statistics baseline on the same held-out set: "
        f"Precision={baseline['precision']:.4f} "
        f"Recall={baseline['recall']:.4f} "
        f"Specificity={baseline['specificity']:.4f} "
        f"F1={baseline['f1']:.4f}"
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
        f"\nHighest-probability held-out row #{representative['test_row_index']}: "
        f"failure_probability={representative['failure_probability']:.4f}, "
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
