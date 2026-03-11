"""CRUD helpers for all ORM models."""

from __future__ import annotations
import json
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from clustersentinel.simulator.schemas import (
    NodeMetrics, AnomalyEvent, RCAReport, FeedbackRecord, Severity,
)
from .models import (
    MetricRecord, AnomalyEventRecord, RCAReportRecord, FeedbackRecordORM,
)


# ── Metrics ──────────────────────────────────────────────────────────────────

def save_node_metrics(session: Session, nm: NodeMetrics) -> MetricRecord:
    record = MetricRecord(
        id=str(uuid.uuid4()),
        timestamp=nm.timestamp,
        cluster_id=nm.cluster_id,
        node_id=nm.node_id,
        cpu_usage_pct=nm.cpu_usage_pct,
        memory_usage_pct=nm.memory_usage_pct,
        storage_read_iops=nm.storage_read_iops,
        storage_write_iops=nm.storage_write_iops,
        storage_read_latency_ms=nm.storage_read_latency_ms,
        storage_write_latency_ms=nm.storage_write_latency_ms,
        network_rx_mbps=nm.network_rx_mbps,
        network_tx_mbps=nm.network_tx_mbps,
        controller_vm_cpu_pct=nm.controller_vm_cpu_pct,
        controller_vm_mem_pct=nm.controller_vm_mem_pct,
        disk_throughput_mbps=nm.disk_throughput_mbps,
        active_vms=nm.active_vms,
    )
    session.add(record)
    return record


def get_metrics_window(
    session: Session,
    node_id: str,
    end_time: datetime,
    window_minutes: int = 30,
) -> list[NodeMetrics]:
    start_time = end_time - timedelta(minutes=window_minutes)
    stmt = (
        select(MetricRecord)
        .where(and_(
            MetricRecord.node_id == node_id,
            MetricRecord.timestamp >= start_time,
            MetricRecord.timestamp <= end_time,
        ))
        .order_by(MetricRecord.timestamp)
    )
    rows = session.execute(stmt).scalars().all()
    return [_orm_to_node_metrics(r) for r in rows]


def get_all_metrics_for_node(session: Session, node_id: str) -> list[NodeMetrics]:
    stmt = (
        select(MetricRecord)
        .where(MetricRecord.node_id == node_id)
        .order_by(MetricRecord.timestamp)
    )
    rows = session.execute(stmt).scalars().all()
    return [_orm_to_node_metrics(r) for r in rows]


def _orm_to_node_metrics(r: MetricRecord) -> NodeMetrics:
    return NodeMetrics(
        timestamp=r.timestamp,
        cluster_id=r.cluster_id,
        node_id=r.node_id,
        cpu_usage_pct=r.cpu_usage_pct,
        memory_usage_pct=r.memory_usage_pct,
        storage_read_iops=r.storage_read_iops,
        storage_write_iops=r.storage_write_iops,
        storage_read_latency_ms=r.storage_read_latency_ms,
        storage_write_latency_ms=r.storage_write_latency_ms,
        network_rx_mbps=r.network_rx_mbps,
        network_tx_mbps=r.network_tx_mbps,
        controller_vm_cpu_pct=r.controller_vm_cpu_pct,
        controller_vm_mem_pct=r.controller_vm_mem_pct,
        disk_throughput_mbps=r.disk_throughput_mbps,
        active_vms=r.active_vms,
    )


# ── Anomaly Events ────────────────────────────────────────────────────────────

def save_anomaly_event(session: Session, event: AnomalyEvent) -> AnomalyEventRecord:
    event_id = event.id or str(uuid.uuid4())
    record = AnomalyEventRecord(
        id=event_id,
        timestamp=event.timestamp,
        cluster_id=event.cluster_id,
        node_id=event.node_id,
        affected_metrics=json.dumps(event.affected_metrics),
        severity=event.severity.value,
        prophet_score=event.prophet_score,
        isolation_score=event.isolation_score,
        lstm_score=event.lstm_score,
        ensemble_score=event.ensemble_score,
        description=event.description,
    )
    session.add(record)
    return record


def get_anomaly_events(
    session: Session,
    severity: Severity | None = None,
    since: datetime | None = None,
    limit: int = 100,
) -> list[AnomalyEvent]:
    stmt = select(AnomalyEventRecord).order_by(AnomalyEventRecord.timestamp.desc())
    if severity:
        stmt = stmt.where(AnomalyEventRecord.severity == severity.value)
    if since:
        stmt = stmt.where(AnomalyEventRecord.timestamp >= since)
    stmt = stmt.limit(limit)
    rows = session.execute(stmt).scalars().all()
    return [_orm_to_anomaly_event(r) for r in rows]


def get_anomaly_event_by_id(session: Session, event_id: str) -> AnomalyEvent | None:
    row = session.get(AnomalyEventRecord, event_id)
    return _orm_to_anomaly_event(row) if row else None


def get_correlated_anomalies(
    session: Session,
    cluster_id: str,
    center_time: datetime,
    window_minutes: int = 10,
) -> list[AnomalyEvent]:
    start = center_time - timedelta(minutes=window_minutes)
    end = center_time + timedelta(minutes=window_minutes)
    stmt = (
        select(AnomalyEventRecord)
        .where(and_(
            AnomalyEventRecord.cluster_id == cluster_id,
            AnomalyEventRecord.timestamp >= start,
            AnomalyEventRecord.timestamp <= end,
        ))
        .order_by(AnomalyEventRecord.timestamp)
    )
    rows = session.execute(stmt).scalars().all()
    return [_orm_to_anomaly_event(r) for r in rows]


def _orm_to_anomaly_event(r: AnomalyEventRecord) -> AnomalyEvent:
    return AnomalyEvent(
        id=r.id,
        timestamp=r.timestamp,
        cluster_id=r.cluster_id,
        node_id=r.node_id,
        affected_metrics=json.loads(r.affected_metrics),
        severity=Severity(r.severity),
        prophet_score=r.prophet_score,
        isolation_score=r.isolation_score,
        lstm_score=r.lstm_score,
        ensemble_score=r.ensemble_score,
        description=r.description,
    )


# ── RCA Reports ───────────────────────────────────────────────────────────────

def save_rca_report(session: Session, report: RCAReport) -> RCAReportRecord:
    report_id = report.id or str(uuid.uuid4())
    record = RCAReportRecord(
        id=report_id,
        anomaly_event_id=report.anomaly_event_id,
        timestamp=report.timestamp,
        root_cause=report.root_cause,
        causal_chain=report.causal_chain,
        blast_radius=report.blast_radius,
        remediation_steps=json.dumps(report.remediation_steps),
        time_to_resolution_estimate=report.time_to_resolution_estimate,
        confidence_score=report.confidence_score,
        raw_llm_output=report.raw_llm_output,
    )
    session.add(record)
    return record


def get_rca_report_by_id(session: Session, report_id: str) -> RCAReport | None:
    row = session.get(RCAReportRecord, report_id)
    if not row:
        return None
    return RCAReport(
        id=row.id,
        anomaly_event_id=row.anomaly_event_id,
        timestamp=row.timestamp,
        root_cause=row.root_cause,
        causal_chain=row.causal_chain,
        blast_radius=row.blast_radius,
        remediation_steps=json.loads(row.remediation_steps),
        time_to_resolution_estimate=row.time_to_resolution_estimate,
        confidence_score=row.confidence_score,
        raw_llm_output=row.raw_llm_output,
    )


# ── Feedback ──────────────────────────────────────────────────────────────────

def save_feedback(session: Session, fb: FeedbackRecord) -> FeedbackRecordORM:
    record = FeedbackRecordORM(
        id=fb.id or str(uuid.uuid4()),
        rca_report_id=fb.rca_report_id,
        timestamp=fb.timestamp,
        helpful=fb.helpful,
        comment=fb.comment or "",
    )
    session.add(record)
    return record
