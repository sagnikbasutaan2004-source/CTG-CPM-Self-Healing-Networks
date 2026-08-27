"""
game_engine.py
Algorithmic Game Theory & Multi-Agent Optimization Engine for CTG-CPM

Includes:
1. BargainingGameTree: Extensive-Form Investment & Bargaining Game (Backward Induction / SPE)
2. VCGAuctionAllocator: VCG Auction Mechanism for DSIC Agent Task Allocation
3. ShapleyAttributor: Shapley Value Feature Attribution for Root Cause Analysis
4. NashEquilibriumCoordinator: Matrix Game Nash Equilibrium Solver for Remediation Actions
"""

import math
import itertools
from typing import Dict, Any, List, Tuple

class BargainingGameTree:
    """
    Extensive-Form Investment and Bargaining Game:
    - Player 2 (System Hardware/Node) chooses Investment level:
      High Investment (Surplus=18, Cost=2) or Low Investment (Surplus=14, Cost=1).
    - Player 1 (Remediation Agent) proposes split:
      Fair (50/50 split of surplus) or Greedy (P1 takes surplus-1, P2 gets 1).
    - Player 2 responds:
      Accept (P1 gets share, P2 gets share - cost) or Reject (0 surplus, P2 pays cost).
    """

    def __init__(self):
        self.high_surplus = 18.0
        self.high_cost_p2 = 2.0
        
        self.low_surplus = 14.0
        self.low_cost_p2 = 1.0

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
            return (0.0, 0.0 - cost)

        if response == "Accept":
            if proposal == "Fair":
                share_p1 = surplus / 2.0
                share_p2 = surplus / 2.0
            elif proposal == "Greedy":
                share_p1 = surplus - 1.0
                share_p2 = 1.0
            else:
                raise ValueError(f"Unknown proposal: {proposal}")

            return (share_p1, share_p2 - cost)

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
            "p2_decisions": p2_decisions,
            "p1_decisions": p1_decisions,
            "summary": f"SPE Outcome: Investment={best_inv}, Proposal={spe_proposal}, Response={spe_response} -> Payoff (u1={spe_payoff[0]}, u2={spe_payoff[1]})"
        }


class VCGAuctionAllocator:
    """
    Vickrey-Clarke-Groves (VCG) Auction for Multi-Agent Task Allocation:
    Ensures Dominant-Strategy Incentive Compatibility (DSIC) - agents bid truthful cost/capability.
    """

    def __init__(self):
        pass

    def allocate_tasks(self, agents: List[str], tasks: List[str], bids: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        """
        bids: {agent_id: {task_id: valuation_score}}
        Higher valuation = higher agent suitability for task.
        Returns optimal assignment and VCG payments/discounts.
        """
        # Find assignment maximizing total social welfare
        best_welfare = -float("inf")
        best_assignment = {}

        # Generate all valid assignments (one task per agent if possible)
        possible_assignments = list(itertools.permutations(agents, len(tasks))) if len(agents) >= len(tasks) else []

        for p in possible_assignments:
            current_assignment = {tasks[i]: p[i] for i in range(len(tasks))}
            welfare = sum(bids[p[i]][tasks[i]] for i in range(len(tasks)))
            if welfare > best_welfare:
                best_welfare = welfare
                best_assignment = current_assignment

        # Compute VCG payments/discounts for each assigned agent
        vcg_payments = {}
        for task, assigned_agent in best_assignment.items():
            # Welfare of others with assigned_agent present
            welfare_others_with = sum(bids[a][t] for t, a in best_assignment.items() if a != assigned_agent)

            # Welfare of others without assigned_agent present
            remaining_agents = [a for a in agents if a != assigned_agent]
            welfare_others_without = 0.0
            if remaining_agents and len(tasks) > 0:
                # Find optimal allocation for remaining agents
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
            "vcg_payments": {a: round(p, 2) for a, p in vcg_payments.items()}
        }


class ShapleyAttributor:
    """
    Shapley Value Decomposition for Fair Root-Cause Attribution:
    Calculates exact feature importance φ_i(v) for multivariate telemetry metrics.
    """

    @staticmethod
    def calculate_shapley_values(metrics: List[str], characteristic_fn) -> Dict[str, float]:
        """
        characteristic_fn(subset: Tuple[str]) -> float anomaly score
        """
        n = len(metrics)
        shapley_values = {m: 0.0 for m in metrics}

        all_subsets = []
        for r in range(n + 1):
            all_subsets.extend(itertools.combinations(metrics, r))

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

        # Normalize to percentage
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
    """

    @staticmethod
    def find_pure_nash_equilibrium(payoff_matrix_a: List[List[float]], payoff_matrix_b: List[List[float]], actions_a: List[str], actions_b: List[str]) -> List[Dict[str, Any]]:
        """
        Finds pure strategy Nash Equilibria for 2-agent normal form game.
        """
        num_rows = len(payoff_matrix_a)
        num_cols = len(payoff_matrix_a[0])

        equilibria = []

        # Find best responses for Agent A given Agent B's strategy col
        best_responses_a = set()
        for c in range(num_cols):
            max_val = max(payoff_matrix_a[r][c] for r in range(num_rows))
            for r in range(num_rows):
                if payoff_matrix_a[r][c] == max_val:
                    best_responses_a.add((r, c))

        # Find best responses for Agent B given Agent A's strategy row
        best_responses_b = set()
        for r in range(num_rows):
            max_val = max(payoff_matrix_b[r][c] for c in range(num_cols))
            for c in range(num_cols):
                if payoff_matrix_b[r][c] == max_val:
                    best_responses_b.add((r, c))

        # Nash equilibrium = intersection of best responses
        nash_pairs = best_responses_a.intersection(best_responses_b)

        for r, c in nash_pairs:
            equilibria.append({
                "action_a": actions_a[r],
                "action_b": actions_b[c],
                "payoff_a": payoff_matrix_a[r][c],
                "payoff_b": payoff_matrix_b[r][c],
            })

        return equilibria


if __name__ == "__main__":
    # Self-test
    tree = BargainingGameTree()
    sol = tree.solve_backward_induction()
    print("Game Tree SPE:", sol["summary"])

    vcg = VCGAuctionAllocator()
    res = vcg.allocate_tasks(
        agents=["Agent1_Diagnostician", "Agent2_Simulator", "Agent3_Executor"],
        tasks=["RootCauseAnalysis", "DigitalTwinSimulation", "ScriptDeployment"],
        bids={
            "Agent1_Diagnostician": {"RootCauseAnalysis": 95, "DigitalTwinSimulation": 40, "ScriptDeployment": 20},
            "Agent2_Simulator": {"RootCauseAnalysis": 50, "DigitalTwinSimulation": 90, "ScriptDeployment": 30},
            "Agent3_Executor": {"RootCauseAnalysis": 30, "DigitalTwinSimulation": 50, "ScriptDeployment": 98},
        }
    )
    print("\nVCG Auction Task Allocation:", res)
