"""
test_prototype.py
Automated Unit and Integration Test Suite for CTG-CPM Prototype
Verifies zero-hardcoding dynamic mathematical models, PyTorch neural inference, and Kafka streaming bus.
"""

import unittest
from game_engine import BargainingGameTree, VCGAuctionAllocator, ShapleyAttributor, NashEquilibriumCoordinator
from telemetry_collector import LaptopTelemetryCollector, SyntheticTelemetryGenerator
from counterfactual_engine import CounterfactualGenerator
from agentic_remediator import MultiAgentRemediator
from kafka_telemetry_streaming import TelemetryKafkaProducer, TelemetryKafkaConsumer, TOPIC_RAW_TELEMETRY

class TestCTGCPMPrototype(unittest.TestCase):

    def test_game_tree_backward_induction_default(self):
        game = BargainingGameTree()
        sol = game.solve_backward_induction()
        spe = sol["spe_path"]
        self.assertEqual(spe["investment"], "Low")
        self.assertEqual(spe["proposal"], "Greedy")
        self.assertEqual(spe["response"], "Accept")
        self.assertEqual(spe["payoffs"], (13.0, 0.0))

    def test_game_tree_dynamic_from_telemetry(self):
        telemetry = {"osnr_db": 16.5, "temperature_celsius": 74.0, "laser_bias_ma": 68.0}
        game = BargainingGameTree.from_telemetry(telemetry)
        sol = game.solve_backward_induction()
        self.assertIn("spe_path", sol)
        self.assertIn("parameters", sol)
        self.assertGreater(sol["parameters"]["high_surplus"], 0)

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

    def test_dynamic_vcg_bids(self):
        telemetry = {"cpu_overall_percent": 88.0, "memory_percent": 75.0}
        agents = ["Agent1_Diagnostician", "Agent2_Bargainer", "Agent3_Executor"]
        tasks = ["RootCauseAttribution", "GameTheoreticNegotiation", "CounterfactualProjection"]
        bids = VCGAuctionAllocator.compute_dynamic_bids(agents, tasks, telemetry)
        self.assertIn("Agent1_Diagnostician", bids)
        self.assertGreater(bids["Agent1_Diagnostician"]["RootCauseAttribution"], 90.0)

    def test_dynamic_shapley_attribution(self):
        telemetry = {"osnr_db": 15.0, "temperature_celsius": 75.0, "laser_bias_ma": 70.0}
        char_fn = ShapleyAttributor.build_dynamic_characteristic_fn(telemetry)
        shapley = ShapleyAttributor.calculate_shapley_values(["osnr_db", "temperature_celsius", "laser_bias_ma"], char_fn)
        self.assertIn("osnr_db", shapley)
        self.assertEqual(round(sum(shapley.values()), 1), 100.0)

    def test_laptop_telemetry_collector(self):
        collector = LaptopTelemetryCollector()
        metrics = collector.get_live_metrics()
        self.assertIn("cpu_overall_percent", metrics)
        self.assertIn("memory_percent", metrics)
        self.assertIn("anomaly_flag", metrics)
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
        # Every scenario must be tagged with honest provenance and a projection-only note.
        for name, data in res.items():
            self.assertIn("generator", data)
            self.assertIn("is_learned", data)
            self.assertIn("note", data)
            self.assertNotIn("is_stabilized", data)  # removed misleading claim
        # A fix intervention should project stabilization vs. status quo (informational).
        self.assertTrue(res["Load-Balance / CPU Throttle 15%"]["projected_stabilized"])

    def test_multi_agent_remediator_pipeline(self):
        syn = SyntheticTelemetryGenerator()
        anomaly = syn.generate_network_telemetry(inject_anomaly=True)
        remediator = MultiAgentRemediator()
        result = remediator.process_anomaly_and_remediate(anomaly)

        self.assertLess(result["compute_latency_ms"], 2000.0)  # in-process diffusion inference on CPU (~150ms warm)
        # Honest deployment: must state it is NOT deployed by default.
        self.assertEqual(result["deployment_status"]["deployed"], False)
        self.assertIn("remediation_command", result)
        self.assertIn("vcg_task_allocation", result)
        self.assertIn("shapley_root_cause_attribution", result)
        self.assertIn("spe_bargaining_outcome", result)
        # Provenance present, no false "digital_twin_verified" field.
        self.assertIn("projection_generator", result)
        self.assertNotIn("digital_twin_verified", result)

    def test_kafka_telemetry_streaming(self):
        # Kafka must be REAL. Report status honestly rather than emulating a broker.
        producer = TelemetryKafkaProducer()
        if producer.connected:
            consumer = TelemetryKafkaConsumer(TOPIC_RAW_TELEMETRY)
            test_payload = {"source": "UnitTest", "cpu_overall_percent": 45.0, "timestamp": 12345.0}
            result = producer.send_telemetry(TOPIC_RAW_TELEMETRY, test_payload)
            self.assertTrue(result.get("ok", False))
            self.assertEqual(result.get("kafka_status"), "connected")
        else:
            # If no broker is reachable, the producer must NOT pretend it streamed.
            result = producer.send_telemetry(TOPIC_RAW_TELEMETRY,
                                             {"source": "UnitTest", "cpu_overall_percent": 45.0})
            self.assertFalse(result.get("ok", True))
            self.assertNotEqual(result.get("kafka_status"), "connected")

if __name__ == "__main__":
    unittest.main()
