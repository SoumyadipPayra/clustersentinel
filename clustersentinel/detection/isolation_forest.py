"""Isolation Forest detector: multi-metric outlier scoring per node."""

from __future__ import annotations
import pickle
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]
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


class IsolationForestDetector(DetectorBase):
    """One IsolationForest per node trained on clean baseline feature vectors."""

    def __init__(self, contamination: float = 0.05) -> None:
        self.contamination = contamination
        self.models: dict[str, IsolationForest] = {}
        self.scalers: dict[str, StandardScaler] = {}

    def fit(self, df: pd.DataFrame) -> None:
        for node_id, node_df in df.groupby("node_id"):
            features = node_df[[c for c in _FEATURE_COLS if c in node_df.columns]].fillna(0)
            scaler = StandardScaler()
            X = scaler.fit_transform(features)
            model = IsolationForest(
                contamination=self.contamination,
                random_state=42,
                n_estimators=100,
            )
            model.fit(X)
            self.models[str(node_id)] = model
            self.scalers[str(node_id)] = scaler

    def detect(self, df: pd.DataFrame) -> list[AnomalyScore]:
        scores: list[AnomalyScore] = []
        for node_id, node_df in df.groupby("node_id"):
            nid = str(node_id)
            if nid not in self.models:
                continue
            features = node_df[[c for c in _FEATURE_COLS if c in node_df.columns]].fillna(0)
            X = self.scalers[nid].transform(features)
            # decision_function: more negative = more anomalous
            raw_scores = self.models[nid].decision_function(X)
            # Map to [0, 1] where 1 = most anomalous
            normalized = np.clip((-raw_scores + 0.5), 0, 1)

            for i, score_val in enumerate(normalized):
                if score_val > 0.5:
                    # Find the metric with greatest deviation
                    z_scores = np.abs(X[i])
                    top_metric_idx = int(np.argmax(z_scores))
                    feat_cols = [c for c in _FEATURE_COLS if c in node_df.columns]
                    metric_name = feat_cols[top_metric_idx]
                    actual = float(node_df.iloc[i][metric_name])
                    scores.append(AnomalyScore(
                        metric=metric_name,
                        node_id=nid,
                        score=float(score_val),
                        actual_value=actual,
                    ))
        return scores

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({"models": self.models, "scalers": self.scalers}, f)

    def load(self, path: str) -> None:
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.models = data["models"]
        self.scalers = data["scalers"]
