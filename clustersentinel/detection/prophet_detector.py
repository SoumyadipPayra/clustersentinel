"""Prophet-based detector: per-metric seasonal baseline + band breach detection."""

from __future__ import annotations
import pickle
from pathlib import Path
import pandas as pd
from prophet import Prophet  # type: ignore[import-untyped]
from clustersentinel.simulator.schemas import AnomalyScore
from .base import DetectorBase

_METRICS = [
    "cpu_usage_pct", "memory_usage_pct",
    "storage_read_iops", "storage_write_iops",
    "storage_read_latency_ms", "storage_write_latency_ms",
    "network_rx_mbps", "network_tx_mbps",
    "controller_vm_cpu_pct", "controller_vm_mem_pct",
    "disk_throughput_mbps",
]


class ProphetDetector(DetectorBase):
    """Trains one Prophet model per (node_id, metric).

    Anomaly = actual value outside [yhat_lower, yhat_upper].
    Score = normalized distance from the nearest band edge.
    """

    def __init__(self) -> None:
        # models[node_id][metric] = fitted Prophet
        self.models: dict[str, dict[str, Prophet]] = {}

    def fit(self, df: pd.DataFrame) -> None:
        for node_id, node_df in df.groupby("node_id"):
            self.models[node_id] = {}  # type: ignore[index]
            for metric in _METRICS:
                if metric not in node_df.columns:
                    continue
                prophet_df = node_df[["timestamp", metric]].rename(
                    columns={"timestamp": "ds", metric: "y"}
                )
                m = Prophet(
                    daily_seasonality=True,
                    weekly_seasonality=False,
                    interval_width=0.95,
                    changepoint_prior_scale=0.05,
                )
                m.fit(prophet_df)
                self.models[node_id][metric] = m  # type: ignore[index]

    def detect(self, df: pd.DataFrame) -> list[AnomalyScore]:
        scores: list[AnomalyScore] = []
        for node_id, node_df in df.groupby("node_id"):
            if node_id not in self.models:
                continue
            for metric, model in self.models[node_id].items():  # type: ignore[index]
                if metric not in node_df.columns:
                    continue
                future = node_df[["timestamp"]].rename(columns={"timestamp": "ds"})
                forecast = model.predict(future)
                for _, row in forecast.iterrows():
                    ts_mask = node_df["timestamp"] == row["ds"]
                    if not ts_mask.any():
                        continue
                    actual = float(node_df.loc[ts_mask, metric].iloc[0])
                    lo, hi = row["yhat_lower"], row["yhat_upper"]
                    if actual < lo or actual > hi:
                        band_width = max(hi - lo, 1e-6)
                        score = min(abs(actual - row["yhat"]) / band_width, 1.0)
                        scores.append(AnomalyScore(
                            metric=metric,
                            node_id=str(node_id),
                            score=score,
                            expected_range=(lo, hi),
                            actual_value=actual,
                        ))
        return scores

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self.models, f)

    def load(self, path: str) -> None:
        with open(path, "rb") as f:
            self.models = pickle.load(f)
