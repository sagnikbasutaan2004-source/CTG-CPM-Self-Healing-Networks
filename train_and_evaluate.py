"""
train_and_evaluate.py
Training & Empirical Evaluation Pipeline for CTG-CPM PyTorch Neural Network Models
Trains GraphSAGE GNN & Diffusion-TS Time-Series Generator, computes FID score, ROC-AUC, MTTR,
saves model weights (.pt), and exports empirical benchmark plots.
"""

import time
import os
import math
import numpy as np
import scipy.linalg
import matplotlib.pyplot as plt
import torch
import torch.optim as optim
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score

from dataset_generator import NetworkDatasetGenerator
from gnn_topology_model import GNNTopologyModel
from diffusion_ts_model import DiffusionTSModel

# Configure matplotlib dark aesthetic theme for CTG-CPM
plt.style.use('dark_background')
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['axes.edgecolor'] = '#30363D'
plt.rcParams['axes.facecolor'] = '#161B22'
plt.rcParams['figure.facecolor'] = '#0D1117'

def calculate_time_series_fid(real_ts: np.ndarray, synth_ts: np.ndarray) -> float:
    """
    Calculates Fréchet Inception Distance (FID) between real and generated synthetic time-series distributions.
    FID = ||μ_r - μ_g||^2 + Tr(Σ_r + Σ_g - 2 * sqrt(Σ_r * Σ_g))
    """
    # Reshape (N, T, C) -> (N, T * C)
    n_samples, seq_len, channels = real_ts.shape
    real_flat = real_ts.reshape(n_samples, -1)
    synth_flat = synth_ts.reshape(n_samples, -1)

    mu_r, sigma_r = np.mean(real_flat, axis=0), np.cov(real_flat, rowvar=False)
    mu_g, sigma_g = np.mean(synth_flat, axis=0), np.cov(synth_flat, rowvar=False)

    # Difference of means
    diff = mu_r - mu_g

    # Regularize covariance product to keep sqrtm numerically stable
    eps = 1e-6
    prod = sigma_r.dot(sigma_g) + np.eye(sigma_r.shape[0]) * eps
    sqrt_res = scipy.linalg.sqrtm(prod)
    covmean = sqrt_res[0] if isinstance(sqrt_res, tuple) else sqrt_res

    # Handle numerical imaginary component if present
    if np.iscomplexobj(covmean):
        covmean = covmean.real

    fid = diff.dot(diff) + np.trace(sigma_r + sigma_g - 2.0 * covmean)
    return float(max(0.0, fid))

def train_and_evaluate_all():
    print("=" * 75)
    print("      CTG-CPM: Training PyTorch Neural Models & Empirical Evaluation")
    print("=" * 75)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using Device: {device}")

    # 1. Dataset Generation
    print("\n[STEP 1] Generating 5G Optical Backhaul & Host Telemetry Datasets...")
    ds_gen = NetworkDatasetGenerator(num_samples=1000, seq_len=20, num_nodes=10)
    adj, node_x, node_y = ds_gen.generate_topology_graph()
    x0, cond, xt_target = ds_gen.generate_time_series_dataset()

    adj_t = torch.tensor(adj, dtype=torch.float32).to(device)
    node_x_t = torch.tensor(node_x, dtype=torch.float32).to(device)
    node_y_t = torch.tensor(node_y, dtype=torch.float32).to(device)

    x0_t = x0.to(device)
    cond_t = cond.to(device)
    xt_target_t = xt_target.to(device)

    # 2. Train GraphSAGE GNN Model
    print("\n[STEP 2] Training PyTorch GraphSAGE GNN Topology Model (20 Epochs)...")
    gnn_model = GNNTopologyModel(in_features=4, hidden_dim=32, out_features=1).to(device)
    gnn_optimizer = optim.Adam(gnn_model.parameters(), lr=0.01)
    bce_loss_fn = torch.nn.BCELoss()

    gnn_losses = []
    for epoch in range(1, 21):
        gnn_model.train()
        gnn_optimizer.zero_grad()
        probs, _ = gnn_model(node_x_t, adj_t)
        loss = bce_loss_fn(probs, node_y_t)
        loss.backward()
        gnn_optimizer.step()
        gnn_losses.append(loss.item())
        if epoch % 5 == 0 or epoch == 1:
            print(f"  Epoch {epoch:02d}/20 | GNN Loss: {loss.item():.4f}")

    # Save GNN weights
    torch.save(gnn_model.state_dict(), "gnn_model.pt")
    print("  -> Saved GNN weights to 'gnn_model.pt'")

    # Evaluate GNN metrics
    gnn_model.eval()
    with torch.no_grad():
        final_probs, _ = gnn_model(node_x_t, adj_t)
        probs_np = final_probs.cpu().numpy().flatten()
        y_true = node_y.flatten()
        y_pred = (probs_np > 0.5).astype(int)

        gnn_acc = accuracy_score(y_true, y_pred)
        gnn_prec = precision_score(y_true, y_pred, zero_division=1)
        gnn_rec = recall_score(y_true, y_pred, zero_division=1)
        gnn_f1 = f1_score(y_true, y_pred, zero_division=1)
        gnn_auc = roc_auc_score(y_true, probs_np) if len(np.unique(y_true)) > 1 else 1.0

    print(f"\n  -> GNN Empirical Metrics: Accuracy={gnn_acc:.4f}, Precision={gnn_prec:.4f}, Recall={gnn_rec:.4f}, F1={gnn_f1:.4f}, ROC-AUC={gnn_auc:.4f}")

    # NOTE: these metrics are measured on the SYNTHETIC training set - they reflect how well
    # the model fits the synthetic data generator, not real network performance.

    # 3. Train Diffusion-TS Model
    print("\n[STEP 3] Training PyTorch Diffusion-TS Denoising Model (20 Epochs)...")
    diff_model = DiffusionTSModel(timesteps=50, in_channels=4, seq_len=20, cond_dim=4).to(device)
    diff_optimizer = optim.Adam(diff_model.parameters(), lr=0.002)

    diff_losses = []
    for epoch in range(1, 21):
        diff_model.train()
        diff_optimizer.zero_grad()
        loss = diff_model.compute_loss(xt_target_t, cond_t)
        loss.backward()
        diff_optimizer.step()
        diff_losses.append(loss.item())
        if epoch % 5 == 0 or epoch == 1:
            print(f"  Epoch {epoch:02d}/20 | Diffusion Loss: {loss.item():.4f}")

    # Save Diffusion weights
    torch.save(diff_model.state_dict(), "diffusion_ts_model.pt")
    print("  -> Saved Diffusion-TS weights to 'diffusion_ts_model.pt'")

    # 4. Generate Counterfactuals & Compute FID Score
    print("\n[STEP 4] Generating Counterfactual Telemetry & Computing FID Score...")
    diff_model.eval()
    with torch.no_grad():
        synth_samples_t = diff_model.sample_counterfactual(x0_t[:200], cond_t[:200])
        synth_samples_np = synth_samples_t.cpu().numpy()
        real_target_np = xt_target_t[:200].cpu().numpy()

        fid_score = calculate_time_series_fid(real_target_np, synth_samples_np)
        mse_score = float(np.mean((real_target_np - synth_samples_np) ** 2))
        mae_score = float(np.mean(np.abs(real_target_np - synth_samples_np)))

    print(f"  -> Generated Time-Series Quality Metrics:")
    print(f"     - FID Score (Fréchet Inception Distance): {fid_score:.2f} (Target < 50.0)")
    print(f"     - MSE (Mean Squared Error): {mse_score:.4f}")
    print(f"     - MAE (Mean Absolute Error): {mae_score:.4f}")

    # 5. Benchmark Compute Latency (IN-PROCESS ONLY)
    print("\n[STEP 5] Benchmarking Multi-Agent COMPUTE latency (100 Runs)...")
    from agentic_remediator import MultiAgentRemediator
    remediator = MultiAgentRemediator()
    sample_telemetry = {"osnr_db": 15.5, "temperature_celsius": 76.0, "laser_bias_ma": 68.0, "packet_loss_percent": 3.2}

    latencies_ms = []
    for _ in range(100):
        t0 = time.time()
        _ = remediator.process_anomaly_and_remediate(sample_telemetry)
        latencies_ms.append((time.time() - t0) * 1000.0)

    avg_latency_ms = float(np.mean(latencies_ms))
    std_latency_ms = float(np.std(latencies_ms))
    p99_latency_ms = float(np.percentile(latencies_ms, 99))

    print(f"  -> Compute latency (100 runs): Mean={avg_latency_ms:.2f}ms (+-{std_latency_ms:.2f}ms), P99={p99_latency_ms:.2f}ms")
    print("  -> IMPORTANT: This is in-process compute time ONLY. It excludes LLM round-trip and")
    print("     any real device deployment over the network. It is NOT a full end-to-end MTTR claim.")
    # NOTE: No fabricated OPEX / truck-roll savings. Those were hardcoded constants in an earlier
    # revision and have been removed because they were not measured outcomes.

    # 6. Generate Empirical Benchmark Plots
    print("\n[STEP 6] Generating High-Resolution Empirical Benchmark Figures...")
    generate_benchmark_plots(gnn_losses, diff_losses, fid_score, gnn_acc, gnn_auc, avg_latency_ms, real_target_np, synth_samples_np)

    print("\n" + "=" * 75)
    print("  ALL NEURAL MODELS TRAINED, WEIGHTS SAVED, AND EMPIRICAL PLOTS EXPORTED!")
    print("=" * 75)

def generate_benchmark_plots(gnn_losses, diff_losses, fid_score, gnn_acc, gnn_auc, avg_latency_ms, real_ts, synth_ts):
    os.makedirs("benchmark_figures", exist_ok=True)

    # -------------------------------------------------------------
    # Figure 1: Empirical Metrics Dashboard
    # -------------------------------------------------------------
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 8))

    # Loss Curves
    epochs = range(1, len(gnn_losses) + 1)
    ax1.plot(epochs, gnn_losses, color='#7EE787', marker='o', label='GNN Loss')
    ax1.plot(epochs, diff_losses, color='#D2A8FF', marker='s', label='Diffusion Loss')
    ax1.set_title('Neural Model Training Loss Curves', color='white', fontsize=12, fontweight='bold')
    ax1.set_xlabel('Epochs')
    ax1.set_ylabel('Loss')
    ax1.grid(True, linestyle='--', alpha=0.3)
    ax1.legend()

    # FID Score vs Target Threshold
    categories = ['Target Max FID', 'CTG-CPM Achieved FID']
    values = [50.0, fid_score]
    colors = ['#FF7B72', '#58A6FF']
    bars = ax2.bar(categories, values, color=colors, width=0.5)
    ax2.set_title('Time-Series Counterfactual FID Score', color='white', fontsize=12, fontweight='bold')
    ax2.set_ylabel('FID Score (Lower is Better)')
    ax2.grid(True, linestyle='--', alpha=0.3)
    for bar in bars:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, yval + 1.5, f"{yval:.2f}", ha='center', color='white', fontweight='bold')

    # Accuracy & ROC-AUC Bar Chart (measured on synthetic dataset)
    metrics_names = ['GNN Accuracy', 'GNN ROC-AUC']
    metrics_vals = [gnn_acc * 100, gnn_auc * 100]
    ax3.barh(metrics_names, metrics_vals, color=['#79C0FF', '#7EE787', '#FFA657'])
    ax3.set_title('Anomaly Detection & Validation Metrics (%)', color='white', fontsize=12, fontweight='bold')
    ax3.set_xlim(0, 115)
    ax3.grid(True, linestyle='--', alpha=0.3)
    for i, v in enumerate(metrics_vals):
        ax3.text(v + 1.5, i, f"{v:.1f}%", va='center', color='white', fontweight='bold')

    # Latency Breakdown (representative proportions, not measured per-component)
    components = ['GNN Ingest', 'Diffusion Gen', 'Game Theory', 'Script Gen']
    times = [0.15, 0.45, 0.25, 0.15]
    ax4.pie(times, labels=components, autopct='%1.1f%%', colors=['#58A6FF', '#D2A8FF', '#FFA657', '#7EE787'],
            textprops={'color': 'white', 'fontweight': 'bold'})
    ax4.set_title(f'Illustrative Compute Latency Split (Mean: {avg_latency_ms:.2f}ms)', color='white', fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.savefig('benchmark_figures/empirical_benchmark_metrics.png', dpi=300)
    plt.close()
    print("  -> Saved plot: 'benchmark_figures/empirical_benchmark_metrics.png'")

    # -------------------------------------------------------------
    # Figure 2: Counterfactual Time-Series Trajectory Comparison
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 5))
    steps = range(1, 21)
    
    # Plot real target trajectory vs generated counterfactual
    ax.plot(steps, real_ts[0, :, 0], color='#58A6FF', linewidth=2.5, label='Ground Truth OSNR Trajectory (dB)')
    ax.plot(steps, synth_ts[0, :, 0], color='#7EE787', linestyle='--', linewidth=2.5, label='Diffusion-TS Counterfactual OSNR (dB)')
    ax.axhline(y=18.0, color='#FF7B72', linestyle=':', linewidth=2, label='18.0 dB Anomaly Safety Threshold')
    
    ax.set_title('Real vs Diffusion-TS Synthetic Counterfactual OSNR Trajectory', color='white', fontsize=14, fontweight='bold')
    ax.set_xlabel('Time Horizon Steps')
    ax.set_ylabel('Optical Signal-to-Noise Ratio (OSNR dB)')
    ax.grid(True, linestyle='--', alpha=0.3)
    ax.legend(loc='lower right')

    plt.tight_layout()
    plt.savefig('benchmark_figures/counterfactual_diffusion_curves.png', dpi=300)
    plt.close()
    print("  -> Saved plot: 'benchmark_figures/counterfactual_diffusion_curves.png'")

    # -------------------------------------------------------------
    # Figure 3: Traditional vs CTG-CPM decision-compute comparison
    # NOTE: 'CTG-CPM value' is in-process decision compute only (no LLM, no deployment).
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 5))
    mttr_labels = ['Traditional Manual Repair', 'Rule-Based Automation', 'CTG-CPM Decision Compute*']
    mttr_values = [14400.0, 300.0, avg_latency_ms / 1000.0]  # 4 hours vs 5 min vs decision-compute seconds
    colors = ['#FF7B72', '#FFA657', '#7EE787']

    bars = ax.bar(mttr_labels, mttr_values, color=colors, width=0.45)
    ax.set_yscale('log')
    ax.set_title('Time-to-Repair: Manual vs Automation vs Decision-Compute (Log Scale)', color='white', fontsize=14, fontweight='bold')
    ax.set_ylabel('Seconds (Log Scale)')
    ax.grid(True, which="both", linestyle='--', alpha=0.3)

    for bar, val in zip(bars, mttr_values):
        if val >= 60:
            text_str = f"{val/3600:.1f} Hours" if val >= 3600 else f"{val/60:.1f} Mins"
        else:
            text_str = f"{val:.3f} Seconds"
        ax.text(bar.get_x() + bar.get_width()/2, val * 1.5, text_str, ha='center', color='white', fontweight='bold')

    ax.text(0.5, 1.03,
            "*CTG-CPM bar = in-process decision compute only. Excludes LLM round-trip and device deployment time.",
            transform=ax.transAxes, ha='center', va='bottom', color='white', fontsize=8)
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig('benchmark_figures/mttr_comparison_bar.png', dpi=300)
    plt.close()
    print("  -> Saved plot: 'benchmark_figures/mttr_comparison_bar.png'")

if __name__ == "__main__":
    train_and_evaluate_all()
