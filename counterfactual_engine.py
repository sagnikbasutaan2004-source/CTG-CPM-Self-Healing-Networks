"""
counterfactual_engine.py
Generative Counterfactual Telemetry Engine for CTG-CPM
Synthesizes hypothetical future time-series streams under candidate remediation interventions.

Honesty principles:
- The PyTorch Diffusion-TS model (diffusion_ts_model.pt) is the primary generator when weights
  are present and load correctly; the result records which engine produced it.
- When no trained weights are available, a clearly-labelled heuristic state-space trajectory
  model is used. It is NEVER presented as "digital-twin verified" — the engine reports the
  generator provenance and whether the output is a learned inference or a heuristic projection.
- Health scores are diagnostic summaries of the projected trajectories, not a claim that the
  fix has been applied and validated on live infrastructure.
"""

import os
import math
import random
from typing import Dict, Any, List
import numpy as np
import torch

try:
    from diffusion_ts_model import DiffusionTSModel
    PYTORCH_DIFFUSION_AVAILABLE = True
except ImportError:
    PYTORCH_DIFFUSION_AVAILABLE = False


class CounterfactualGenerator:
    """
    Synthesizes parallel "What-If" future telemetry streams conditioned on candidate interventions.

    Uses the trained PyTorch Diffusion-TS denoising model weights (diffusion_ts_model.pt)
    as the primary engine when available; otherwise uses an explicit heuristic trajectory
    model and says so in the per-scenario `model_used` field.
    """

    def __init__(self, horizon_steps: int = 20, weights_path: str = "diffusion_ts_model.pt"):
        self.horizon_steps = horizon_steps
        self.weights_path = weights_path
        self.pytorch_model = None
        self.model_loaded = False
        self.load_error = None

        if PYTORCH_DIFFUSION_AVAILABLE and os.path.exists(weights_path):
            try:
                self.pytorch_model = DiffusionTSModel(timesteps=50, in_channels=4, seq_len=20, cond_dim=4)
                self.pytorch_model.load_state_dict(torch.load(weights_path, map_location=torch.device('cpu')))
                self.pytorch_model.eval()
                self.model_loaded = True
            except Exception as e:
                self.pytorch_model = None
                self.load_error = str(e)

    def _exponential_trajectory(self, y0: float, y_target: float, decay_rate: float, step: int,
                                noise_scale: float = 0.05) -> float:
        """Explicit state-space heuristic projection (NOT a learned model)."""
        val = y_target + (y0 - y_target) * math.exp(-decay_rate * step)
        noise = random.uniform(-noise_scale, noise_scale)
        return val + noise

    def _needs_noop_targets(self, inv_name: str) -> bool:
        """Whether an intervention name maps to a 'no action' degraded trajectory."""
        return "Status Quo" in inv_name or "No Action" in inv_name

    def _heuristic_projection(self, current_state: Dict[str, Any], inv_name: str):
        """
        Explicit heuristic future projection. Returns only projected metric streams — no
        "verification" claim. The caller computes an informational health score on top.
        """
        is_network = "osnr_db" in current_state
        future_stream = []

        if is_network:
            osnr_0 = float(current_state.get("osnr_db", 20.0))
            laser_bias_0 = float(current_state.get("laser_bias_ma", 45.0))
            temp_0 = float(current_state.get("temperature_celsius", 50.0))
            packet_loss_0 = float(current_state.get("packet_loss_percent", 0.05))
        else:
            cpu_0 = float(current_state.get("cpu_overall_percent", 50.0))
            mem_0 = float(current_state.get("memory_percent", 40.0))
            temp_0 = float(current_state.get("temperature_proxy", 40.0 + (cpu_0 / 100.0) * 45.0))

        if self._needs_noop_targets(inv_name):
            decay_rate = 0.05
            if is_network:
                target_osnr, target_bias, target_temp, target_loss = (
                    max(10.0, osnr_0 - 6.0), min(90.0, laser_bias_0 + 20.0),
                    min(95.0, temp_0 + 25.0), min(15.0, packet_loss_0 + 5.0))
            else:
                target_cpu, target_temp = min(100.0, cpu_0 + 20.0), min(95.0, temp_0 + 20.0)
        elif "Laser Bias" in inv_name or "Thermal Cooling" in inv_name:
            decay_rate = 0.25
            if is_network:
                target_osnr, target_bias, target_temp, target_loss = (
                    min(23.5, max(21.0, osnr_0 + 4.5)), max(42.0, laser_bias_0 - 18.0),
                    max(50.0, temp_0 - 20.0), 0.01)
            else:
                target_cpu, target_temp = max(25.0, cpu_0 - 30.0), max(48.0, temp_0 - 22.0)
        elif "Load-Balance" in inv_name or "CPU Throttle" in inv_name:
            decay_rate = 0.20
            if is_network:
                target_osnr, target_bias, target_temp, target_loss = (
                    min(22.0, osnr_0 + 3.0), max(44.0, laser_bias_0 - 8.0),
                    max(55.0, temp_0 - 12.0), 0.03)
            else:
                target_cpu, target_temp = max(35.0, cpu_0 * 0.75), max(52.0, temp_0 - 14.0)
        else:  # Reroute / default
            decay_rate = 0.18
            if is_network:
                target_osnr, target_bias, target_temp, target_loss = (
                    min(22.5, osnr_0 + 3.5), max(43.0, laser_bias_0 - 10.0),
                    max(52.0, temp_0 - 15.0), 0.01)
            else:
                target_cpu, target_temp = max(30.0, cpu_0 - 25.0), max(50.0, temp_0 - 16.0)

        for step in range(1, self.horizon_steps + 1):
            if is_network:
                osnr_t = self._exponential_trajectory(osnr_0, target_osnr, decay_rate, step, 0.05)
                temp_t = self._exponential_trajectory(temp_0, target_temp, decay_rate, step, 0.1)
                bias_t = self._exponential_trajectory(laser_bias_0, target_bias, decay_rate, step, 0.1)
                loss_t = max(0.01, self._exponential_trajectory(packet_loss_0, target_loss, decay_rate, step, 0.01))
                future_stream.append({
                    "step": step,
                    "osnr_db": round(max(0.0, osnr_t), 2),
                    "laser_bias_ma": round(max(0.0, bias_t), 2),
                    "temperature_celsius": round(max(0.0, temp_t), 2),
                    "packet_loss_percent": round(max(0.0, loss_t), 3),
                })
            else:
                cpu_t = self._exponential_trajectory(cpu_0, target_cpu, decay_rate, step, 0.5)
                temp_t = self._exponential_trajectory(temp_0, target_temp, decay_rate, step, 0.3)
                future_stream.append({
                    "step": step,
                    "cpu_percent": round(max(0.0, min(100.0, cpu_t)), 1),
                    "temperature_celsius": round(max(0.0, temp_t), 1),
                })

        return future_stream

    def _pytorch_projection(self, current_state: Dict[str, Any], inv_idx: int):
        """
        Primary learned generator: reverse-diffusion sampling conditioned on the intervention.
        Only called for network telemetry when weights are loaded. Returns (projections, ok_flag).
        """
        if not (self.pytorch_model is not None and "osnr_db" in current_state):
            return [], False
        try:
            osnr_0 = float(current_state.get("osnr_db", 20.0))
            laser_bias_0 = float(current_state.get("laser_bias_ma", 45.0))
            temp_0 = float(current_state.get("temperature_celsius", 50.0))
            packet_loss_0 = float(current_state.get("packet_loss_percent", 0.05))

            cond_vec = torch.zeros((1, 4), dtype=torch.float32)
            cond_vec[0, inv_idx % 4] = 1.0

            x0_base = np.zeros((1, self.horizon_steps, 4), dtype=np.float32)
            for t in range(self.horizon_steps):
                x0_base[0, t] = [osnr_0, laser_bias_0, temp_0, packet_loss_0]
            x0_base_t = torch.tensor(x0_base, dtype=torch.float32)

            with torch.no_grad():
                synth_out = self.pytorch_model.sample_counterfactual(x0_base_t, cond_vec)
            synth_np = synth_out.cpu().numpy()[0]

            future_stream = []
            for step in range(1, self.horizon_steps + 1):
                s_idx = step - 1
                future_stream.append({
                    "step": step,
                    "osnr_db": round(max(0.0, float(synth_np[s_idx, 0])), 2),
                    "laser_bias_ma": round(max(0.0, float(synth_np[s_idx, 1])), 2),
                    "temperature_celsius": round(max(0.0, float(synth_np[s_idx, 2])), 2),
                    "packet_loss_percent": round(max(0.0, float(synth_np[s_idx, 3])), 3),
                })
            return future_stream, True
        except Exception:
            return [], False

    def _health_score(self, future_stream: List[Dict[str, Any]]) -> float:
        """
        Informational multi-attribute health score computed from the FINAL projected state.
        This is a diagnostic summary of the projection, NOT a claim about the live system.
        """
        if not future_stream:
            return 0.0
        final_step = future_stream[-1]
        is_network = "osnr_db" in final_step
        if is_network:
            penalty_temp = max(0.0, (final_step["temperature_celsius"] - 50.0) / 45.0)
            penalty_osnr = max(0.0, (22.4 - final_step["osnr_db"]) / 12.0)
            penalty_loss = min(1.0, final_step["packet_loss_percent"] / 5.0)
            overall_penalty = penalty_temp * 0.4 + penalty_osnr * 0.4 + penalty_loss * 0.2
            return round(max(0.0, min(100.0, 100.0 * (1.0 - overall_penalty))), 2)
        penalty_cpu = max(0.0, final_step["cpu_percent"] / 100.0)
        penalty_temp = max(0.0, (final_step["temperature_celsius"] - 45.0) / 50.0)
        overall_penalty = penalty_cpu * 0.5 + penalty_temp * 0.5
        return round(max(0.0, min(100.0, 100.0 * (1.0 - overall_penalty))), 2)

    def generate_counterfactuals(self, current_state: Dict[str, Any], interventions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Returns parallel projected futures. Each scenario is tagged with:
          - generator: "diffusion" | "heuristic"
          - is_learned: bool
          - projected_health_score (informational)
        No scenario is presented as having been executed/verified on the live system.
        """
        counterfactual_results = {}
        for inv_idx, inv in enumerate(interventions):
            inv_name = inv["name"]

            # Primary: learned diffusion (network telemetry only)
            future_stream, ok = self._pytorch_projection(current_state, inv_idx)
            generator = "diffusion" if ok else "heuristic"

            if not ok:
                future_stream = self._heuristic_projection(current_state, inv_name)

            health_score = self._health_score(future_stream)

            counterfactual_results[inv_name] = {
                "intervention": inv_name,
                "cost_score": float(inv.get("cost", 1.0)),
                "time_series_future": future_stream,
                "projected_health_score": health_score,
                "generator": generator,
                "is_learned": generator == "diffusion",
                "projected_stabilized": (health_score >= 40.0) if future_stream else False,
                "note": "PROJECTION ONLY - model output / heuristic projection, not applied to or verified on the live system."
            }

        return counterfactual_results


if __name__ == "__main__":
    from telemetry_collector import SyntheticTelemetryGenerator
    syn = SyntheticTelemetryGenerator()
    baseline = syn.generate_network_telemetry(inject_anomaly=True)

    cf_gen = CounterfactualGenerator()
    print("Diffusion weights loaded:", cf_gen.model_loaded)
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
        print(f"\nScenario: {inv} | Health: {data['projected_health_score']} | "
              f"Stabilized(proj): {data['projected_stabilized']} | Generator: {data['generator']}")
        if data["time_series_future"]:
            print(f"Final Future Metric State: {data['time_series_future'][-1]}")
