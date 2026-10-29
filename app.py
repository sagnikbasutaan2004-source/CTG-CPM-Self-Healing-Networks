"""
app.py
CTG-CPM: Predictive Maintenance Recommendations via Counterfactual Telemetry
Premium Flask Web Application with Dynamic Game Theory & LLM Diagnostics
"""

import os
import csv
import io
import math
import threading
from pathlib import Path
from flask import Flask, jsonify, render_template, request
from telemetry_collector import LaptopTelemetryCollector, SyntheticTelemetryGenerator
from counterfactual_engine import CounterfactualGenerator
from agentic_remediator import MultiAgentRemediator
from game_engine import BargainingGameTree
from aps_dataset import DEFAULT_MODEL_PATH, load_saved_model, predict_aps_record
from llm_diagnostician import (
    generate_aps_diagnosis_and_remediation,
    generate_diagnosis_and_remediation,
)

# static_folder='.' lets Flask serve /static/<path> from the project root,
# so /static/benchmark_figures/*.png resolves to ./benchmark_figures/*.png
app = Flask(__name__, static_folder='.', static_url_path='/static')
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

laptop_collector = LaptopTelemetryCollector()
synthetic_generator = SyntheticTelemetryGenerator()
cf_generator = CounterfactualGenerator()
remediator = MultiAgentRemediator()

anomaly_active = False
last_diagnosis = None
aps_model_bundle = None
aps_model_lock = threading.Lock()


def _get_aps_model_bundle():
    global aps_model_bundle
    if aps_model_bundle is None:
        with aps_model_lock:
            if aps_model_bundle is None:
                model_path = Path(app.root_path) / DEFAULT_MODEL_PATH
                aps_model_bundle = load_saved_model(model_path)
    return aps_model_bundle


def _parse_aps_csv_record(file_storage, feature_names):
    try:
        content = file_storage.stream.read().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Upload a UTF-8 encoded CSV file.") from exc
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise ValueError("The uploaded CSV needs a header row with APS feature names.")
    normalized_headers = [header.strip() if header else "" for header in reader.fieldnames]
    headers = [header for header in normalized_headers if header]
    duplicates = sorted({name for name in headers if headers.count(name) > 1})
    if duplicates:
        raise ValueError("Duplicate CSV columns: " + ", ".join(duplicates[:10]))
    unknown = set(headers).difference(feature_names).difference({"class"})
    if unknown:
        raise ValueError(
            "Unknown APS CSV columns: " + ", ".join(sorted(unknown)[:10])
        )
    missing_columns = set(feature_names).difference(headers)
    if missing_columns:
        raise ValueError(
            "CSV is missing APS feature columns: "
            + ", ".join(sorted(missing_columns)[:10])
        )

    rows = list(reader)
    if len(rows) != 1:
        raise ValueError("Upload exactly one APS record per prediction.")
    normalized_row = {
        (key.strip() if key else ""): value
        for key, value in rows[0].items()
        if key is not None
    }
    record = {}
    for name in feature_names:
        raw_value = (normalized_row.get(name) or "").strip()
        if not raw_value or raw_value.lower() == "na":
            continue
        try:
            value = float(raw_value)
        except ValueError as exc:
            raise ValueError(f"Feature {name} must be numeric or NA.") from exc
        if not math.isfinite(value):
            raise ValueError(f"Feature {name} must be finite or NA.")
        record[name] = value
    return record


def _parse_manual_aps_record(payload, feature_names):
    if not isinstance(payload, dict):
        raise ValueError("Provide feature values in a JSON object.")
    record = payload.get("features")
    if not isinstance(record, dict):
        raise ValueError("Provide feature values in a JSON object.")
    unknown = set(record).difference(feature_names)
    if unknown:
        raise ValueError(
            "Unknown APS feature names: " + ", ".join(sorted(unknown)[:10])
        )
    parsed = {}
    for name, raw_value in record.items():
        if raw_value is None or raw_value == "":
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Feature {name} must be numeric or blank.") from exc
        if not math.isfinite(value):
            raise ValueError(f"Feature {name} must be finite or blank.")
        parsed[name] = value
    return parsed

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/telemetry", methods=["GET"])
def get_telemetry():
    mode = request.args.get("mode", "laptop")
    if mode == "laptop":
        data = laptop_collector.get_live_metrics()
        if anomaly_active:
            # Dynamic stress scaling factor based on live metrics
            data["cpu_overall_percent"] = round(min(99.0, max(85.0, data["cpu_overall_percent"] * 2.2 + 35.0)), 1)
            data["memory_percent"] = round(min(96.0, data["memory_percent"] * 1.35 + 15.0), 1)
            data["anomaly_flag"] = True
    else:
        data = synthetic_generator.generate_network_telemetry(inject_anomaly=anomaly_active)
    return jsonify(data)

@app.route("/api/toggle_anomaly", methods=["POST"])
def toggle_anomaly():
    global anomaly_active
    payload = request.json or {}
    anomaly_active = payload.get("active", not anomaly_active)
    return jsonify({"anomaly_active": anomaly_active})

@app.route("/api/run_pipeline", methods=["POST"])
def run_pipeline():
    global anomaly_active, last_diagnosis
    payload = request.json or {}
    mode = payload.get("mode", "laptop")

    if mode == "laptop":
        metrics = laptop_collector.get_live_metrics()
        if anomaly_active:
            # Dynamic live metric stress scaling
            metrics["cpu_overall_percent"] = round(min(99.0, max(88.0, metrics["cpu_overall_percent"] * 2.4 + 40.0)), 1)
            metrics["memory_percent"] = round(min(96.0, metrics["memory_percent"] * 1.35 + 15.0), 1)
            metrics["anomaly_flag"] = True
    else:
        metrics = synthetic_generator.generate_network_telemetry(inject_anomaly=True)

    result = remediator.process_anomaly_and_remediate(metrics)

    # Generate LLM-powered diagnosis
    try:
        diagnosis = generate_diagnosis_and_remediation(
            telemetry=metrics,
            shapley_attribution=result["shapley_root_cause_attribution"],
            spe_outcome=result["spe_bargaining_outcome"],
            counterfactual_scenarios=result["counterfactual_scenarios"],
            mode=mode
        )
    except Exception as e:
        diagnosis = {
            "severity": "High",
            "problem_title": "System Anomaly Detected",
            "problem_description": f"Anomaly detected in system telemetry. LLM analysis unavailable: {str(e)}",
            "root_cause": "See Shapley attribution for contributing feature weights.",
            "risk_if_unresolved": "System may degrade further without intervention.",
            "remediation_steps": [
                {"step_number": 1, "action": "Review Telemetry", "detail": "Check system metrics.", "expected_impact": "Identify contributing factors."}
            ],
            "expected_outcome": "Projected system stabilization (not yet applied/verified).",
            "health_score_before": 30, "health_score_after": 83,
            "estimated_fix_time": "Decision compute only; excludes deployment",
            "truck_roll_avoided": "unknown", "downtime_prevented": "Unknown",
            "llm_powered": False,
            "confidence_note": "Fallback values are heuristic estimates, not measured outcomes."
        }

    result["llm_diagnosis"] = diagnosis
    last_diagnosis = diagnosis
    anomaly_active = False

    # Serialize counterfactual scenario time series (reduce payload)
    simplified_cf = {}
    for name, data in result["counterfactual_scenarios"].items():
        simplified_cf[name] = {
            "projected_health_score": data["projected_health_score"],
            "projected_stabilized": data["projected_stabilized"],
            "generator": data["generator"],
            "cost_score": data["cost_score"],
            "final_state": data["time_series_future"][-1] if data["time_series_future"] else {}
        }
    result["counterfactual_scenarios"] = simplified_cf

    return jsonify(result)

@app.route("/api/game_tree", methods=["GET"])
def get_game_tree():
    mode = request.args.get("mode", "laptop")
    if mode == "laptop":
        metrics = laptop_collector.get_live_metrics()
    else:
        metrics = synthetic_generator.generate_network_telemetry(inject_anomaly=False)

    game_tree = BargainingGameTree.from_telemetry(metrics)
    sol = game_tree.solve_backward_induction()
    return jsonify(sol)

@app.route("/api/last_diagnosis", methods=["GET"])
def get_last_diagnosis():
    if last_diagnosis:
        return jsonify(last_diagnosis)
    return jsonify({"error": "No diagnosis available. Run the pipeline first."})

@app.route("/api/datasets/aps/features", methods=["GET"])
def get_aps_features():
    """Return the feature schema from the pre-trained inference checkpoint."""
    try:
        model = _get_aps_model_bundle()
    except (OSError, ValueError, RuntimeError) as exc:
        return jsonify({
            "error": "The pre-trained APS model is unavailable.",
            "details": str(exc),
        }), 503
    return jsonify({
        "dataset": model["dataset"],
        "feature_names": model["feature_names"],
        "usable_features": len(model["feature_indices"]),
        "threshold": model["threshold"],
    })


@app.route("/api/datasets/aps/predict", methods=["POST"])
def predict_aps_dataset_record():
    """Run single-record APS inference through the saved model and CTG-CPM."""
    try:
        model = _get_aps_model_bundle()
    except (OSError, ValueError, RuntimeError) as exc:
        return jsonify({
            "error": "The pre-trained APS model is unavailable.",
            "details": str(exc),
        }), 503

    try:
        if request.files.get("file"):
            record = _parse_aps_csv_record(
                request.files["file"],
                model["feature_names"],
            )
            llm_consent = request.form.get("llm_consent") == "true"
        else:
            payload = request.get_json(silent=True) or {}
            if not isinstance(payload, dict):
                raise ValueError("Provide feature values in a JSON object.")
            record = _parse_manual_aps_record(payload, model["feature_names"])
            llm_consent = payload.get("llm_consent") is True

        result = predict_aps_record(model, record, llm_consent=llm_consent)
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        app.logger.exception("APS single-record inference failed")
        return jsonify({
            "error": "APS inference failed.",
            "details": str(exc),
        }), 500

    result["diagnosis"] = generate_aps_diagnosis_and_remediation(
        result["failure_probability"],
        result["threshold"],
        result["top_feature_values"],
        result["feature_attribution_percent"],
        use_llm=llm_consent,
    )
    return jsonify(result)


@app.errorhandler(413)
def request_entity_too_large(_error):
    return jsonify({"error": "Upload is too large. Maximum request size is 1 MB."}), 413

if __name__ == "__main__":
    print("Starting CTG-CPM Dashboard Server on http://127.0.0.1:5000...")
    app.run(host="127.0.0.1", port=5000, debug=True)
