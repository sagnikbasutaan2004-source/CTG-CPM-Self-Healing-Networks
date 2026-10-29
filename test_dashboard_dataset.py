import csv
import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import app
from llm_diagnostician import generate_aps_diagnosis_and_remediation


class TestDashboardDatasetRoute(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.model = {
            "dataset": "APS Failure at Scania Trucks",
            "feature_names": ["sensor_a", "sensor_b"],
            "feature_indices": [0],
            "threshold": 0.75,
        }

    def test_dashboard_exposes_record_inference_not_retraining(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Inspect a truck", response.data)
        self.assertIn(b"Predict Uploaded Record", response.data)
        self.assertIn(b"Enter feature values manually", response.data)
        self.assertNotIn(b"api/datasets/aps/benchmark", response.data)

    @patch("app._get_aps_model_bundle")
    def test_features_endpoint_uses_saved_model_schema(self, get_model):
        get_model.return_value = self.model

        response = self.client.get("/api/datasets/aps/features")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["feature_names"], ["sensor_a", "sensor_b"])

    @patch("app.generate_aps_diagnosis_and_remediation")
    @patch("app.predict_aps_record")
    @patch("app._get_aps_model_bundle")
    def test_manual_record_runs_saved_inference_and_local_remediation(
        self, get_model, predict, diagnosis
    ):
        get_model.return_value = self.model
        predict.return_value = {
            "failure_probability": 0.81,
            "threshold": 0.75,
            "diagnosis": None,
            "top_feature_values": {"sensor_a": 4.0},
            "feature_attribution_percent": {"sensor_a": 100.0},
            "vcg_task_allocation": {"RootCauseAttribution": "Agent1_Diagnostician"},
            "anomaly_detected": True,
            "dataset": "APS Failure at Scania Trucks",
            "model": "saved-test-model",
            "input_feature_count": 1,
            "usable_feature_count": 1,
            "selected_feature_count": 1,
        }
        diagnosis.return_value = {
            "problem_title": "APS risk",
            "problem_description": "Risk exceeded threshold.",
            "root_cause": "Statistical contributor.",
            "risk_if_unresolved": "Review the vehicle.",
            "remediation_steps": [],
            "llm_powered": False,
        }

        response = self.client.post(
            "/api/datasets/aps/predict",
            json={
                "features": {"sensor_a": "4.0", "sensor_b": None},
                "llm_consent": False,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["diagnosis"]["problem_title"], "APS risk")
        predict.assert_called_once_with(
            self.model,
            {"sensor_a": 4.0},
            llm_consent=False,
        )
        self.assertFalse(diagnosis.call_args.kwargs["use_llm"])

    @patch("app.generate_aps_diagnosis_and_remediation")
    @patch("app.predict_aps_record")
    @patch("app._get_aps_model_bundle")
    def test_single_row_csv_ignores_class_column_and_obeys_llm_consent(
        self, get_model, predict, diagnosis
    ):
        get_model.return_value = self.model
        predict.return_value = {
            "failure_probability": 0.8,
            "threshold": 0.75,
            "top_feature_values": {},
            "feature_attribution_percent": {},
            "vcg_task_allocation": {},
            "anomaly_detected": True,
            "dataset": "APS Failure at Scania Trucks",
            "model": "saved-test-model",
            "input_feature_count": 1,
            "usable_feature_count": 1,
            "selected_feature_count": 1,
        }
        diagnosis.return_value = {"llm_powered": True}
        stream = io.StringIO()
        writer = csv.DictWriter(
            stream, fieldnames=["class", "sensor_a", "sensor_b"]
        )
        writer.writeheader()
        writer.writerow({"class": "pos", "sensor_a": "4.0", "sensor_b": "na"})

        response = self.client.post(
            "/api/datasets/aps/predict",
            data={
                "file": (io.BytesIO(stream.getvalue().encode()), "record.csv"),
                "llm_consent": "true",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        predict.assert_called_once_with(
            self.model, {"sensor_a": 4.0}, llm_consent=True
        )
        self.assertTrue(diagnosis.call_args.kwargs["use_llm"])

    @patch("app._get_aps_model_bundle")
    def test_predict_requires_pretrained_model(self, get_model):
        get_model.side_effect = FileNotFoundError("Run py train_aps_model.py")

        response = self.client.post(
            "/api/datasets/aps/predict",
            json={"features": {"sensor_a": 1}},
        )

        self.assertEqual(response.status_code, 503)
        self.assertIn("pre-trained APS model", response.get_json()["error"])

    @patch("app._get_aps_model_bundle")
    def test_predict_rejects_bad_record(self, get_model):
        get_model.return_value = self.model

        response = self.client.post(
            "/api/datasets/aps/predict",
            json={"features": {"not_a_sensor": 1}},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unknown APS feature", response.get_json()["error"])

    @patch("app._get_aps_model_bundle")
    def test_csv_requires_exactly_one_data_row(self, get_model):
        get_model.return_value = self.model
        content = (
            "class,sensor_a,sensor_b\n"
            "neg,1,2\n"
            "pos,3,4\n"
        )

        response = self.client.post(
            "/api/datasets/aps/predict",
            data={
                "file": (io.BytesIO(content.encode()), "records.csv"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("exactly one", response.get_json()["error"])

    @patch("llm_diagnostician.client.chat.completions.create")
    def test_local_diagnosis_does_not_call_external_llm(self, create):
        diagnosis = generate_aps_diagnosis_and_remediation(
            failure_probability=0.9,
            decision_threshold=0.75,
            feature_values={"sensor_a": 10.0},
            feature_attribution={"sensor_a": 100.0},
            use_llm=False,
        )

        self.assertFalse(diagnosis["llm_powered"])
        self.assertIn("sensor_a", diagnosis["root_cause"])
        create.assert_not_called()

    @patch("llm_diagnostician.client.chat.completions.create")
    def test_consented_llm_receives_prediction_context(self, create):
        create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"severity":"High","problem_title":"Review APS",'
                            '"problem_description":"Risk elevated.",'
                            '"root_cause":"Sensor anomaly.",'
                            '"risk_if_unresolved":"Inspect.",'
                            '"remediation_steps":[],"expected_outcome":"Human review."}'
                        )
                    )
                )
            ]
        )

        diagnosis = generate_aps_diagnosis_and_remediation(
            failure_probability=0.9,
            decision_threshold=0.75,
            feature_values={"sensor_a": 10.0},
            feature_attribution={"sensor_a": 100.0},
            use_llm=True,
        )

        self.assertTrue(diagnosis["llm_powered"])
        self.assertEqual(diagnosis["problem_title"], "Review APS")
        prompt = create.call_args.kwargs["messages"][1]["content"]
        self.assertIn("sensor_a", prompt)
        self.assertIn("90.0%", prompt)


if __name__ == "__main__":
    unittest.main()
