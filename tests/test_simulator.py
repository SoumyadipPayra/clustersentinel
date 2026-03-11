"""Tests for the simulator layer."""

from datetime import datetime
import numpy as np
import pytest
from clustersentinel.simulator.cluster import ClusterSimulator
from clustersentinel.simulator.failure_injector import FailureMode
from clustersentinel.simulator.schemas import NodeMetrics, ClusterMetrics


def test_cluster_tick_returns_correct_node_count():
    sim = ClusterSimulator(num_nodes=3, seed=0)
    ts = datetime(2024, 1, 1, 10, 0)
    node_metrics, cluster = sim.tick(ts)
    assert len(node_metrics) == 3
    assert isinstance(cluster, ClusterMetrics)


def test_node_metrics_values_in_range():
    sim = ClusterSimulator(num_nodes=2, seed=1)
    ts = datetime(2024, 1, 1, 14, 0)
    node_metrics, _ = sim.tick(ts)
    for nm in node_metrics:
        assert 0 <= nm.cpu_usage_pct <= 100
        assert 0 <= nm.memory_usage_pct <= 100
        assert nm.storage_read_iops >= 0
        assert nm.storage_write_latency_ms >= 0


def test_failure_injection_raises_affected_metrics():
    sim = ClusterSimulator(num_nodes=2, seed=42)
    inject_time = datetime(2024, 1, 1, 10, 0)
    sim.inject_failure(FailureMode.NODE_DEGRADATION, inject_time, target_nodes=["node-01"])

    # Baseline tick (before failure)
    baseline_metrics, _ = sim.tick(datetime(2024, 1, 1, 9, 0))
    baseline_cvm_cpu = next(m.controller_vm_cpu_pct for m in baseline_metrics if m.node_id == "node-01")

    # During failure
    failure_metrics, _ = sim.tick(datetime(2024, 1, 1, 10, 15))
    failure_cvm_cpu = next(m.controller_vm_cpu_pct for m in failure_metrics if m.node_id == "node-01")

    assert failure_cvm_cpu > baseline_cvm_cpu


def test_cluster_run_yields_expected_ticks():
    sim = ClusterSimulator(num_nodes=2, interval_seconds=300, seed=0)  # 5-min intervals
    start = datetime(2024, 1, 1, 0, 0)
    ticks = list(sim.run(start, duration_hours=1.0))
    # 60min / 5min = 12 intervals + 1 = 13 ticks
    assert len(ticks) == 13


def test_multiple_failures_accumulate():
    sim = ClusterSimulator(num_nodes=2, seed=0)
    inject_time = datetime(2024, 1, 1, 10, 0)
    sim.inject_failure(FailureMode.NODE_DEGRADATION, inject_time, target_nodes=["node-01"])
    sim.inject_failure(FailureMode.MEMORY_PRESSURE, inject_time, target_nodes=["node-01"])

    metrics, _ = sim.tick(datetime(2024, 1, 1, 10, 20))
    node01 = next(m for m in metrics if m.node_id == "node-01")
    # Both failures affect node-01 — memory should be significantly elevated
    assert node01.memory_usage_pct > 60
