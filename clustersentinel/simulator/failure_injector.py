"""Failure scenario definitions and metric perturbation logic.

Each FailureMode has an inject() method that returns a dict of additive
metric deltas for one or more nodes. Multiple failures can be active
simultaneously (deltas are summed in cluster.py).
"""

from __future__ import annotations
import numpy as np
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field


class FailureMode(str, Enum):
    NODE_DEGRADATION    = "NODE_DEGRADATION"
    NOISY_NEIGHBOR      = "NOISY_NEIGHBOR"
    STORAGE_REBALANCE   = "STORAGE_REBALANCE"
    MEMORY_PRESSURE     = "MEMORY_PRESSURE"
    NETWORK_SATURATION  = "NETWORK_SATURATION"
    DISK_PRE_FAILURE    = "DISK_PRE_FAILURE"
    CASCADING_FAILURE   = "CASCADING_FAILURE"


# Duration bounds (minutes) per failure mode
_DURATIONS: dict[FailureMode, tuple[int, int]] = {
    FailureMode.NODE_DEGRADATION:   (15, 45),
    FailureMode.NOISY_NEIGHBOR:     (5,  20),
    FailureMode.STORAGE_REBALANCE:  (30, 90),
    FailureMode.MEMORY_PRESSURE:    (20, 60),
    FailureMode.NETWORK_SATURATION: (10, 30),
    FailureMode.DISK_PRE_FAILURE:   (60, 180),
    FailureMode.CASCADING_FAILURE:  (45, 120),
}


@dataclass
class ActiveFailure:
    mode: FailureMode
    target_nodes: list[str]
    start_time: datetime
    end_time: datetime
    rng: np.random.Generator = field(repr=False)

    def is_active(self, ts: datetime) -> bool:
        return self.start_time <= ts <= self.end_time

    def elapsed_fraction(self, ts: datetime) -> float:
        """0.0 at start → 1.0 at end."""
        total = (self.end_time - self.start_time).total_seconds()
        elapsed = (ts - self.start_time).total_seconds()
        return min(max(elapsed / total, 0.0), 1.0)

    def inject(self, ts: datetime, node_id: str) -> dict[str, float]:
        """Return additive metric deltas for node_id at time ts."""
        if not self.is_active(ts) or node_id not in self.target_nodes:
            return {}
        f = self.elapsed_fraction(ts)
        return _INJECTORS[self.mode](f, node_id, self.target_nodes, self.rng)


def _node_degradation(f: float, node_id: str, nodes: list[str], rng: np.random.Generator) -> dict[str, float]:
    """CVM CPU spikes, write IOPS collapse, write latency rises progressively."""
    return {
        "controller_vm_cpu_pct":    30.0 * f + rng.normal(0, 3),
        "storage_write_iops":      -1200 * f + rng.normal(0, 100),
        "storage_write_latency_ms":  50.0 * f + rng.normal(0, 5),
        "cpu_usage_pct":             20.0 * f + rng.normal(0, 4),
    }


def _noisy_neighbor(f: float, node_id: str, nodes: list[str], rng: np.random.Generator) -> dict[str, float]:
    """One VM hogs CPU/IOPS on node-02, starving co-located VMs."""
    return {
        "cpu_usage_pct":          40.0 + rng.normal(0, 5),
        "storage_read_iops":      2000  + rng.normal(0, 200),
        "active_vms":            -3,
    }


def _storage_rebalance(f: float, node_id: str, nodes: list[str], rng: np.random.Generator) -> dict[str, float]:
    """High disk throughput + latency spikes during rebalance."""
    peak = np.sin(f * np.pi)  # bell curve over duration
    return {
        "disk_throughput_mbps":     300 * peak + rng.normal(0, 30),
        "storage_write_latency_ms":  30 * peak + rng.normal(0, 3),
        "network_rx_mbps":          200 * peak + rng.normal(0, 20),
        "network_tx_mbps":          200 * peak + rng.normal(0, 20),
        "replication_lag_ms":       80  * peak + rng.normal(0, 8),  # type: ignore[dict-item]
    }


def _memory_pressure(f: float, node_id: str, nodes: list[str], rng: np.random.Generator) -> dict[str, float]:
    """Gradual memory exhaustion on two nodes."""
    return {
        "memory_usage_pct":       35.0 * f + rng.normal(0, 2),
        "controller_vm_mem_pct":  40.0 * f + rng.normal(0, 3),
    }


def _network_saturation(f: float, node_id: str, nodes: list[str], rng: np.random.Generator) -> dict[str, float]:
    """East-west traffic spike saturating RX/TX."""
    burst = 1.0 if f < 0.8 else (1.0 - f) * 5  # abrupt start, gradual end
    return {
        "network_rx_mbps":        600 * burst + rng.normal(0, 50),
        "network_tx_mbps":        550 * burst + rng.normal(0, 50),
        "replication_lag_ms":     120 * burst + rng.normal(0, 10),  # type: ignore[dict-item]
    }


def _disk_pre_failure(f: float, node_id: str, nodes: list[str], rng: np.random.Generator) -> dict[str, float]:
    """Slow creeping latency rise + IOPS drop before disk failure."""
    return {
        "storage_read_latency_ms":  20.0 * f + rng.normal(0, 2),
        "storage_write_latency_ms": 25.0 * f + rng.normal(0, 3),
        "storage_read_iops":       -1500 * f + rng.normal(0, 150),
        "storage_write_iops":      -900  * f + rng.normal(0, 90),
    }


def _cascading_failure(f: float, node_id: str, nodes: list[str], rng: np.random.Generator) -> dict[str, float]:
    """NODE_DEGRADATION on first node, STORAGE_REBALANCE spreading to others."""
    primary = nodes[0]
    if node_id == primary:
        return _node_degradation(f, node_id, nodes, rng)
    # secondary nodes experience rebalance-style load
    peak = np.sin(min(f * 1.5, 1.0) * np.pi)
    return {
        "disk_throughput_mbps":     200 * peak + rng.normal(0, 20),
        "storage_write_latency_ms":  20 * peak + rng.normal(0, 2),
        "replication_lag_ms":        60 * peak + rng.normal(0, 6),  # type: ignore[dict-item]
        "controller_vm_cpu_pct":     15 * peak + rng.normal(0, 2),
    }


_INJECTORS = {
    FailureMode.NODE_DEGRADATION:   _node_degradation,
    FailureMode.NOISY_NEIGHBOR:     _noisy_neighbor,
    FailureMode.STORAGE_REBALANCE:  _storage_rebalance,
    FailureMode.MEMORY_PRESSURE:    _memory_pressure,
    FailureMode.NETWORK_SATURATION: _network_saturation,
    FailureMode.DISK_PRE_FAILURE:   _disk_pre_failure,
    FailureMode.CASCADING_FAILURE:  _cascading_failure,
}


class FailureInjector:
    """Manages scheduled and on-demand failure injection."""

    def __init__(self, rng: np.random.Generator) -> None:
        self.rng = rng
        self.active: list[ActiveFailure] = []

    def schedule(
        self,
        mode: FailureMode,
        target_nodes: list[str],
        start_time: datetime,
        duration_minutes: int | None = None,
    ) -> ActiveFailure:
        lo, hi = _DURATIONS[mode]
        duration = duration_minutes or int(self.rng.integers(lo, hi + 1))
        end_time = start_time + timedelta(minutes=duration)
        failure = ActiveFailure(
            mode=mode,
            target_nodes=target_nodes,
            start_time=start_time,
            end_time=end_time,
            rng=self.rng,
        )
        self.active.append(failure)
        return failure

    def get_overrides(self, ts: datetime, node_id: str) -> dict[str, float]:
        """Accumulate deltas from all currently active failures for a node."""
        combined: dict[str, float] = {}
        for failure in self.active:
            if failure.is_active(ts):
                for metric, delta in failure.inject(ts, node_id).items():
                    combined[metric] = combined.get(metric, 0.0) + delta
        return combined

    def purge_expired(self, ts: datetime) -> None:
        self.active = [f for f in self.active if f.is_active(ts)]
