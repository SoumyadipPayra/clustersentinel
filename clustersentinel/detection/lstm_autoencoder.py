"""LSTM Autoencoder detector: temporal anomaly detection via reconstruction error.

Architecture: LSTM encoder → bottleneck → LSTM decoder.
Anomaly = reconstruction error above 95th-percentile threshold from training.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from clustersentinel.simulator.schemas import AnomalyScore
from .base import DetectorBase

_FEATURE_COLS = [
    "cpu_usage_pct", "memory_usage_pct",
    "storage_read_iops", "storage_write_iops",
    "storage_read_latency_ms", "storage_write_latency_ms",
    "network_rx_mbps", "network_tx_mbps",
    "controller_vm_cpu_pct", "controller_vm_mem_pct",
    "disk_throughput_mbps",
]

WINDOW = 60  # timesteps per sequence


class _LSTMAutoencoder(nn.Module):
    def __init__(self, input_size: int, hidden_size: int = 64, num_layers: int = 2) -> None:
        super().__init__()
        self.encoder = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.bottleneck = nn.Linear(hidden_size, hidden_size // 2)
        self.expand = nn.Linear(hidden_size // 2, hidden_size)
        self.decoder = nn.LSTM(hidden_size, input_size, num_layers, batch_first=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        enc_out, _ = self.encoder(x)
        bottleneck = torch.relu(self.bottleneck(enc_out))
        expanded = torch.relu(self.expand(bottleneck))
        dec_out, _ = self.decoder(expanded)
        return dec_out


class LSTMAutoencoderDetector(DetectorBase):
    """Per-node LSTM autoencoder; threshold = 95th pct of training reconstruction errors."""

    def __init__(self, epochs: int = 20, lr: float = 1e-3) -> None:
        self.epochs = epochs
        self.lr = lr
        self.models: dict[str, _LSTMAutoencoder] = {}
        self.thresholds: dict[str, float] = {}
        self.feature_means: dict[str, np.ndarray] = {}
        self.feature_stds: dict[str, np.ndarray] = {}
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def _normalize(self, node_id: str, arr: np.ndarray, fit: bool = False) -> np.ndarray:
        if fit:
            self.feature_means[node_id] = arr.mean(axis=0)
            self.feature_stds[node_id] = arr.std(axis=0) + 1e-8
        return (arr - self.feature_means[node_id]) / self.feature_stds[node_id]

    def _make_windows(self, arr: np.ndarray) -> np.ndarray:
        if len(arr) < WINDOW:
            return np.empty((0, WINDOW, arr.shape[1]))
        return np.stack([arr[i:i + WINDOW] for i in range(len(arr) - WINDOW + 1)])

    def fit(self, df: pd.DataFrame) -> None:
        for node_id, node_df in df.groupby("node_id"):
            nid = str(node_id)
            cols = [c for c in _FEATURE_COLS if c in node_df.columns]
            arr = node_df.sort_values("timestamp")[cols].fillna(0).values.astype(np.float32)
            arr = self._normalize(nid, arr, fit=True)
            windows = self._make_windows(arr)
            if len(windows) == 0:
                continue

            X = torch.tensor(windows, dtype=torch.float32).to(self.device)
            loader = DataLoader(TensorDataset(X), batch_size=32, shuffle=True)
            model = _LSTMAutoencoder(input_size=len(cols)).to(self.device)
            optimizer = torch.optim.Adam(model.parameters(), lr=self.lr)
            criterion = nn.MSELoss()

            model.train()
            for _ in range(self.epochs):
                for (batch,) in loader:
                    optimizer.zero_grad()
                    recon = model(batch)
                    loss = criterion(recon, batch)
                    loss.backward()
                    optimizer.step()

            # Compute threshold from training reconstruction errors
            model.eval()
            with torch.no_grad():
                recon = model(X)
                errors = ((X - recon) ** 2).mean(dim=(1, 2)).cpu().numpy()
            self.thresholds[nid] = float(np.percentile(errors, 95))
            self.models[nid] = model

    def detect(self, df: pd.DataFrame) -> list[AnomalyScore]:
        scores: list[AnomalyScore] = []
        for node_id, node_df in df.groupby("node_id"):
            nid = str(node_id)
            if nid not in self.models:
                continue
            cols = [c for c in _FEATURE_COLS if c in node_df.columns]
            arr = node_df.sort_values("timestamp")[cols].fillna(0).values.astype(np.float32)
            arr = self._normalize(nid, arr)
            windows = self._make_windows(arr)
            if len(windows) == 0:
                continue

            model = self.models[nid]
            model.eval()
            X = torch.tensor(windows, dtype=torch.float32).to(self.device)
            with torch.no_grad():
                recon = model(X)
                errors = ((X - recon) ** 2).mean(dim=(1, 2)).cpu().numpy()

            threshold = self.thresholds[nid]
            for i, err in enumerate(errors):
                if err > threshold:
                    norm_score = min(err / (threshold * 2 + 1e-8), 1.0)
                    # Find most anomalous feature in last window step
                    last_step = (X[i, -1] - recon[i, -1]).abs().cpu().numpy()
                    metric_name = cols[int(np.argmax(last_step))]
                    actual = float(node_df.iloc[i + WINDOW - 1][metric_name])
                    scores.append(AnomalyScore(
                        metric=metric_name,
                        node_id=nid,
                        score=float(norm_score),
                        actual_value=actual,
                    ))
        return scores

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            "models": {k: v.state_dict() for k, v in self.models.items()},
            "thresholds": self.thresholds,
            "feature_means": self.feature_means,
            "feature_stds": self.feature_stds,
        }, path)

    def load(self, path: str) -> None:
        data = torch.load(path, map_location=self.device)
        self.thresholds = data["thresholds"]
        self.feature_means = data["feature_means"]
        self.feature_stds = data["feature_stds"]
        for nid, state_dict in data["models"].items():
            n_features = len(self.feature_means[nid])
            model = _LSTMAutoencoder(input_size=n_features).to(self.device)
            model.load_state_dict(state_dict)
            self.models[nid] = model
