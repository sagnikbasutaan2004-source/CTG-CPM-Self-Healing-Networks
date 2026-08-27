"""
test_prototype.py
Automated Unit and Integration Test Suite for CTG-CPM Prototype
"""

import unittest
from game_engine import BargainingGameTree, VCGAuctionAllocator, ShapleyAttributor, NashEquilibriumCoordinator
from telemetry_collector import LaptopTelemetryCollector, SyntheticTelemetryGenerator
from counterfactual_engine import CounterfactualGenerator
from agentic_remediator import MultiAgentRemediator

class TestCTGCPMPrototype(unittest.TestCase):

    def test_game_tree_backward_induction(self):
        game = BargainingGameTree()
        sol = game.solve_backward_induction()
        spe = sol["spe_path"]
        
        self.assertEqual(spe["investment"], "Low")
        self.assertEqual(spe["proposal"], "Greedy")
        self.assertEqual(spe["response"], "Accept")
        self.assertEqual(spe["payoffs"], (13.0, 0.0))

    def test_vcg_auction_allocation(self):
        vcg = VCGAuctionAllocator()
        agents = ["Agent1", "Agent2", "Agent3"]
        tasks = ["TaskA", "TaskB", "TaskC"]
        bids = {
            "Agent1": {"TaskA": 90, "TaskB": 10, "TaskC": 10},
            "Agent2": {"TaskA": 20, "TaskB": 95, "TaskC": 10},
            "Agent3": {"TaskA": 10, "TaskB": 20, "TaskC": 100}
        }
        res = vcg.allocate_tasks(agents, tasks, bids)
        self.assertEqual(res["assignment"]["TaskA"], "Agent1")
        self.assertEqual(res["assignment"]["TaskB"], "Agent2")
        self.assertEqual(res["assignment"]["TaskC"], "Agent3")

    def test_laptop_telemetry_collector(self):
        collector = LaptopTelemetryCollector()
        metrics = collector.get_live_metrics()
        self.assertIn("cpu_overall_percent", metrics)
        self.assertIn("memory_percent", metrics)
        self.assertGreaterEqual(metrics["cpu_overall_percent"], 0.0)

    def test_counterfactual_generator(self):
        gen = CounterfactualGenerator()
        base = {"osnr_db": 16.5, "laser_bias_ma": 68.0, "temperature_celsius": 74.0, "packet_loss_percent": 3.0}
        interventions = [
            {"name": "Status Quo (No Action)", "cost": 0.0},
            {"name": "Load-Balance / CPU Throttle 15%", "cost": 1.0}
        ]
        res = gen.generate_counterfactuals(base, interventions)
        self.assertIn("Status Quo (No Action)", res)
        self.assertIn("Load-Balance / CPU Throttle 15%", res)
        self.assertTrue(res["Load-Balance / CPU Throttle 15%"]["is_stabilized"])

    def test_multi_agent_remediator_pipeline(self):
        syn = SyntheticTelemetryGenerator()
        anomaly = syn.generate_network_telemetry(inject_anomaly=True)
        remediator = MultiAgentRemediator()
        result = remediator.process_anomaly_and_remediate(anomaly)
        
        self.assertLess(result["mttr_seconds"], 10.0) # Verifies MTTR < 10 seconds
        self.assertTrue(result["digital_twin_verified"])
        self.assertIn("remediation_script", result)

if __name__ == "__main__":
    unittest.main()
