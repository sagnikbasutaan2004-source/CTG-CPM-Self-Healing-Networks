import csv
import tempfile
import unittest
from pathlib import Path

import numpy as np

from agentic_remediator import MultiAgentRemediator
from aps_dataset import (
    _best_f1_threshold,
    load_saved_model,
    predict_aps_record,
    run_benchmark,
    train_and_save_model,
)
from game_engine import ShapleyAttributor


def write_aps_fixture(path: Path, positive_count: int, negative_count: int) -> None:
    headers = ["class", "sensor_a", "sensor_b", "sensor_constant"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        stream.write("Fixture dataset preamble\n\n")
        writer = csv.writer(stream)
        writer.writerow(headers)
        for index in range(negative_count):
            writer.writerow(["neg", index % 4, (index % 7) - 3, 10])
        for index in range(positive_count):
            writer.writerow(["pos", 20 + index, 30 + index, 10])


class TestApsDataset(unittest.TestCase):
    def test_runs_dynamic_benchmark_from_labelled_csv(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary)
            raw_dir = data_dir / "raw"
            raw_dir.mkdir()
            write_aps_fixture(
                raw_dir / "aps_failure_training_set.csv",
                positive_count=20,
                negative_count=100,
            )
            write_aps_fixture(
                raw_dir / "aps_failure_test_set.csv",
                positive_count=10,
                negative_count=40,
            )

            result = run_benchmark(data_dir, seed=7)

        self.assertEqual(result["training_rows"], 120)
        self.assertEqual(result["test_rows"], 50)
        self.assertEqual(result["feature_count"], 3)
        self.assertEqual(result["usable_features"], 2)
        self.assertIn("challenge_cost", result["metrics"])
        self.assertIn("average_precision", result["metrics"])
        self.assertEqual(
            result["selected_model"],
            "CTG-CPM supervised PyTorch APS classifier",
        )
        self.assertGreater(result["selected_model_epochs"], 0)
        self.assertIn("f1", result["validation_metrics"])
        self.assertIn("f1", result["baseline_metrics"])
        self.assertIn("accuracy", result["metrics"])
        self.assertIn("vcg_task_allocation", result["ctg_cpm_decision"])
        self.assertFalse(result["ctg_cpm_decision"]["repair_effect_claim"])
        self.assertEqual(
            result["vcg_task_assignment"]["RootCauseAttribution"],
            "Agent1_Diagnostician",
        )
        self.assertAlmostEqual(
            sum(result["representative_record"]["feature_attribution_percent"].values()),
            100.0,
            places=1,
        )
        self.assertTrue(any(
            "counterfactual repair" in item.lower()
            for item in result["limitations"]
        ))

    def test_f1_threshold_is_selected_from_supplied_validation_labels(self):
        threshold, metrics = _best_f1_threshold(
            np.asarray([0.9, 0.8, 0.2, 0.1]),
            np.asarray([True, False, True, False]),
        )
        self.assertEqual(threshold, 0.2)
        self.assertEqual(metrics["f1"], 0.8)

    def test_trained_checkpoint_loads_and_predicts_without_training(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary) / "data"
            raw_dir = data_dir / "raw"
            raw_dir.mkdir(parents=True)
            write_aps_fixture(
                raw_dir / "aps_failure_training_set.csv",
                positive_count=20,
                negative_count=100,
            )
            write_aps_fixture(
                raw_dir / "aps_failure_test_set.csv",
                positive_count=10,
                negative_count=40,
            )
            model_path = Path(temporary) / "models" / "aps.pt"
            trained = train_and_save_model(
                data_dir, model_path=model_path, seed=7
            )
            loaded = load_saved_model(model_path)
            prediction = predict_aps_record(
                loaded,
                {"sensor_a": 25.0, "sensor_b": 35.0},
            )
            self.assertTrue(model_path.is_file())

        self.assertEqual(trained["feature_count"], 3)
        self.assertEqual(prediction["model"], "CTG-CPM supervised PyTorch APS classifier")
        self.assertGreaterEqual(prediction["failure_probability"], 0.0)
        self.assertLessEqual(prediction["failure_probability"], 1.0)
        self.assertIn("RootCauseAttribution", prediction["vcg_task_allocation"])

    def test_ctg_cpm_aps_path_uses_model_risk_without_repair_claims(self):
        result = MultiAgentRemediator.analyze_aps_failure_risk(
            telemetry={"sensor_a": 14.0, "sensor_b": -2.0},
            failure_probability=0.85,
            baseline_means={"sensor_a": 10.0, "sensor_b": 0.0},
            baseline_stds={"sensor_a": 2.0, "sensor_b": 1.0},
            decision_threshold=0.75,
        )
        self.assertTrue(result["anomaly_detected"])
        self.assertEqual(result["failure_probability"], 0.85)
        self.assertFalse(result["repair_effect_claim"])
        self.assertIn("RootCauseAttribution", result["vcg_task_allocation"]["assignment"])
        below_threshold = MultiAgentRemediator.analyze_aps_failure_risk(
            telemetry={"sensor_a": 14.0},
            failure_probability=0.6,
            baseline_means={"sensor_a": 10.0},
            baseline_stds={"sensor_a": 2.0},
            decision_threshold=0.75,
        )
        self.assertFalse(below_threshold["anomaly_detected"])

        with self.assertRaises(ValueError):
            MultiAgentRemediator.analyze_aps_failure_risk(
                {}, 1.1, {}, {}, 0.5
            )

    def test_shapley_supports_absolute_direction_and_missing_values(self):
        characteristic = ShapleyAttributor.build_dynamic_characteristic_fn(
            {"sensor": 12.0},
            baseline_means={"sensor": 10.0, "missing_sensor": 0.0},
            baseline_stds={"sensor": 2.0, "missing_sensor": 1.0},
            directions={"sensor": "absolute", "missing_sensor": "absolute"},
        )
        values = ShapleyAttributor.calculate_shapley_values(
            ["sensor", "missing_sensor"], characteristic
        )
        self.assertEqual(values["sensor"], 100.0)
        self.assertEqual(values["missing_sensor"], 0.0)


if __name__ == "__main__":
    unittest.main()
