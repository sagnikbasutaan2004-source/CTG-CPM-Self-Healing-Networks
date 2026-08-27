"""
main.py
CTG-CPM: Self-Healing Networks & Host Maintenance via Counterfactual Telemetry
CLI Demonstrator and Pipeline Controller
"""

import sys
import time
from telemetry_collector import LaptopTelemetryCollector, SyntheticTelemetryGenerator
from counterfactual_engine import CounterfactualGenerator
from agentic_remediator import MultiAgentRemediator
from game_engine import BargainingGameTree

def print_banner():
    print("=" * 75)
    print("        CTG-CPM // Autonomous Self-Healing System (v1.0)")
    print(" Counterfactual Telemetry Generation + Game-Theoretic Agentic AI")
    print("=" * 75)

def run_live_laptop_demo():
    print("\n[STAGE 01] Live Laptop Host Telemetry Ingestion (psutil)...")
    collector = LaptopTelemetryCollector()
    metrics = collector.get_live_metrics()
    
    print(f" -> CPU Overall Load: {metrics['cpu_overall_percent']}% | Frequency: {metrics['cpu_frequency_mhz']} MHz")
    print(f" -> Memory Used: {metrics['memory_percent']}% ({metrics['memory_used_mb']} MB / {metrics['memory_available_mb']} MB avail)")
    print(f" -> Disk Read/Write: {metrics['disk_read_kbps']} KB/s / {metrics['disk_write_kbps']} KB/s")
    print(f" -> Battery Level: {metrics['battery_percent']}%")
    if metrics['top_processes']:
        print(f" -> Top CPU Process: {metrics['top_processes'][0]['name']} (PID: {metrics['top_processes'][0]['pid']}, CPU: {metrics['top_processes'][0]['cpu_percent']}%)")

    print("\n[STAGE 02 & 03] Multi-Agent Pipeline & Counterfactual 'What-If' Simulation...")
    remediator = MultiAgentRemediator()
    result = remediator.process_anomaly_and_remediate(metrics)

    print(f"\n[RESULTS] Execution Latency: {result['execution_latency_ms']} ms | MTTR: {result['mttr_seconds']}s")
    print(" -> VCG Auction Task Allocation:")
    for task, agent in result['vcg_task_allocation']['assignment'].items():
        print(f"    - Task '{task}' -> Assigned to: {agent}")
    
    print("\n -> Shapley Value Feature Attribution (Root Cause Weight):")
    for feat, pct in result['shapley_root_cause_attribution'].items():
        print(f"    - {feat}: {pct}%")

    print(f"\n -> Game Theory SPE Bargaining Outcome:\n    {result['spe_summary']}")
    print(f"\n -> Selected Remediation Action: {result['chosen_remediation']}")
    print(f" -> Digital Twin Verification Status: {'STABILIZED (SAFE)' if result['digital_twin_verified'] else 'UNSTABLE'}")
    print(f" -> Projected System Health Score: {result['projected_health_score']} / 100")

    print("\n[STAGE 04] Autonomous Script Execution Payload:")
    print("-" * 50)
    print(result['remediation_script'])
    print("-" * 50)
    print(">>> STATUS: AUTONOMOUS REMEDIATION COMPLETE (ZERO TRUCK ROLL) <<<")

def run_synthetic_5g_demo():
    print("\n[STAGE 01] Ingesting 5G Optical Backhaul Telemetry & Injecting OSNR Anomaly...")
    syn = SyntheticTelemetryGenerator()
    telemetry = syn.generate_network_telemetry(inject_anomaly=True)
    
    print(f" -> Transceiver OSNR: {telemetry['osnr_db']} dB (Threshold: 18.0 dB)")
    print(f" -> Laser Bias Current: {telemetry['laser_bias_ma']} mA")
    print(f" -> Operating Temp: {telemetry['temperature_celsius']} °C")
    print(f" -> Packet Loss: {telemetry['packet_loss_percent']}%")

    print("\n[STAGE 02, 03 & 04] Executing CTG-CPM Autonomous Self-Healing Pipeline...")
    remediator = MultiAgentRemediator()
    result = remediator.process_anomaly_and_remediate(telemetry)

    print(f"\n[SUMMARY] Pipeline Latency: {result['execution_latency_ms']} ms | MTTR: {result['mttr_seconds']} seconds")
    print(f" -> Shapley Root Cause Attribution: {result['shapley_root_cause_attribution']}")
    print(f" -> SPE Solution Path: {result['spe_bargaining_outcome']}")
    print(f" -> Autonomous Remediation Script (NETCONF/YANG):\n{result['remediation_script']}")
    print("\n>>> STATUS: 5G BACKHAUL FIBER LINK SELF-HEALED SUB-SECOND <<<")

if __name__ == "__main__":
    print_banner()
    print("\nSelect Demo Mode:")
    print("1. Live Laptop Host Telemetry & Self-Healing")
    print("2. 5G Optical Backhaul Fiber Anomaly (Simulated Counterfactual)")
    print("3. Solve Game-Theoretic Investment & Bargaining Game (SPE)")
    
    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        choice = "1" # Default to 1 for automated non-interactive run

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
