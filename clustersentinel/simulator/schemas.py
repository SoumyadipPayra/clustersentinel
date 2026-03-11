"""Pydantic models for all data contracts in ClusterSentinel."""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class NodeMetrics(BaseModel):
    """Per-node telemetry payload emitted every METRIC_INTERVAL_SECONDS."""

    timestamp: datetime
    cluster_id: str
    node_id: str
    cpu_usage_pct: float = Field(ge=0, le=100)
    memory_usage_pct: float = Field(ge=0, le=100)
    storage_read_iops: float = Field(ge=0)
    storage_write_iops: float = Field(ge=0)
    storage_read_latency_ms: float = Field(ge=0)
    storage_write_latency_ms: float = Field(ge=0)
    network_rx_mbps: float = Field(ge=0)
    network_tx_mbps: float = Field(ge=0)
    controller_vm_cpu_pct: float = Field(ge=0, le=100)
    controller_vm_mem_pct: float = Field(ge=0, le=100)
    disk_throughput_mbps: float = Field(ge=0)
    active_vms: int = Field(ge=0)


class ClusterMetrics(BaseModel):
    """Cluster-level aggregates computed from all NodeMetrics in a tick."""

    timestamp: datetime
    cluster_id: str
    total_cpu_usage_pct: float
    total_memory_usage_pct: float
    storage_utilization_pct: float
    avg_read_latency_ms: float
    avg_write_latency_ms: float
    degraded_nodes: int
    replication_lag_ms: float


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AnomalyEvent(BaseModel):
    """Emitted by the EnsembleDetector when the fused score exceeds threshold."""

    id: Optional[str] = None
    timestamp: datetime
    node_id: str
    cluster_id: str
    affected_metrics: list[str]
    severity: Severity
    prophet_score: float = 0.0
    isolation_score: float = 0.0
    lstm_score: float = 0.0
    ensemble_score: float
    description: str = ""


class RCAReport(BaseModel):
    """Root cause analysis report produced by the LangGraph agent."""

    id: Optional[str] = None
    anomaly_event_id: str
    timestamp: datetime
    root_cause: str
    causal_chain: str
    blast_radius: str
    remediation_steps: list[str]
    time_to_resolution_estimate: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    raw_llm_output: str = ""


class FeedbackRecord(BaseModel):
    """User feedback on an RCA report."""

    id: Optional[str] = None
    rca_report_id: str
    timestamp: datetime
    helpful: bool
    comment: Optional[str] = None


class AnomalyScore(BaseModel):
    """Intermediate score from a single detector."""

    metric: str
    node_id: str
    score: float
    expected_range: Optional[tuple[float, float]] = None
    actual_value: float
