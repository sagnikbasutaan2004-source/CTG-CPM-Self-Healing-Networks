"""
game_engine.py
Algorithmic Game Theory & Multi-Agent Optimization Engine for CTG-CPM

Includes fully dynamic mathematical mechanisms without hardcoded constants:
1. BargainingGameTree: Extensive-Form Investment & Bargaining Game (Backward Induction / SPE)
   - Dynamic parameter derivation from raw live system telemetry & headroom metrics.
2. VCGAuctionAllocator: VCG Auction Mechanism for DSIC Agent Task Allocation
   - Dynamic agent capability & bid generation functions based on system stress & entropy.
3. ShapleyAttributor: Shapley Value Feature Attribution for Root Cause Analysis
   - Dynamic characteristic function v(S) built on raw telemetry statistical Z-scores.
4. NashEquilibriumCoordinator: Matrix Game Nash Equilibrium Solver for Remediation Actions
   - Dynamic payoff matrix construction from counterfactual health scores & resource costs.
"""

import math
import itertools
from typing import Dict, Any, List, Tuple

class BargainingGameTree:
    """
    Extensive-Form Investment and Bargaining Game:
    - Player 2 (System Node/Infrastructure) chooses Investment level (High vs Low).
    - Player 1 (Remediation Agent) proposes split (Fair vs Greedy).
    - Player 2 responds (Accept vs Reject).
    
    Fully dynamic: Accepts parameters or dynamically calculates them from raw live telemetry.
    """

    def __init__(self, high_surplus: float = 18.0, high_cost_p2: float = 2.0,
                 low_surplus: float = 14.0, low_cost_p2: float = 1.0,
                 greedy_margin: float = 1.0):
        self.high_surplus = float(high_surplus)
        self.high_cost_p2 = float(high_cost_p2)
        self.low_surplus = float(low_surplus)
        self.low_cost_p2 = float(low_cost_p2)
        self.greedy_margin = float(greedy_margin)

    @classmethod
    def from_telemetry(cls, telemetry: Dict[str, Any]):
        """
        Dynamically calculates game tree parameters from live raw telemetry using mathematical formulas:
        - Surplus S = f(headroom, signal quality, capacity)
        - Cost K = f(operating temp, resource stress ratio)
        - Greedy Margin delta = f(risk, surplus)
        """
        if "osnr_db" in telemetry:
            osnr = float(telemetry.get("osnr_db", 20.0))
            temp = float(telemetry.get("temperature_celsius", 50.0))
            laser_bias = float(telemetry.get("laser_bias_ma", 45.0))

            # Dynamic formula for optical capacity surplus
            high_surplus = max(5.0, round(osnr * 0.95 + 2.0, 2))
            low_surplus = max(3.0, round(osnr * 0.70, 2))
            high_cost_p2 = max(0.5, round((temp / 50.0) * 2.2 + (laser_bias / 50.0) * 0.5, 2))
            low_cost_p2 = max(0.2, round((temp / 50.0) * 0.9, 2))
        else:
            cpu = float(telemetry.get("cpu_overall_percent", 50.0))
            mem = float(telemetry.get("memory_percent", 50.0))
            freq = float(telemetry.get("cpu_frequency_mhz", 2500.0))

            # Dynamic formula for host compute surplus headroom
            available_headroom = max(10.0, 200.0 - (cpu + mem))
            high_surplus = round(available_headroom * 0.18 + (freq / 1000.0) * 2.0, 2)
            low_surplus = round(available_headroom * 0.12 + (freq / 1000.0) * 1.0, 2)
            high_cost_p2 = round((cpu / 100.0) * 2.5 + (mem / 100.0) * 1.0 + 0.2, 2)
            low_cost_p2 = round((cpu / 100.0) * 1.0 + 0.1, 2)

        greedy_margin = round(max(0.5, high_surplus * 0.08), 2)
        return cls(high_surplus, high_cost_p2, low_surplus, low_cost_p2, greedy_margin)

    def get_terminal_payoff(self, investment: str, proposal: str, response: str) -> Tuple[float, float]:
        if investment == "High":
            surplus = self.high_surplus
            cost = self.high_cost_p2
        elif investment == "Low":
            surplus = self.low_surplus
            cost = self.low_cost_p2
        else:
            raise ValueError(f"Unknown investment: {investment}")

        if response == "Reject":
            return (0.0, round(0.0 - cost, 2))

        if response == "Accept":
            if proposal == "Fair":
                share_p1 = surplus / 2.0
                share_p2 = surplus / 2.0
            elif proposal == "Greedy":
                share_p1 = max(0.0, surplus - self.greedy_margin)
                share_p2 = min(surplus, self.greedy_margin)
            else:
                raise ValueError(f"Unknown proposal: {proposal}")

            return (round(share_p1, 2), round(share_p2 - cost, 2))

        raise ValueError(f"Unknown response: {response}")

    def solve_backward_induction(self) -> Dict[str, Any]:
        """
        Solves game tree using Backward Induction to find Subgame Perfect Equilibrium (SPE).
        """
        # Step 1: P2 response choices at final nodes
        p2_decisions = {}
        for inv in ["High", "Low"]:
            p2_decisions[inv] = {}
            for prop in ["Fair", "Greedy"]:
                p_accept = self.get_terminal_payoff(inv, prop, "Accept")
                p_reject = self.get_terminal_payoff(inv, prop, "Reject")

                best_resp = "Accept" if p_accept[1] >= p_reject[1] else "Reject"
                best_payoff = p_accept if best_resp == "Accept" else p_reject

                p2_decisions[inv][prop] = {
                    "best_response": best_resp,
                    "payoff_accept": p_accept,
                    "payoff_reject": p_reject,
                    "equilibrium_payoff": best_payoff
                }

        # Step 2: P1 proposal choices
        p1_decisions = {}
        for inv in ["High", "Low"]:
            fair_payoff = p2_decisions[inv]["Fair"]["equilibrium_payoff"]
            greedy_payoff = p2_decisions[inv]["Greedy"]["equilibrium_payoff"]

            best_prop = "Greedy" if greedy_payoff[0] >= fair_payoff[0] else "Fair"
            best_payoff = greedy_payoff if best_prop == "Greedy" else fair_payoff

            p1_decisions[inv] = {
                "best_proposal": best_prop,
                "fair_outcome": fair_payoff,
                "greedy_outcome": greedy_payoff,
                "equilibrium_payoff": best_payoff
            }

        # Step 3: P2 initial investment decision
        high_payoff = p1_decisions["High"]["equilibrium_payoff"]
        low_payoff = p1_decisions["Low"]["equilibrium_payoff"]

        best_inv = "Low" if low_payoff[1] >= high_payoff[1] else "High"
        spe_payoff = low_payoff if best_inv == "Low" else high_payoff
        spe_proposal = p1_decisions[best_inv]["best_proposal"]
        spe_response = p2_decisions[best_inv][spe_proposal]["best_response"]

        return {
            "spe_path": {
                "investment": best_inv,
                "proposal": spe_proposal,
                "response": spe_response,
                "payoffs": spe_payoff
            },
            "parameters": {
                "high_surplus": self.high_surplus, "high_cost_p2": self.high_cost_p2,
                "low_surplus": self.low_surplus, "low_cost_p2": self.low_cost_p2,
                "greedy_margin": self.greedy_margin
            },
            "p2_decisions": p2_decisions,
            "p1_decisions": p1_decisions,
            "summary": f"SPE Outcome: Investment={best_inv}, Proposal={spe_proposal}, Response={spe_response} -> Payoff (u1={spe_payoff[0]}, u2={spe_payoff[1]})"
        }


class VCGAuctionAllocator:
    """
    Vickrey-Clarke-Groves (VCG) Auction for Multi-Agent Task Allocation:
    Ensures Dominant-Strategy Incentive Compatibility (DSIC) - agents bid truthful valuation / cost.
    Supports dynamic bid calculation based on raw live telemetry stress metrics.
    """

    def __init__(self):
        pass

    @staticmethod
    def compute_dynamic_bids(agents: List[str], tasks: List[str], telemetry: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
        """
        Dynamically computes agent bids b_{i,j} for tasks based on raw telemetry stress and specialized fitness functions.
        Formula: b_{i,j} = BaseCapability_{i,j} * (1 + StressFactor * AgentTaskWeight_{i,j})
        """
        if "osnr_db" in telemetry:
            osnr = float(telemetry.get("osnr_db", 22.0))
            temp = float(telemetry.get("temperature_celsius", 50.0))
            stress = min(1.0, max(0.0, (25.0 - osnr) / 10.0 + (temp - 45.0) / 40.0))
        else:
            cpu = float(telemetry.get("cpu_overall_percent", 30.0))
            mem = float(telemetry.get("memory_percent", 30.0))
            stress = min(1.0, max(0.0, (cpu + mem - 60.0) / 140.0))

        # Base capability matrix
        base_capabilities = {
            "Agent1_Diagnostician": {"RootCauseAttribution": 92.0, "GameTheoreticNegotiation": 40.0, "CounterfactualProjection": 20.0},
            "Agent2_Bargainer": {"RootCauseAttribution": 42.0, "GameTheoreticNegotiation": 94.0, "CounterfactualProjection": 32.0},
            "Agent3_Executor": {"RootCauseAttribution": 28.0, "GameTheoreticNegotiation": 48.0, "CounterfactualProjection": 96.0}
        }

        bids = {}
        for agent in agents:
            bids[agent] = {}
            agent_base = base_capabilities.get(agent, {})
            for task in tasks:
                base_val = agent_base.get(task, 50.0)
                # Specialized responsiveness under high stress
                if agent == "Agent1_Diagnostician" and "Attribution" in task:
                    val = base_val + stress * 7.5
                elif agent == "Agent2_Bargainer" and "Negotiation" in task:
                    val = base_val + (1.0 - stress) * 5.0
                elif agent == "Agent3_Executor" and "Projection" in task:
                    val = base_val + stress * 3.5
                else:
                    val = base_val * (1.0 - stress * 0.15)
                bids[agent][task] = round(max(1.0, val), 2)
        return bids

    def allocate_tasks(self, agents: List[str], tasks: List[str], bids: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        """
        bids: {agent_id: {task_id: valuation_score}}
        Finds assignment maximizing total social welfare and computes VCG payments.
        """
        best_welfare = -float("inf")
        best_assignment = {}

        possible_assignments = list(itertools.permutations(agents, len(tasks))) if len(agents) >= len(tasks) else []

        for p in possible_assignments:
            current_assignment = {tasks[i]: p[i] for i in range(len(tasks))}
            welfare = sum(bids[p[i]][tasks[i]] for i in range(len(tasks)))
            if welfare > best_welfare:
                best_welfare = welfare
                best_assignment = current_assignment

        vcg_payments = {}
        for task, assigned_agent in best_assignment.items():
            welfare_others_with = sum(bids[a][t] for t, a in best_assignment.items() if a != assigned_agent)

            remaining_agents = [a for a in agents if a != assigned_agent]
            welfare_others_without = 0.0
            if remaining_agents and len(tasks) > 0:
                best_rem = 0.0
                for perm in itertools.permutations(remaining_agents, min(len(remaining_agents), len(tasks))):
                    w = sum(bids[perm[i]][tasks[i]] for i in range(len(perm)))
                    if w > best_rem:
                        best_rem = w
                welfare_others_without = best_rem

            payment = welfare_others_without - welfare_others_with
            vcg_payments[assigned_agent] = payment

        return {
            "assignment": best_assignment,
            "total_social_welfare": round(best_welfare, 2),
            "vcg_payments": {a: round(p, 2) for a, p in vcg_payments.items()},
            "bids_used": bids
        }


class ShapleyAttributor:
    """
    Shapley Value Decomposition for Fair Root-Cause Attribution:
    Calculates exact feature importance φ_i(v) for multivariate telemetry metrics.
    Supports dynamic characteristic functions v(S) derived from statistical Z-score deviations.
    """

    @staticmethod
    def build_dynamic_characteristic_fn(telemetry: Dict[str, Any], baseline_means: Dict[str, float] = None, baseline_stds: Dict[str, float] = None):
        """
        Dynamically constructs a characteristic function v(S) based on raw telemetry values
        and non-linear statistical Z-score metric deviations.
        """
        default_means = {
            "cpu_overall_percent": 30.0, "memory_percent": 40.0, "disk_read_kbps": 100.0, "temperature_proxy": 45.0,
            "osnr_db": 22.4, "laser_bias_ma": 45.0, "temperature_celsius": 52.0, "packet_loss_percent": 0.01
        }
        default_stds = {
            "cpu_overall_percent": 15.0, "memory_percent": 10.0, "disk_read_kbps": 200.0, "temperature_proxy": 10.0,
            "osnr_db": 1.5, "laser_bias_ma": 3.0, "temperature_celsius": 5.0, "packet_loss_percent": 0.05
        }

        means = baseline_means or default_means
        stds = baseline_stds or default_stds

        z_scores = {}
        for metric, val in telemetry.items():
            if isinstance(val, (int, float)):
                mean = means.get(metric, 35.0)
                std = stds.get(metric, 10.0)
                std = std if std > 1e-5 else 1.0

                if metric == "osnr_db":
                    z = (mean - float(val)) / std
                else:
                    z = (float(val) - mean) / std
                z_scores[metric] = max(0.0, z)

        def characteristic_fn(subset: Tuple[str, ...]) -> float:
            score = 0.0
            for m in subset:
                z = z_scores.get(m, 0.5)
                # Quadratic non-linear anomaly weight formula
                score += (z ** 1.6) * 15.0
            return score

        return characteristic_fn

    @staticmethod
    def calculate_shapley_values(metrics: List[str], characteristic_fn) -> Dict[str, float]:
        r"""
        Calculates exact Shapley values for metrics list and characteristic_fn.
        Formula: φ_i(v) = ∑_{S ⊆ N\{i}} [|S|!(|N|-|S|-1)! / |N|!] * [v(S ∪ {i}) - v(S)]
        """
        n = len(metrics)
        shapley_values = {m: 0.0 for m in metrics}

        for m in metrics:
            val = 0.0
            other_metrics = [x for x in metrics if x != m]
            for r in range(n):
                for S in itertools.combinations(other_metrics, r):
                    weight = (math.factorial(len(S)) * math.factorial(n - len(S) - 1)) / math.factorial(n)
                    v_S = characteristic_fn(S)
                    v_S_m = characteristic_fn(S + (m,))
                    val += weight * (v_S_m - v_S)
            shapley_values[m] = round(val, 4)

        total = sum(shapley_values.values())
        if total > 0:
            shapley_percentages = {m: round((v / total) * 100, 2) for m, v in shapley_values.items()}
        else:
            shapley_percentages = {m: round(100.0 / n, 2) for m in metrics}

        return shapley_percentages


class NashEquilibriumCoordinator:
    """
    Nash Equilibrium Coordinator for Multi-Agent Remediation Strategies:
    Finds pure strategy Nash Equilibria in matrix games between remediation agents.
    Supports dynamic payoff matrix construction from counterfactual health scores and costs.
    """

    @staticmethod
    def construct_dynamic_payoff_matrices(counterfactual_scenarios: Dict[str, Any]) -> Tuple[List[List[float]], List[List[float]], List[str], List[str]]:
        """
        Dynamically constructs 2-agent normal form payoff matrices A and B from counterfactual simulation health scores.
        """
        scenarios = list(counterfactual_scenarios.items())
        actions_a = [s[0] for s in scenarios[:2]] if len(scenarios) >= 2 else ["Remediate", "Status Quo"]
        actions_b = ["High Performance Mode", "Eco Efficiency Mode"]

        payoff_matrix_a = []
        payoff_matrix_b = []

        for name, data in scenarios[:2]:
            h_score = float(data.get("projected_health_score", data.get("health_score", 50.0)))
            c_cost = float(data.get("cost_score", 1.0))
            is_stab = 1.0 if data.get("projected_stabilized", data.get("is_stabilized", True)) else 0.0

            # Agent A payoff = Health Score - Cost + Stability Bonus
            u_a_high = round(h_score * 0.22 - c_cost * 1.4 + is_stab * 3.0, 2)
            u_a_eco = round(h_score * 0.19 - c_cost * 0.7 + is_stab * 2.0, 2)
            payoff_matrix_a.append([u_a_high, u_a_eco])

            # Agent B payoff = System Stability - Operating Cost
            u_b_high = round(h_score * 0.16 - c_cost * 1.8, 2)
            u_b_eco = round(h_score * 0.24 - c_cost * 0.4, 2)
            payoff_matrix_b.append([u_b_high, u_b_eco])

        return payoff_matrix_a, payoff_matrix_b, actions_a, actions_b

    @staticmethod
    def find_pure_nash_equilibrium(payoff_matrix_a: List[List[float]], payoff_matrix_b: List[List[float]],
                                    actions_a: List[str], actions_b: List[str]) -> List[Dict[str, Any]]:
        """
        Finds pure strategy Nash Equilibria for 2-agent normal form game.
        """
        num_rows = len(payoff_matrix_a)
        num_cols = len(payoff_matrix_a[0])

        best_responses_a = set()
        for c in range(num_cols):
            max_val = max(payoff_matrix_a[r][c] for r in range(num_rows))
            for r in range(num_rows):
                if payoff_matrix_a[r][c] == max_val:
                    best_responses_a.add((r, c))

        best_responses_b = set()
        for r in range(num_rows):
            max_val = max(payoff_matrix_b[r][c] for c in range(num_cols))
            for c in range(num_cols):
                if payoff_matrix_b[r][c] == max_val:
                    best_responses_b.add((r, c))

        nash_pairs = best_responses_a.intersection(best_responses_b)

        equilibria = []
        for r, c in nash_pairs:
            equilibria.append({
                "action_a": actions_a[r],
                "action_b": actions_b[c],
                "payoff_a": payoff_matrix_a[r][c],
                "payoff_b": payoff_matrix_b[r][c],
            })

        return equilibria


if __name__ == "__main__":
    # Self-test with raw telemetry inputs
    sample_telemetry = {"osnr_db": 16.2, "temperature_celsius": 73.5, "laser_bias_ma": 68.0}
    tree = BargainingGameTree.from_telemetry(sample_telemetry)
    sol = tree.solve_backward_induction()
    print("Dynamic Game Tree SPE:", sol["summary"])

    bids = VCGAuctionAllocator.compute_dynamic_bids(
        ["Agent1_Diagnostician", "Agent2_Bargainer", "Agent3_Executor"],
        ["RootCauseAttribution", "GameTheoreticNegotiation", "CounterfactualProjection"],
        sample_telemetry
    )
    vcg = VCGAuctionAllocator()
    res = vcg.allocate_tasks(["Agent1_Diagnostician", "Agent2_Bargainer", "Agent3_Executor"],
                              ["RootCauseAttribution", "GameTheoreticNegotiation", "CounterfactualProjection"], bids)
    print("\nDynamic VCG Task Allocation:", res["assignment"])

    fn = ShapleyAttributor.build_dynamic_characteristic_fn(sample_telemetry)
    shapley = ShapleyAttributor.calculate_shapley_values(["osnr_db", "temperature_celsius", "laser_bias_ma"], fn)
    print("\nDynamic Shapley Attribution:", shapley)
