"""
diffusion_ts_model.py
PyTorch Denoising Diffusion Probabilistic Model (Diffusion-TS) for Time-Series Counterfactual Telemetry
CTG-CPM Layer 3 Component
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Dict, Any, List

class SinusoidalPositionalEmbedding(nn.Module):
    """Sinusoidal Timestep Embeddings for Diffusion Step t"""
    def __init__(self, dim: int):
        super().__init__()
        self.dim = dim

    def forward(self, timesteps: torch.Tensor) -> torch.Tensor:
        device = timesteps.device
        half_dim = self.dim // 2
        embeddings = math.log(10000) / (half_dim - 1)
        embeddings = torch.exp(torch.arange(half_dim, device=device) * -embeddings)
        embeddings = timesteps[:, None].float() * embeddings[None, :]
        embeddings = torch.cat((embeddings.sin(), embeddings.cos()), dim=-1)
        return embeddings

class DenoisingUNet1D(nn.Module):
    """
    1D ResNet / UNet Denoising Network:
    Predicts noise ε_θ(x_t, t, c) added to time-series sequence x_t conditioned on:
    - Diffusion timestep t
    - Intervention conditioning vector c (one-hot)
    """
    def __init__(self, in_channels: int = 4, seq_len: int = 20, cond_dim: int = 4, hidden_dim: int = 64):
        super().__init__()
        self.time_mlp = nn.Sequential(
            SinusoidalPositionalEmbedding(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU()
        )
        self.cond_mlp = nn.Sequential(
            nn.Linear(cond_dim, hidden_dim),
            nn.GELU()
        )

        # 1D Convolutional Feature Extractor
        self.input_conv = nn.Conv1d(in_channels, hidden_dim, kernel_size=3, padding=1)
        
        self.res_block1 = nn.Sequential(
            nn.Conv1d(hidden_dim, hidden_dim, kernel_size=3, padding=1),
            nn.BatchNorm1d(hidden_dim),
            nn.GELU(),
            nn.Conv1d(hidden_dim, hidden_dim, kernel_size=3, padding=1),
            nn.BatchNorm1d(hidden_dim)
        )
        
        self.res_block2 = nn.Sequential(
            nn.Conv1d(hidden_dim, hidden_dim, kernel_size=3, padding=1),
            nn.BatchNorm1d(hidden_dim),
            nn.GELU(),
            nn.Conv1d(hidden_dim, hidden_dim, kernel_size=3, padding=1),
            nn.BatchNorm1d(hidden_dim)
        )

        self.out_conv = nn.Conv1d(hidden_dim, in_channels, kernel_size=3, padding=1)

    def forward(self, x: torch.Tensor, t: torch.Tensor, cond: torch.Tensor) -> torch.Tensor:
        # x shape: (B, seq_len, in_channels) -> transpose to (B, in_channels, seq_len)
        x = x.transpose(1, 2)
        
        t_emb = self.time_mlp(t)    # (B, hidden_dim)
        c_emb = self.cond_mlp(cond) # (B, hidden_dim)
        emb = (t_emb + c_emb).unsqueeze(-1) # (B, hidden_dim, 1)

        h = self.input_conv(x) + emb
        h = F.gelu(h + self.res_block1(h))
        h = F.gelu(h + self.res_block2(h))
        out = self.out_conv(h)

        # Re-transpose to (B, seq_len, in_channels)
        return out.transpose(1, 2)

class DiffusionTSModel(nn.Module):
    """
    DDPM Denoising Diffusion Model for Time-Series Generation:
    Forward process: x_t = sqrt(α_bar_t) * x_0 + sqrt(1 - α_bar_t) * ε
    Reverse process: Sampling x_0 step-by-step from noise
    """
    def __init__(self, timesteps: int = 100, in_channels: int = 4, seq_len: int = 20, cond_dim: int = 4):
        super().__init__()
        self.timesteps = timesteps
        self.seq_len = seq_len
        self.in_channels = in_channels

        self.denoise_net = DenoisingUNet1D(in_channels=in_channels, seq_len=seq_len, cond_dim=cond_dim)

        # Linear Beta Schedule
        beta_start = 0.0001
        beta_end = 0.02
        betas = torch.linspace(beta_start, beta_end, timesteps)
        alphas = 1.0 - betas
        alphas_cumprod = torch.cumprod(alphas, dim=0)

        self.register_buffer("betas", betas)
        self.register_buffer("alphas", alphas)
        self.register_buffer("alphas_cumprod", alphas_cumprod)
        self.register_buffer("sqrt_alphas_cumprod", torch.sqrt(alphas_cumprod))
        self.register_buffer("sqrt_one_minus_alphas_cumprod", torch.sqrt(1.0 - alphas_cumprod))

    def q_sample(self, x0: torch.Tensor, t: torch.Tensor, noise: torch.Tensor = None) -> torch.Tensor:
        """Forward diffusion process: Adds noise to x0 at timestep t"""
        if noise is None:
            noise = torch.randn_like(x0)
        
        sqrt_alpha_bar = self.sqrt_alphas_cumprod[t].view(-1, 1, 1)
        sqrt_one_minus_alpha_bar = self.sqrt_one_minus_alphas_cumprod[t].view(-1, 1, 1)
        
        return sqrt_alpha_bar * x0 + sqrt_one_minus_alpha_bar * noise

    def compute_loss(self, x0: torch.Tensor, cond: torch.Tensor) -> torch.Tensor:
        """Trains denoising network via MSE loss between true noise and predicted noise"""
        batch_size = x0.size(0)
        t = torch.randint(0, self.timesteps, (batch_size,), device=x0.device).long()
        noise = torch.randn_like(x0)

        xt = self.q_sample(x0, t, noise)
        predicted_noise = self.denoise_net(xt, t, cond)

        return F.mse_loss(predicted_noise, noise)

    @torch.no_grad()
    def sample_counterfactual(self, x0_baseline: torch.Tensor, cond: torch.Tensor) -> torch.Tensor:
        """
        Reverse sampling process: Generates synthetic counterfactual future starting from x0_baseline
        conditioned on intervention vector cond.
        """
        self.eval()
        device = x0_baseline.device
        batch_size = x0_baseline.size(0)

        # Start with noisy baseline representation
        xt = x0_baseline + torch.randn_like(x0_baseline) * 0.1

        for t_idx in reversed(range(0, self.timesteps)):
            t = torch.full((batch_size,), t_idx, device=device, dtype=torch.long)
            pred_noise = self.denoise_net(xt, t, cond)

            alpha = self.alphas[t_idx]
            alpha_bar = self.alphas_cumprod[t_idx]
            beta = self.betas[t_idx]

            if t_idx > 0:
                noise = torch.randn_like(xt)
            else:
                noise = 0.0

            xt = (1.0 / torch.sqrt(alpha)) * (xt - (beta / torch.sqrt(1.0 - alpha_bar)) * pred_noise) + torch.sqrt(beta) * noise

        return xt

if __name__ == "__main__":
    from dataset_generator import NetworkDatasetGenerator
    ds_gen = NetworkDatasetGenerator(num_samples=16)
    x0, cond, xt = ds_gen.generate_time_series_dataset()

    model = DiffusionTSModel(timesteps=50, in_channels=4, seq_len=20, cond_dim=4)
    loss = model.compute_loss(xt, cond)
    samples = model.sample_counterfactual(x0[:2], cond[:2])

    print("Diffusion Model Loss:", loss.item())
    print("Generated Counterfactual Samples Shape:", samples.shape)
