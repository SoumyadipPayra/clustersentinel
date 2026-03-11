"""Per-node metric generator with realistic noise and diurnal patterns.

Baseline load is higher during 09:00–18:00 (business hours). Gaussian noise
is added on top; all values are clamped to valid ranges.
"""

from __future__ import annotations
import numpy as np
from datetime import datetime
from .schemas import NodeMetrics


# Baseline ranges: (day_mean, night_mean, std)
_BASELINES: dict[str, tuple[float, float, float]] = {
    "cpu_usage_pct":             (45.0,  25.0,  8.0),
    "memory_usage_pct":          (60.0,  50.0,  6.0),
    "storage_read_iops":         (3500,  1200, 400),
    "storage_write_iops":        (1800,   600, 200),
    "storage_read_latency_ms":   (2.5,    1.5,  0.4),
    "storage_write_latency_ms":  (3.0,    2.0,  0.5),
    "network_rx_mbps":           (400,    150,  60),
    "network_tx_mbps":           (350,    120,  55),
    "controller_vm_cpu_pct":     (20.0,  12.0,  4.0),
    "controller_vm_mem_pct":     (35.0,  30.0,  3.0),
    "disk_throughput_mbps":      (250,    100,  30),
    "active_vms":                (18,      8,    3),
}

_CLAMPS: dict[str, tuple[float, float]] = {
    "cpu_usage_pct":             (0, 100),
    "memory_usage_pct":          (0, 100),
    "storage_read_iops":         (0, 50_000),
    "storage_write_iops":        (0, 50_000),
    "storage_read_latency_ms":   (0.1, 2000),
    "storage_write_latency_ms":  (0.1, 2000),
    "network_rx_mbps":           (0, 10_000),
    "network_tx_mbps":           (0, 10_000),
    "controller_vm_cpu_pct":     (0, 100),
    "controller_vm_mem_pct":     (0, 100),
    "disk_throughput_mbps":      (0, 5000),
    "active_vms":                (0, 200),
}


def _is_business_hours(ts: datetime) -> bool:
    return 9 <= ts.hour < 18


def generate_node_metrics(
    ts: datetime,
    cluster_id: str,
    node_id: str,
    rng: np.random.Generator,
    overrides: dict[str, float] | None = None,
) -> NodeMetrics:
    """Generate a single NodeMetrics sample for a node at the given timestamp.

    Args:
        ts: Current simulation timestamp.
        cluster_id: Cluster identifier.
        node_id: Node identifier.
        rng: NumPy random generator (caller-owned for reproducibility).
        overrides: Metric overrides injected by FailureInjector (additive delta).
    """
    business = _is_business_hours(ts)
    overrides = overrides or {}
    values: dict[str, float] = {}

    for metric, (day_mean, night_mean, std) in _BASELINES.items():
        mean = day_mean if business else night_mean
        raw = rng.normal(mean, std)
        delta = overrides.get(metric, 0.0)
        lo, hi = _CLAMPS[metric]
        values[metric] = float(np.clip(raw + delta, lo, hi))

    return NodeMetrics(
        timestamp=ts,
        cluster_id=cluster_id,
        node_id=node_id,
        active_vms=int(values["active_vms"]),
        **{k: v for k, v in values.items() if k != "active_vms"},
    )
