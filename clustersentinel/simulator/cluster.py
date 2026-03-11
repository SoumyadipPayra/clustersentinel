"""Multi-node cluster state machine.

Orchestrates N nodes, calls telemetry.py per node each tick, applies
failure injector overrides, and computes cluster-level aggregates.
"""

from __future__ import annotations
import uuid
import numpy as np
from datetime import datetime, timedelta
from typing import Iterator
from .schemas import NodeMetrics, ClusterMetrics
from .telemetry import generate_node_metrics
from .failure_injector import FailureInjector, FailureMode


_NODE_HEALTH_THRESHOLD = 70.0  # cpu or mem above this = degraded


class ClusterSimulator:
    """Simulates a multi-node HCI cluster, emitting metrics each tick."""

    def __init__(
        self,
        num_nodes: int = 4,
        cluster_id: str | None = None,
        interval_seconds: int = 30,
        seed: int | None = None,
    ) -> None:
        self.cluster_id = cluster_id or f"cluster-{uuid.uuid4().hex[:8]}"
        self.node_ids = [f"node-{i:02d}" for i in range(1, num_nodes + 1)]
        self.interval_seconds = interval_seconds
        self.rng = np.random.default_rng(seed)
        self.injector = FailureInjector(rng=self.rng)

    def inject_failure(
        self,
        mode: FailureMode,
        start_time: datetime,
        target_nodes: list[str] | None = None,
        duration_minutes: int | None = None,
    ) -> None:
        """Schedule a failure to start at start_time."""
        nodes = target_nodes or self.node_ids[:2]
        self.injector.schedule(mode, nodes, start_time, duration_minutes)

    def tick(self, ts: datetime) -> tuple[list[NodeMetrics], ClusterMetrics]:
        """Generate one tick of metrics for all nodes."""
        self.injector.purge_expired(ts)

        node_metrics: list[NodeMetrics] = []
        for node_id in self.node_ids:
            overrides = self.injector.get_overrides(ts, node_id)
            nm = generate_node_metrics(ts, self.cluster_id, node_id, self.rng, overrides)
            node_metrics.append(nm)

        cluster = self._aggregate(ts, node_metrics)
        return node_metrics, cluster

    def run(
        self,
        start_time: datetime,
        duration_hours: float,
    ) -> Iterator[tuple[list[NodeMetrics], ClusterMetrics]]:
        """Yield (node_metrics_list, cluster_metrics) for each simulation tick."""
        ts = start_time
        end = start_time + timedelta(hours=duration_hours)
        step = timedelta(seconds=self.interval_seconds)
        while ts <= end:
            yield self.tick(ts)
            ts += step

    def _aggregate(self, ts: datetime, nodes: list[NodeMetrics]) -> ClusterMetrics:
        n = len(nodes)
        degraded = sum(
            1 for nm in nodes
            if nm.cpu_usage_pct > _NODE_HEALTH_THRESHOLD
            or nm.memory_usage_pct > _NODE_HEALTH_THRESHOLD
        )
        # Replication lag is cluster-level; estimate from node variance in write latency
        write_latencies = [nm.storage_write_latency_ms for nm in nodes]
        replication_lag = float(np.std(write_latencies) * 10)

        return ClusterMetrics(
            timestamp=ts,
            cluster_id=self.cluster_id,
            total_cpu_usage_pct=sum(nm.cpu_usage_pct for nm in nodes) / n,
            total_memory_usage_pct=sum(nm.memory_usage_pct for nm in nodes) / n,
            storage_utilization_pct=min(
                sum(nm.storage_write_iops + nm.storage_read_iops for nm in nodes) / (n * 10000) * 100,
                100.0,
            ),
            avg_read_latency_ms=sum(nm.storage_read_latency_ms for nm in nodes) / n,
            avg_write_latency_ms=sum(nm.storage_write_latency_ms for nm in nodes) / n,
            degraded_nodes=degraded,
            replication_lag_ms=replication_lag,
        )
