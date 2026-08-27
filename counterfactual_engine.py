"""
counterfactual_engine.py
Generative Counterfactual Telemetry Engine for CTG-CPM
Synthesizes hypothetical future time-series streams under candidate remediation interventions.
"""

import time
import math
import random
from typing import Dict, Any, List

class CounterfactualGenerator:
    """
    Synthesizes parallel "What-If" future telemetry streams conditioned on candidate interventions.
    Models physical constraints and degradation curves.
    """

    def __init__(self, horizon_steps: int = 20):
        self.horizon_steps = horizon_steps # 20 time steps into future

    def generate_counterfactuals(self, current_state: Dict[str, Any], interventions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        current_state: baseline metric dictionary (Live laptop or Synthetic Network)
        interventions: list of candidate remediation actions
        Returns parallel simulated time-series futures and outcome scores.
        """
        counterfactual_results = {}

        is_network = "osnr_db" in current_state

        for inv in interventions:
            inv_name = inv["name"]
            future_stream = []
            
            # Extract baseline metrics
            if is_network:
                osnr = current_state["osnr_db"]
                laser_bias = current_state["laser_bias_ma"]
                temp = current_state["temperature_celsius"]
                packet_loss = current_state["packet_loss_percent"]
            else:
                cpu = current_state["cpu_overall_percent"]
                temp = 72.0 if cpu > 80 else 55.0 # Thermal proxy
                mem = current_state["memory_percent"]

            # Intervene and simulate trajectory over horizon
            for step in range(1, self.horizon_steps + 1):
                t = step * 0.5
                
                if inv_name == "Status Quo (No Action)":
                    if is_network:
                        osnr = max(10.0, osnr - 0.3 * step + random.uniform(-0.1, 0.1))
                        temp = min(95.0, temp + 0.8 * step + random.uniform(-0.2, 0.2))
                        laser_bias = min(90.0, laser_bias + 0.5 * step)
                        packet_loss = min(15.0, packet_loss + 0.2 * step)
                    else:
                        cpu = min(100.0, cpu + 0.5 * step)
                        temp = min(95.0, temp + 0.9 * step)

                elif inv_name == "Adjust Laser Bias / Thermal Cooling":
                    if is_network:
                        osnr = min(23.5, osnr + 0.5 * step + random.uniform(-0.05, 0.05))
                        temp = max(50.0, temp - 0.9 * step)
                        laser_bias = max(42.0, laser_bias - 0.7 * step)
                        packet_loss = max(0.01, packet_loss - 0.1 * step)
                    else:
                        temp = max(45.0, temp - 1.2 * step)
                        cpu = max(20.0, cpu - 0.8 * step)

                elif inv_name == "Load-Balance / CPU Throttle 15%":
                    if is_network:
                        osnr = min(21.0, osnr + 0.3 * step)
                        temp = max(55.0, temp - 0.4 * step)
                        packet_loss = max(0.05, packet_loss - 0.05 * step)
                    else:
                        cpu = max(35.0, cpu * 0.85 - 0.5 * step)
                        temp = max(50.0, temp - 0.6 * step)

                elif inv_name == "Reroute Traffic / Demote Process Priority":
                    if is_network:
                        osnr = min(22.0, osnr + 0.4 * step)
                        temp = max(52.0, temp - 0.5 * step)
                        packet_loss = 0.01
                    else:
                        cpu = max(30.0, cpu - 1.5 * step)
                        temp = max(48.0, temp - 0.8 * step)

                if is_network:
                    future_stream.append({
                        "step": step,
                        "osnr_db": round(osnr, 2),
                        "laser_bias_ma": round(laser_bias, 2),
                        "temperature_celsius": round(temp, 2),
                        "packet_loss_percent": round(packet_loss, 3)
                    })
                else:
                    future_stream.append({
                        "step": step,
                        "cpu_percent": round(cpu, 1),
                        "temperature_celsius": round(temp, 1)
                    })

            # Calculate final health score and risk
            final_step = future_stream[-1]
            if is_network:
                health_score = 100.0 - (final_step["temperature_celsius"] - 50.0) * 0.5 - (23.0 - final_step["osnr_db"]) * 4.0 - final_step["packet_loss_percent"] * 5.0
                stabilized = final_step["osnr_db"] >= 18.0 and final_step["temperature_celsius"] <= 70.0
            else:
                health_score = 100.0 - final_step["cpu_percent"] * 0.4 - (final_step["temperature_celsius"] - 45.0) * 0.6
                stabilized = final_step["temperature_celsius"] <= 75.0

            counterfactual_results[inv_name] = {
                "intervention": inv_name,
                "cost_score": inv.get("cost", 1.0),
                "time_series_future": future_stream,
                "health_score": round(max(0.0, min(100.0, health_score)), 2),
                "is_stabilized": stabilized
            }

        return counterfactual_results

if __name__ == "__main__":
    from telemetry_collector import SyntheticTelemetryGenerator
    syn = SyntheticTelemetryGenerator()
    baseline = syn.generate_network_telemetry(inject_anomaly=True)
    
    cf_gen = CounterfactualGenerator()
    results = cf_gen.generate_counterfactuals(
        baseline,
        interventions=[
            {"name": "Status Quo (No Action)", "cost": 0.0},
            {"name": "Adjust Laser Bias / Thermal Cooling", "cost": 2.0},
            {"name": "Load-Balance / CPU Throttle 15%", "cost": 1.0},
            {"name": "Reroute Traffic / Demote Process Priority", "cost": 1.5}
        ]
    )
    
    print("=== COUNTERFACTUAL 'WHAT-IF' GENERATION RESULTS ===")
    for inv, data in results.items():
        print(f"\nScenario: {inv} | Health Score: {data['health_score']} | Stabilized: {data['is_stabilized']}")
        print(f"Final Future Metric State: {data['time_series_future'][-1]}")
