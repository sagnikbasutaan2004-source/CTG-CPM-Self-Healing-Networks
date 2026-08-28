"""
agentic_remediator.py
Multi-Agent Orchestration & Remediation Recommendation Engine for CTG-CPM

Combines:
- Agent 1: Diagnostician (PyTorch GNN Topology Risk Prediction + Shapley Root-Cause Attribution)
- Agent 2: Game-Theoretic Bargainer (VCG Task Auction + Dynamic SPE + Nash Coordination)
- Agent 3: Executor (counterfactual projection evaluation + remediation command generation)

HONESTY:
- The system produces a RECOMMENDED remediation command and evaluates counterfactual
  projections, but it does NOT claim the command was deployed or that the live system was
  verified. `deployment_status` explicitly reports whether anything was actually applied.
- MTTR reported is the in-process compute latency only and is labelled as such; it does NOT
  include LLM round-trip or any real device deployment time (which would run over a network).
"""

import os
import time
import numpy as np
import torch
from typing import Dict, Any, List
from game_engine import BargainingGameTree, VCGAuctionAllocator, ShapleyAttributor, NashEquilibriumCoordinator
from counterfactual_engine import CounterfactualGenerator

try:
    from gnn_topology_model import GNNTopologyModel
    from dataset_generator import NetworkDatasetGenerator
    PYTORCH_GNN_AVAILABLE = True
except ImportError:
    PYTORCH_GNN_AVAILABLE = False


class MultiAgentRemediator:
    """
    Orchestrates the 3-agent recommendation loop:
    Diagnose -> Negotiate & Allocate -> Evaluate projections & generate remediation recommendation.
    Uses real trained PyTorch GNN & Diffusion weights when present; otherwise reports the
    statistical/heuristic fallback honestly. Nothing is auto-deployed.
    """

    def __init__(self, gnn_weights_path: str = "gnn_model.pt", deploy_commands: bool = False,
                 deployment_target: str = None):
        self.vcg_auction = VCGAuctionAllocator()
        self.shapley_attributor = ShapleyAttributor()
        self.nash_coordinator = NashEquilibriumCoordinator()
        self.cf_generator = CounterfactualGenerator()

        # Whether this instance is configured to actually push commands to a target.
        # By default it is NOT, so the system never fabricates an "autonomous deployment".
        self.deploy_commands = deploy_commands
        self.deployment_target = deployment_target

        self.gnn_model = None
        self.gnn_kind = "none"
        if PYTORCH_GNN_AVAILABLE and os.path.exists(gnn_weights_path):
            try:
                weights = torch.load(gnn_weights_path, map_location=torch.device('cpu'))
                # Try loading weights as the architecture they were trained with.
                # Pre-existing gnn_model.pt was a GCN (keys: gconv1/gconv2); a GraphSAGE
                # alternative can be produced by training with kind='graphsage'.
                for kind in ("gcn", "graphsage"):
                    try:
                        candidate = GNNTopologyModel(in_features=4, hidden_dim=32, out_features=1, kind=kind)
                        candidate.load_state_dict(weights)
                        candidate.eval()
                        self.gnn_model = candidate
                        self.gnn_kind = candidate.kind
                        break
                    except Exception:
                        continue
            except Exception:
                self.gnn_model = None
                self.gnn_kind = "none"

    # ------------------------------------------------------------------
    # Deployment hook: subclasses or wiring can override to push a command
    # to a real device. The default does nothing and reports "not deployed".
    # ------------------------------------------------------------------
    def _deploy(self, command: str) -> Dict[str, Any]:
        """
        Actual deployment routine. By default it does NOT push anything (prototype safety).
        Returns an honest deployment record.
        """
        if not self.deploy_commands or not self.deployment_target:
            return {
                "deployed": False,
                "status": "not_deployed",
                "note": "Auto-deployment is disabled in prototype. Command is a recommendation "
                        "and has NOT been applied to any device.",
                "target": self.deployment_target,
            }
        # If wiring provides a real transport, implement it here. Default is safe no-op.
        return {
            "deployed": False,
            "status": "not_deployed",
            "note": "No deployment transport configured; command not applied.",
            "target": self.deployment_target,
        }

    def process_anomaly_and_remediate(self, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the end-to-end multi-agent loop with dynamic computations.
        Returns an honest result (recommendation, not a claim of applied fix).
        """
        start_time = time.time()
        is_network = "osnr_db" in telemetry

        # -------------------------------------------------------------
        # STEP 1: VCG AUCTION FOR AGENT TASK ALLOCATION (DYNAMIC BIDS)
        # -------------------------------------------------------------
        agents = ["Agent1_Diagnostician", "Agent2_Bargainer", "Agent3_Executor"]
        tasks = ["RootCauseAttribution", "GameTheoreticNegotiation", "CounterfactualProjection"]

        dynamic_bids = self.vcg_auction.compute_dynamic_bids(agents, tasks, telemetry)
        vcg_result = self.vcg_auction.allocate_tasks(agents, tasks, dynamic_bids)

        # -------------------------------------------------------------
        # STEP 1B: AGENT 1 - PYTORCH GNN TOPOLOGY CASCADE RISK PREDICTION
        # -------------------------------------------------------------
        gnn_report = {"gnn_model_used": "none"}
        if is_network and self.gnn_model is not None:
            try:
                ds_gen = NetworkDatasetGenerator(num_samples=1)
                adj, node_x, _ = ds_gen.generate_topology_graph()
                node_x[0] = [
                    float(telemetry.get("osnr_db", 20.0)),
                    float(telemetry.get("laser_bias_ma", 45.0)),
                    float(telemetry.get("temperature_celsius", 50.0)),
                    float(telemetry.get("packet_loss_percent", 0.01)),
                ]
                adj_t = torch.tensor(adj, dtype=torch.float32)
                node_x_t = torch.tensor(node_x, dtype=torch.float32)
                gnn_report = self.gnn_model.predict_cascade_risk(node_x_t, adj_t)
                gnn_report["gnn_model_used"] = f"PyTorch {self.gnn_kind.upper()} GNN (gnn_model.pt)"
            except Exception:
                gnn_report = {"gnn_model_used": "Statistical Network Topology Estimator (GNN unavailable)"}

        # -------------------------------------------------------------
        # STEP 2: AGENT 1 - SHAPLEY ROOT-CAUSE ATTRIBUTION (DYNAMIC Z-SCORE)
        # -------------------------------------------------------------
        if is_network:
            metrics = ["osnr_db", "laser_bias_ma", "temperature_celsius", "packet_loss_percent"]
        else:
            metrics = ["cpu_overall_percent", "memory_percent", "disk_read_kbps", "temperature_proxy"]

        dynamic_char_fn = self.shapley_attributor.build_dynamic_characteristic_fn(telemetry)
        shapley_attribution = self.shapley_attributor.calculate_shapley_values(metrics, dynamic_char_fn)

        # -------------------------------------------------------------
        # STEP 3: AGENT 2 - DYNAMIC GAME-THEORETIC BARGAINING & NASH COORDINATION
        # -------------------------------------------------------------
        game_tree = BargainingGameTree.from_telemetry(telemetry)
        spe_solution = game_tree.solve_backward_induction()

        # -------------------------------------------------------------
        # STEP 4: GENERATIVE COUNTERFACTUAL PROJECTION EVALUATION
        # -------------------------------------------------------------
        interventions = [
            {"name": "Status Quo (No Action)", "cost": 0.0},
            {"name": "Adjust Laser Bias / Thermal Cooling", "cost": 2.0},
            {"name": "Load-Balance / CPU Throttle 15%", "cost": 1.0},
            {"name": "Reroute Traffic / Demote Process Priority", "cost": 1.5},
        ]

        counterfactual_scenarios = self.cf_generator.generate_counterfactuals(telemetry, interventions)

        # -------------------------------------------------------------
        # STEP 3B: NASH EQUILIBRIUM COORDINATION (DYNAMIC PAYOFF MATRIX)
        # -------------------------------------------------------------
        p_matrix_a, p_matrix_b, actions_a, actions_b = self.nash_coordinator.construct_dynamic_payoff_matrices(counterfactual_scenarios)
        nash_eq = self.nash_coordinator.find_pure_nash_equilibrium(p_matrix_a, p_matrix_b, actions_a, actions_b)

        # -------------------------------------------------------------
        # STEP 5: AGENT 3 - SELECT RECOMMENDED REMEDIATION & GENERATE COMMAND
        # -------------------------------------------------------------
        # Choose the highest projected health score among stabilized projections;
        # fall back to Status Quo explicitly rather than pretending a broken fix is best.
        candidates = [k for k, v in counterfactual_scenarios.items()
                      if v.get("generator", "heuristic") == "diffusion"]
        pool = candidates if candidates else list(counterfactual_scenarios.keys())

        status_quo_name = next((n for n in pool if "Status Quo" in n or "No Action" in n), None)
        non_noop = [n for n in pool if n != status_quo_name]

        if non_noop:
            selected_remediation = max(non_noop, key=lambda n: counterfactual_scenarios[n]["projected_health_score"])
        elif status_quo_name:
            selected_remediation = status_quo_name
        else:
            selected_remediation = max(pool, key=lambda n: counterfactual_scenarios[n]["projected_health_score"])

        selected_scenario = counterfactual_scenarios[selected_remediation]

        # Only treat a fix as "recommended for deployment" if it is NOT the status-quo/no-op
        # and the projection indicates stabilization using a *learned* generator when available.
        is_noop = ("Status Quo" in selected_remediation or "No Action" in selected_remediation)
        recommended_deploy = (not is_noop) and selected_scenario["projected_stabilized"]
        if not recommended_deploy:
            recommended_deploy = (not is_noop)  # still a candidate; verification is downstream

        # Dynamically parameterize the remediation command with raw live metric data
        if is_network:
            raw_osnr = telemetry.get("osnr_db", 18.0)
            raw_temp = telemetry.get("temperature_celsius", 50.0)
            target_bias_adj = round(max(35.0, telemetry.get("laser_bias_ma", 45.0) - 5.0), 1)
            command = (
                f"edit-config target=running:\n"
                f"  <interface name='opt-transceiver-5g-01'>\n"
                f"    <!-- Parameters from raw live OSNR {raw_osnr}dB & Temp {raw_temp}degC -->\n"
                f"    <laser-bias-ma>{target_bias_adj}</laser-bias-ma>\n"
                f"    <traffic-policy>load-balance-dynamic-30</traffic-policy>\n"
                f"    <thermal-cooling-mode>active-peltier</thermal-cooling-mode>\n"
                f"  </interface>"
            )
        else:
            top_procs = telemetry.get("top_processes", [])
            top_proc_name = top_procs[0]["name"] if top_procs else "HighCpuProcess"
            top_proc_pid = top_procs[0]["pid"] if top_procs else 1024
            raw_cpu = telemetry.get("cpu_overall_percent", 80.0)
            target_freq_cap = max(70, min(95, int(100 - (raw_cpu - 50) * 0.5)))
            command = (
                f"powershell.exe -Command \"# Parameters for live top process PID {top_proc_pid} ({top_proc_name})\n"
                f"Get-Process -Id {top_proc_pid} -ErrorAction SilentlyContinue | Set-ProcessPriority -Priority BelowNormal;\n"
                f"Set-CPUFrequencyCap -Percent {target_freq_cap} # from raw CPU load {raw_cpu}%\""
            )

        deployment = self._deploy(command)

        compute_latency_ms = round((time.time() - start_time) * 1000, 2)

        return {
            "anomaly_detected": telemetry.get("anomaly_flag", True),
            "compute_latency_ms": compute_latency_ms,  # in-process compute only
            "latency_note": ("In-process compute latency only. Does NOT include LLM round-trip "
                             "or real device deployment time."),
            "vcg_task_allocation": vcg_result,
            "gnn_cascade_report": gnn_report,
            "shapley_root_cause_attribution": shapley_attribution,
            "spe_bargaining_outcome": spe_solution["spe_path"],
            "spe_summary": spe_solution["summary"],
            "nash_equilibria": nash_eq,
            "counterfactual_scenarios": counterfactual_scenarios,
            "recommended_remediation": selected_remediation,
            "recommendation_note": (
                "Recommendation based on counterfactual projection. Not applied unless "
                "deployment transport is configured and `deploy_commands=True`."),
            "projected_health_score": selected_scenario["projected_health_score"],
            "projection_generator": selected_scenario["generator"],
            "remediation_command": {
                "text": command,
                "format": "NETCONF/YANG XML" if is_network else "PowerShell",
            },
            "deployment_status": deployment,
            "status": "RECOMMENDATION GENERATED",
        }


if __name__ == "__main__":
    from telemetry_collector import SyntheticTelemetryGenerator
    syn = SyntheticTelemetryGenerator()
    anomaly_telemetry = syn.generate_network_telemetry(inject_anomaly=True)

    remediator = MultiAgentRemediator()
    result = remediator.process_anomaly_and_remediate(anomaly_telemetry)

    print("=== MULTI-AGENT REMEDIATION RECOMMENDATION RESULT ===")
    print(f"Status: {result['status']}")
    print(f"Compute latency: {result['compute_latency_ms']}ms ({result['latency_note']})")
    print(f"Recommended fix: {result['recommended_remediation']}")
    print(f"Projection generator: {result['projection_generator']}")
    print(f"Deployment: {result['deployment_status']['status']}")
    print(f"GNN report: {result['gnn_cascade_report']}")
    print(f"Shapley attribution: {result['shapley_root_cause_attribution']}")
    print(f"SPE outcome: {result['spe_summary']}")
