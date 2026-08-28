"""
dataset_generator.py
Dataset Generator for CTG-CPM 5G Optical Backhaul & Host Telemetry
Generates multivariate time-series telemetry datasets and graph topology structures
for training PyTorch GNN and Time-Series Diffusion models.
"""

import math
import random
import numpy as np
import torch
from typing import Dict, Tuple, List

class NetworkDatasetGenerator:
    """
    Generates realistic 5G Optical Backhaul and Host Telemetry Datasets:
    - 1,000 sequence samples of multivariate time-series
    - Graph topology adjacency matrices and node features
    - Intervention-conditioned counterfactual trajectory pairs
    """

    def __init__(self, num_samples: int = 1000, seq_len: int = 20, num_nodes: int = 10, seed: int = 42):
        self.num_samples = num_samples
        self.seq_len = seq_len
        self.num_nodes = num_nodes
        np.random.seed(seed)
        random.seed(seed)
        torch.manual_seed(seed)

    def generate_topology_graph(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generates 5G Backhaul network graph topology:
        - Adjacency matrix A (num_nodes x num_nodes)
        - Dynamic Node Feature Matrix X (num_nodes x 4: OSNR, Laser Bias, Temp, Packet Loss)
        - Node Anomaly Labels Y (num_nodes x 1)
        """
        # Create scale-free / small-world topology graph
        adj = np.zeros((self.num_nodes, self.num_nodes), dtype=np.float32)
        for i in range(self.num_nodes - 1):
            adj[i, i + 1] = 1.0
            adj[i + 1, i] = 1.0
            if i + 2 < self.num_nodes and np.random.rand() > 0.5:
                adj[i, i + 2] = 1.0
                adj[i + 2, i] = 1.0

        # Node features: [OSNR, Laser Bias, Temp, Packet Loss]
        node_features = np.zeros((self.num_nodes, 4), dtype=np.float32)
        node_labels = np.zeros((self.num_nodes, 1), dtype=np.float32)

        for i in range(self.num_nodes):
            is_anomalous = (np.random.rand() < 0.3)
            if is_anomalous:
                osnr = np.random.uniform(12.0, 17.5)
                laser_bias = np.random.uniform(65.0, 85.0)
                temp = np.random.uniform(70.0, 92.0)
                pkt_loss = np.random.uniform(2.0, 8.0)
                node_labels[i] = 1.0
            else:
                osnr = np.random.uniform(21.0, 24.5)
                laser_bias = np.random.uniform(40.0, 48.0)
                temp = np.random.uniform(45.0, 58.0)
                pkt_loss = np.random.uniform(0.0, 0.05)

            node_features[i] = [osnr, laser_bias, temp, pkt_loss]

        return adj, node_features, node_labels

    def generate_time_series_dataset(self) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Generates multivariate time-series sequence pairs for Diffusion-TS model training:
        - X_0: (num_samples, seq_len, 4) baseline time-series (OSNR, Bias, Temp, Loss)
        - Intervention_cond: (num_samples, 4) one-hot intervention conditioning
        - X_target: (num_samples, seq_len, 4) ground-truth target counterfactual time-series
        """
        X_0 = np.zeros((self.num_samples, self.seq_len, 4), dtype=np.float32)
        X_target = np.zeros((self.num_samples, self.seq_len, 4), dtype=np.float32)
        intervention_cond = np.zeros((self.num_samples, 4), dtype=np.float32)

        for s in range(self.num_samples):
            # Select intervention: 0=Status Quo, 1=Adjust Laser Bias, 2=Load-Balance, 3=Reroute
            inv_idx = np.random.randint(0, 4)
            intervention_cond[s, inv_idx] = 1.0

            # Initial baseline metrics
            osnr_0 = np.random.uniform(14.0, 24.0)
            bias_0 = np.random.uniform(42.0, 75.0)
            temp_0 = np.random.uniform(48.0, 85.0)
            loss_0 = np.random.uniform(0.01, 4.0)

            # Decay target parameters based on intervention
            if inv_idx == 0:  # Status Quo (degradation)
                decay = 0.05
                target_osnr, target_bias, target_temp, target_loss = max(10.0, osnr_0 - 5.0), min(90.0, bias_0 + 15.0), min(95.0, temp_0 + 20.0), min(10.0, loss_0 + 3.0)
            elif inv_idx == 1:  # Laser Bias / Cooling
                decay = 0.25
                target_osnr, target_bias, target_temp, target_loss = 23.0, 44.0, 52.0, 0.01
            elif inv_idx == 2:  # Load-Balance
                decay = 0.20
                target_osnr, target_bias, target_temp, target_loss = 22.0, 48.0, 56.0, 0.03
            else:  # Reroute
                decay = 0.18
                target_osnr, target_bias, target_temp, target_loss = 22.5, 46.0, 54.0, 0.01

            for t in range(self.seq_len):
                # Baseline sequence
                X_0[s, t, 0] = osnr_0 + np.sin(t * 0.2) * 0.2 + np.random.normal(0, 0.05)
                X_0[s, t, 1] = bias_0 + np.cos(t * 0.2) * 0.3 + np.random.normal(0, 0.1)
                X_0[s, t, 2] = temp_0 + np.sin(t * 0.1) * 0.4 + np.random.normal(0, 0.1)
                X_0[s, t, 3] = loss_0 + np.random.normal(0, 0.01)

                # Target counterfactual sequence (exponential trajectory)
                factor = 1.0 - math.exp(-decay * (t + 1))
                X_target[s, t, 0] = osnr_0 + (target_osnr - osnr_0) * factor + np.random.normal(0, 0.05)
                X_target[s, t, 1] = bias_0 + (target_bias - bias_0) * factor + np.random.normal(0, 0.1)
                X_target[s, t, 2] = temp_0 + (target_temp - temp_0) * factor + np.random.normal(0, 0.1)
                X_target[s, t, 3] = loss_0 + (target_loss - loss_0) * factor + np.random.normal(0, 0.005)

        return (
            torch.tensor(X_0, dtype=torch.float32),
            torch.tensor(intervention_cond, dtype=torch.float32),
            torch.tensor(X_target, dtype=torch.float32)
        )

if __name__ == "__main__":
    ds_gen = NetworkDatasetGenerator(num_samples=100)
    adj, node_x, node_y = ds_gen.generate_topology_graph()
    x0, cond, xt = ds_gen.generate_time_series_dataset()
    print("Graph Adjacency Shape:", adj.shape)
    print("Node Features Shape:", node_x.shape)
    print("Time-Series Dataset X0 Shape:", x0.shape)
    print("Intervention Conditioning Shape:", cond.shape)
