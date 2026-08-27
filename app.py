"""
app.py
CTG-CPM: Self-Healing Networks via Counterfactual Telemetry
Premium Flask Web Application with LLM-Powered Diagnostics
"""

from flask import Flask, jsonify, render_template, request
from telemetry_collector import LaptopTelemetryCollector, SyntheticTelemetryGenerator
from counterfactual_engine import CounterfactualGenerator
from agentic_remediator import MultiAgentRemediator
from game_engine import BargainingGameTree
from llm_diagnostician import generate_diagnosis_and_remediation

app = Flask(__name__)

laptop_collector = LaptopTelemetryCollector()
synthetic_generator = SyntheticTelemetryGenerator()
cf_generator = CounterfactualGenerator()
remediator = MultiAgentRemediator()
game_tree = BargainingGameTree()

anomaly_active = False
last_diagnosis = None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/telemetry", methods=["GET"])
def get_telemetry():
    mode = request.args.get("mode", "laptop")
    if mode == "laptop":
        data = laptop_collector.get_live_metrics()
        if anomaly_active:
            data["cpu_overall_percent"] = min(98.5, data["cpu_overall_percent"] + 65.0)
            data["anomaly_flag"] = True
        else:
            data["anomaly_flag"] = data["cpu_overall_percent"] > 85.0
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
            metrics["cpu_overall_percent"] = 96.4
            metrics["memory_percent"] = min(95.0, metrics["memory_percent"] + 15.0)
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
            "root_cause": "See Shapley attribution for root cause weights.",
            "risk_if_unresolved": "System may degrade further without intervention.",
            "remediation_steps": [
                {"step_number": 1, "action": "Review Telemetry", "detail": "Check system metrics.", "expected_impact": "Identify root cause."}
            ],
            "expected_outcome": "System stabilization.",
            "health_score_before": 30, "health_score_after": 83,
            "estimated_fix_time": "< 10 seconds",
            "truck_roll_avoided": True, "downtime_prevented": "Unknown",
            "llm_powered": False
        }

    result["llm_diagnosis"] = diagnosis
    last_diagnosis = diagnosis
    anomaly_active = False
    
    # Serialize counterfactual scenario time series (reduce payload)
    simplified_cf = {}
    for name, data in result["counterfactual_scenarios"].items():
        simplified_cf[name] = {
            "health_score": data["health_score"],
            "is_stabilized": data["is_stabilized"],
            "cost_score": data["cost_score"],
            "final_state": data["time_series_future"][-1] if data["time_series_future"] else {}
        }
    result["counterfactual_scenarios"] = simplified_cf

    return jsonify(result)

@app.route("/api/game_tree", methods=["GET"])
def get_game_tree():
    sol = game_tree.solve_backward_induction()
    return jsonify(sol)

@app.route("/api/last_diagnosis", methods=["GET"])
def get_last_diagnosis():
    if last_diagnosis:
        return jsonify(last_diagnosis)
    return jsonify({"error": "No diagnosis available. Run the pipeline first."})

if __name__ == "__main__":
    print("Starting CTG-CPM Dashboard Server on http://127.0.0.1:5000...")
    app.run(host="127.0.0.1", port=5000, debug=True)
