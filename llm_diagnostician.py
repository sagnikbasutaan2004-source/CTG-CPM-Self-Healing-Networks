"""
llm_diagnostician.py
LLM-Powered Intelligent Diagnostician for CTG-CPM
Uses Groq API to generate human-readable problem diagnosis and step-by-step remediation plans.
"""

import os
from groq import Groq
from typing import Dict, Any

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

client = Groq(api_key=GROQ_API_KEY)

def generate_diagnosis_and_remediation(telemetry: Dict[str, Any], shapley_attribution: Dict[str, float], spe_outcome: Dict[str, Any], counterfactual_scenarios: Dict[str, Any], mode: str = "laptop") -> Dict[str, Any]:
    """
    Uses Groq LLM to generate:
    1. A clear, human-readable problem diagnosis
    2. Step-by-step remediation plan
    3. Risk assessment
    4. Expected outcome after remediation
    """

    if mode == "laptop":
        telemetry_summary = (
            f"CPU Usage: {telemetry.get('cpu_overall_percent', 'N/A')}%, "
            f"Memory Usage: {telemetry.get('memory_percent', 'N/A')}% ({telemetry.get('memory_used_mb', 'N/A')} MB used / {telemetry.get('memory_available_mb', 'N/A')} MB available), "
            f"CPU Frequency: {telemetry.get('cpu_frequency_mhz', 'N/A')} MHz, "
            f"Disk Read: {telemetry.get('disk_read_kbps', 'N/A')} KB/s, "
            f"Disk Write: {telemetry.get('disk_write_kbps', 'N/A')} KB/s, "
            f"Battery: {telemetry.get('battery_percent', 'N/A')}%"
        )
        system_type = "laptop/desktop computer"
    else:
        telemetry_summary = (
            f"OSNR: {telemetry.get('osnr_db', 'N/A')} dB (threshold: 18.0 dB), "
            f"Laser Bias Current: {telemetry.get('laser_bias_ma', 'N/A')} mA, "
            f"Temperature: {telemetry.get('temperature_celsius', 'N/A')} °C, "
            f"Packet Loss: {telemetry.get('packet_loss_percent', 'N/A')}%, "
            f"Throughput: {telemetry.get('throughput_gbps', 'N/A')} Gbps"
        )
        system_type = "5G optical backhaul network transceiver"

    # Build shapley attribution string
    shapley_str = ", ".join([f"{k}: {v}%" for k, v in shapley_attribution.items()])

    # Build counterfactual summary
    cf_lines = []
    for name, data in counterfactual_scenarios.items():
        hs = data.get("projected_health_score", data.get("health_score", "N/A"))
        stab = data.get("projected_stabilized", data.get("is_stabilized", False))
        cf_lines.append(f"  - '{name}': Projected Health Score = {hs}/100, Stabilized(proj) = {stab}")
    cf_summary = "\n".join(cf_lines)

    prompt = f"""You are CTG-CPM, a predictive maintenance recommendation AI system. Analyze the following telemetry data from a {system_type} and provide a comprehensive diagnosis.

## Live Telemetry Data
{telemetry_summary}

## Root Cause Attribution (Shapley Value Analysis)
The following features are contributing to the detected anomaly with these weights:
{shapley_str}

## Counterfactual "What-If" Simulation Results
We simulated multiple remediation scenarios. Here are the projected outcomes:
{cf_summary}

## Game-Theoretic Equilibrium Analysis
The Subgame Perfect Equilibrium (SPE) recommends: Investment Level = {spe_outcome.get('investment', 'N/A')}, Strategy = {spe_outcome.get('proposal', 'N/A')}, Response = {spe_outcome.get('response', 'N/A')}

Based on this analysis, provide your response in EXACTLY this JSON format (no markdown, no code blocks, just raw JSON):
{{
  "severity": "Critical|High|Medium|Low",
  "problem_title": "A short, clear title of the detected problem",
  "problem_description": "A detailed 2-3 sentence description of what is happening and why it matters, written for a NOC engineer or system administrator",
  "root_cause": "A clear explanation of the primary contributing factors identified through feature attribution (Shapley) analysis - NOT a validated causal conclusion",
  "risk_if_unresolved": "What will happen if this issue is not addressed within the next 1-4 hours",
  "remediation_steps": [
    {{
      "step_number": 1,
      "action": "Short action title",
      "detail": "Detailed instruction for this step",
      "expected_impact": "What this step fixes"
    }},
    {{
      "step_number": 2,
      "action": "Short action title",
      "detail": "Detailed instruction for this step",
      "expected_impact": "What this step fixes"
    }},
    {{
      "step_number": 3,
      "action": "Short action title",
      "detail": "Detailed instruction for this step",
      "expected_impact": "What this step fixes"
    }}
  ],
  "expected_outcome": "What the system state will look like after all remediation steps are applied (projected)",
  "health_score_before": {counterfactual_scenarios.get('Status Quo (No Action)', {}).get('projected_health_score', counterfactual_scenarios.get('Status Quo (No Action)', {}).get('health_score', 30))},
  "health_score_after": {max((s.get('projected_health_score', s.get('health_score', 0)) for s in counterfactual_scenarios.values()))},
  "estimated_fix_time": "X seconds/minutes (decision compute only; excludes deployment)",
  "truck_roll_avoided": "potential (not measured)",
  "downtime_prevented": "Estimated downtime that was prevented"
}}"""

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": "You are CTG-CPM, a predictive maintenance recommendation AI. You analyze system telemetry data and provide clear, actionable diagnosis and recommended remediation plans. Always respond with valid JSON only, no markdown formatting. Do NOT include any thinking or reasoning tags."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        response_text = completion.choices[0].message.content.strip()
        
        # Try to parse JSON from response
        import json
        import re
        
        # Strip <think>...</think> tags (Qwen models include these)
        response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL).strip()
        
        # Strip any markdown code block markers if present
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
        
        # Try to extract JSON from the response if there's surrounding text
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            response_text = json_match.group(0)
        
        diagnosis = json.loads(response_text)
        diagnosis["llm_powered"] = True
        diagnosis["model"] = "openai/gpt-oss-20b"
        return diagnosis
        
    except Exception as e:
        # Fallback if LLM call fails
        return _generate_fallback_diagnosis(telemetry, shapley_attribution, counterfactual_scenarios, mode, str(e))


def _top_shapley_cause(shapley) -> str:
    """Returns a human-readable top contributor from the computed Shapley attribution."""
    try:
        if shapley:
            top = max(shapley, key=lambda k: float(shapley[k]))
            return f"{top} is the highest-contributing telemetry feature ({float(shapley[top]):.0f}% weighted)"
    except Exception:
        pass
    return "The primary degrading feature (per Shapley attribution)"


def _generate_fallback_diagnosis(telemetry, shapley, cf_scenarios, mode, error_msg=""):
    """Fallback diagnosis when LLM is unavailable."""
    if mode == "laptop":
        return {
            "severity": "High" if telemetry.get("cpu_overall_percent", 0) > 80 else "Medium",
            "problem_title": "Elevated System Resource Utilization Detected",
            "problem_description": f"CPU utilization is at {telemetry.get('cpu_overall_percent', 'N/A')}% with memory at {telemetry.get('memory_percent', 'N/A')}%. This indicates thermal stress and potential performance degradation risk.",
            "root_cause": "High CPU workload combined with memory pressure is causing thermal stress on the system.",
            "risk_if_unresolved": "Continued operation at these levels may cause thermal throttling, application crashes, or hardware degradation within 2-4 hours.",
            "remediation_steps": [
                {"step_number": 1, "action": "Identify Resource-Heavy Processes", "detail": "Open Task Manager and sort by CPU usage to identify the top consuming processes.", "expected_impact": "Identifies the source of excessive resource consumption."},
                {"step_number": 2, "action": "Apply CPU Throttling", "detail": "Reduce CPU frequency cap to 85% to lower thermal output while maintaining functionality.", "expected_impact": "Reduces thermal stress by 15-20%."},
                {"step_number": 3, "action": "Optimize Memory Allocation", "detail": "Close unnecessary background applications and clear system cache to free memory.", "expected_impact": "Frees up RAM and reduces swap usage."}
            ],
            "expected_outcome": "System health score improves from 45/100 to 83/100 (projected by counterfactual heuristic). CPU temperature stabilizes below safe threshold.",
            "health_score_before": 45,
            "health_score_after": 83,
            "estimated_fix_time": "Decision compute only (ms); full deployment time not measured",
            "truck_roll_avoided": "unknown (potential, not measured)",
            "downtime_prevented": "2-4 hours of potential system downtime (estimate)",
            "llm_powered": False,
            "fallback_reason": error_msg,
            "confidence_note": "Rule-based fallback figures are heuristic estimates, not measured outcomes."
        }
    else:
        return {
            "severity": "Critical",
            "problem_title": "5G Optical Signal Degradation (OSNR Below Threshold)",
            "problem_description": f"OSNR has degraded to {telemetry.get('osnr_db', 'N/A')} dB, below the 18.0 dB safety threshold. Laser bias current elevated to {telemetry.get('laser_bias_ma', 'N/A')} mA with thermal stress at {telemetry.get('temperature_celsius', 'N/A')} °C.",
            "root_cause": f"{_top_shapley_cause(shapley)} combined with thermal stress from elevated operating temperature.",
            "risk_if_unresolved": "Without intervention, the transceiver may continue degrading and could cause a backhaul link outage affecting downstream nodes (estimate).",
            "remediation_steps": [
                {"step_number": 1, "action": "Adjust Laser Bias Current", "detail": "Apply NETCONF/YANG configuration to optimize laser bias current to compensate for degradation.", "expected_impact": "Potential OSNR stabilization above 18.0 dB (projected, not live-verified)."},
                {"step_number": 2, "action": "Load-Balance Traffic", "detail": "Shift 30% of traffic to backup wavelength to reduce thermal stress on primary transceiver.", "expected_impact": "May reduce operating temperature (projected)."},
                {"step_number": 3, "action": "Schedule Preventive Maintenance", "detail": "Flag the transceiver for maintenance window replacement as a precaution.", "expected_impact": "May help avoid an emergency truck roll (potential benefit)."}
            ],
            "expected_outcome": "OSNR projected to stabilize above 20 dB, temperature below 60 degC (counterfactual projection, not live-verified).",
            "health_score_before": 24,
            "health_score_after": 85,
            "estimated_fix_time": "Decision compute only (ms); full deployment time not measured",
            "truck_roll_avoided": "unknown (potential, not measured)",
            "downtime_prevented": "48 hours of potential backhaul outage (estimate)",
            "llm_powered": False,
            "fallback_reason": error_msg,
            "confidence_note": "Rule-based fallback figures are heuristic estimates, not measured outcomes."
        }


if __name__ == "__main__":
    # Quick test
    test_telemetry = {
        "cpu_overall_percent": 92.5,
        "memory_percent": 78.3,
        "memory_used_mb": 12400,
        "memory_available_mb": 3400,
        "cpu_frequency_mhz": 2901.0,
        "disk_read_kbps": 500,
        "disk_write_kbps": 1200,
        "battery_percent": 85
    }
    test_shapley = {"cpu_overall_percent": 50.0, "memory_percent": 15.0, "disk_read_kbps": 5.0, "temperature_proxy": 30.0}
    test_spe = {"investment": "Low", "proposal": "Greedy", "response": "Accept"}
    test_cf = {
        "Status Quo (No Action)": {"health_score": 24.5, "is_stabilized": False},
        "Load-Balance / CPU Throttle 15%": {"health_score": 83.0, "is_stabilized": True}
    }

    result = generate_diagnosis_and_remediation(test_telemetry, test_shapley, test_spe, test_cf, mode="laptop")
    import json
    print(json.dumps(result, indent=2))
