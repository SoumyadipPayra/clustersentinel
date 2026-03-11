"""SQLAlchemy ORM models."""

from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import String, Float, Integer, Boolean, DateTime, Text, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class MetricRecord(Base):
    __tablename__ = "metric_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    cluster_id: Mapped[str] = mapped_column(String, index=True)
    node_id: Mapped[str] = mapped_column(String, index=True)
    cpu_usage_pct: Mapped[float] = mapped_column(Float)
    memory_usage_pct: Mapped[float] = mapped_column(Float)
    storage_read_iops: Mapped[float] = mapped_column(Float)
    storage_write_iops: Mapped[float] = mapped_column(Float)
    storage_read_latency_ms: Mapped[float] = mapped_column(Float)
    storage_write_latency_ms: Mapped[float] = mapped_column(Float)
    network_rx_mbps: Mapped[float] = mapped_column(Float)
    network_tx_mbps: Mapped[float] = mapped_column(Float)
    controller_vm_cpu_pct: Mapped[float] = mapped_column(Float)
    controller_vm_mem_pct: Mapped[float] = mapped_column(Float)
    disk_throughput_mbps: Mapped[float] = mapped_column(Float)
    active_vms: Mapped[int] = mapped_column(Integer)


class AnomalyEventRecord(Base):
    __tablename__ = "anomaly_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    cluster_id: Mapped[str] = mapped_column(String, index=True)
    node_id: Mapped[str] = mapped_column(String, index=True)
    affected_metrics: Mapped[str] = mapped_column(Text)  # JSON list
    severity: Mapped[str] = mapped_column(String)
    prophet_score: Mapped[float] = mapped_column(Float, default=0.0)
    isolation_score: Mapped[float] = mapped_column(Float, default=0.0)
    lstm_score: Mapped[float] = mapped_column(Float, default=0.0)
    ensemble_score: Mapped[float] = mapped_column(Float)
    description: Mapped[str] = mapped_column(Text, default="")


class RCAReportRecord(Base):
    __tablename__ = "rca_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    anomaly_event_id: Mapped[str] = mapped_column(String, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    root_cause: Mapped[str] = mapped_column(Text)
    causal_chain: Mapped[str] = mapped_column(Text)
    blast_radius: Mapped[str] = mapped_column(Text)
    remediation_steps: Mapped[str] = mapped_column(Text)  # JSON list
    time_to_resolution_estimate: Mapped[str] = mapped_column(String)
    confidence_score: Mapped[float] = mapped_column(Float)
    raw_llm_output: Mapped[str] = mapped_column(Text, default="")


class FeedbackRecordORM(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    rca_report_id: Mapped[str] = mapped_column(String, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    helpful: Mapped[bool] = mapped_column(Boolean)
    comment: Mapped[str] = mapped_column(Text, default="")
