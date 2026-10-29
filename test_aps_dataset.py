import csv
import tempfile
import unittest
from pathlib import Path

from aps_dataset import run_benchmark
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
