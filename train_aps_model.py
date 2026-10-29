"""Train and save the APS detector for dashboard inference."""

import argparse
from pathlib import Path

from aps_dataset import DEFAULT_MODEL_PATH, train_and_save_model


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train the APS classifier once for dashboard inference."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data") / "aps_failure",
        help="Dataset cache directory (default: data/aps_failure)",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help="Output checkpoint path (default: models/aps_risk_model.pt)",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    result = train_and_save_model(
        data_dir=args.data_dir,
        model_path=args.model_path,
        seed=args.seed,
    )
    metrics = result["validation_metrics"]
    print(f"Saved APS inference model: {result['model_path']}")
    print(
        f"Validation threshold={result['threshold']:.6f}; "
        f"F1={metrics['f1']:.4f}; "
        f"precision={metrics['precision']:.4f}; "
        f"recall={metrics['recall']:.4f}; "
        f"specificity={metrics['specificity']:.4f}"
    )
    print(
        f"Features={result['usable_features']}/{result['feature_count']}; "
        f"best epoch={result['best_epoch']}"
    )
    print("The official test file was not used for training or threshold selection.")


if __name__ == "__main__":
    main()
