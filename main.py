"""
main.py
CTG-CPM: Predictive Maintenance Decisions via Counterfactual Telemetry
CLI Demonstrator and Pipeline Controller with Apache Kafka Streaming Integration

Honest framing: this demo runs the multi-agent decision pipeline on LIVE host telemetry
(psutil) or synthetic optical telemetry. Kafka streaming is REAL when a broker is present
and honestly reports 'unavailable' otherwise. The system produces a remediation RECOMMENDATION;
it does not claim to have deployed a fix or achieved zero-risk autonomous healing.
"""

import sys
import time
from telemetry_collector import LaptopTelemetryCollector, SyntheticTelemetryGenerator
from counterfactual_engine import CounterfactualGenerator
from agentic_remediator import MultiAgentRemediator
from game_engine import BargainingGameTree

def print_banner():
    print("=" * 75)
    print("        CTG-CPM // Predictive Maintenance Decision System (v2.0)")
    print(" Counterfactual Telemetry Generation + Game-Theoretic Multi-Agent AI")
    print(" Layer 1: Real-Time Apache Kafka Telemetry Event Streaming (when broker present)")
    print("=" * 75)

def run_live_laptop_demo():
    print("\n[STAGE 01] Ingesting LIVE Laptop Host Telemetry (psutil) & Streaming to Kafka...")
    collector = LaptopTelemetryCollector()
    metrics = collector.get_live_metrics()

    print(f" -> Kafka Status: {metrics.get('kafka_status', 'unknown')}")
    print(f" -> CPU Overall Load: {metrics['cpu_overall_percent']}% | Frequency: {metrics['cpu_frequency_mhz']} MHz")
    print(f" -> Memory Used: {metrics['memory_percent']}% ({metrics['memory_used_mb']} MB / {metrics['memory_available_mb']} MB avail)")
    print(f" -> Disk Read/Write: {metrics['disk_read_kbps']} KB/s / {metrics['disk_write_kbps']} KB/s")
    print(f" -> Dynamic Anomaly Z-Score: {metrics.get('dynamic_z_score', 0.0)}")
    if metrics['top_processes']:
        print(f" -> Top CPU Process: {metrics['top_processes'][0]['name']} (PID: {metrics['top_processes'][0]['pid']}, CPU: {metrics['top_processes'][0]['cpu_percent']}%)")

    print("\n[STAGE 02 & 03] Multi-Agent Decision Pipeline & Counterfactual Projection...")
    remediator = MultiAgentRemediator()
    result = remediator.process_anomaly_and_remediate(metrics)

    print(f"\n[RESULTS] Compute Latency: {result['compute_latency_ms']} ms (in-process only, no LLM/deployment)")
    print(" -> VCG Auction Task Allocation:")
    for task, agent in result['vcg_task_allocation']['assignment'].items():
        print(f"    - Task '{task}' -> Assigned to: {agent}")

    print("\n -> Shapley Value Feature Attribution (Root-Cause Weight):")
    for feat, pct in result['shapley_root_cause_attribution'].items():
        print(f"    - {feat}: {pct}%")

    print(f"\n -> Game Theory SPE Bargaining Outcome:\n    {result['spe_summary']}")
    print(f"\n -> Recommended Remediation: {result['recommended_remediation']}")
    print(f" -> Projection generator: {result['projection_generator']}")
    print(f" -> Projected Health Score: {result['projected_health_score']} / 100")
    print(f" -> Recommendation note: {result['recommendation_note']}")

    print("\n[STAGE 04] Remediation Command (RECOMMENDATION ONLY - not auto-deployed):")
    print("-" * 50)
    print(result['remediation_command']['text'])
    print("-" * 50)
    print(f"Deployment status: {result['deployment_status']['status']} - {result['deployment_status']['note']}")

def run_synthetic_5g_demo():
    print("\n[STAGE 01] Ingesting 5G Optical Telemetry & Streaming to Kafka topic 'telemetry-network-stream'...")
    syn = SyntheticTelemetryGenerator()
    telemetry = syn.generate_network_telemetry(inject_anomaly=True)

    print(f" -> Kafka Status: {telemetry.get('kafka_status', 'unknown')}")
    print(f" -> Transceiver OSNR: {telemetry['osnr_db']} dB (Threshold: 18.0 dB)")
    print(f" -> Laser Bias Current: {telemetry['laser_bias_ma']} mA")
    print(f" -> Operating Temp: {telemetry['temperature_celsius']} °C")
    print(f" -> Dynamic Anomaly Index: {telemetry.get('dynamic_anomaly_index', 0.0)}")

    print("\n[STAGE 02, 03 & 04] Executing CTG-CPM Neural Multi-Agent Decision Pipeline...")
    remediator = MultiAgentRemediator()
    result = remediator.process_anomaly_and_remediate(telemetry)

    print(f"\n[SUMMARY] Compute Latency: {result['compute_latency_ms']} ms (in-process only)")
    print(f" -> GNN Risk Report: {result.get('gnn_cascade_report', {})}")
    print(f" -> Shapley Root-Cause Attribution: {result['shapley_root_cause_attribution']}")
    print(f" -> SPE Solution Path: {result['spe_bargaining_outcome']}")
    print(f" -> Recommended Remediation: {result['recommended_remediation']}")
    print(f" -> Remediation Command (RECOMMENDATION):\n{result['remediation_command']['text']}")
    print(f" -> Deployment status: {result['deployment_status']['status']}")
    print("\n>>> DECISION GENERATED. This is a recommendation; it has NOT been auto-deployed.")

if __name__ == "__main__":
    print_banner()
    print("\nSelect Demo Mode:")
    print("1. Live Laptop Host Telemetry (Real Kafka Streamed) & Remediation Recommendation")
    print("2. 5G Optical Backhaul Fiber Anomaly (Real Kafka Streamed & PyTorch Models)")
    print("3. Solve Game-Theoretic Investment & Bargaining Game (SPE)")
    print("   (Produces a remediation RECOMMENDATION; nothing is auto-deployed.)")

    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        choice = "1"

    if choice == "1":
        run_live_laptop_demo()
    elif choice == "2":
        run_synthetic_5g_demo()
    elif choice == "3":
        game = BargainingGameTree()
        sol = game.solve_backward_induction()
        print("\n=== EXTENSIVE FORM GAME BACKWARD INDUCTION ===")
        print(sol["summary"])
        print("\nFull SPE Path:", sol["spe_path"])
    else:
        run_live_laptop_demo()
