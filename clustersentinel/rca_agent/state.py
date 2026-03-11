"""Shared state schema for the LangGraph RCA agent."""

from __future__ import annotations
from typing import Optional
from typing_extensions import TypedDict
from clustersentinel.simulator.schemas import AnomalyEvent, NodeMetrics, RCAReport


class RCAState(TypedDict):
    anomaly_event: AnomalyEvent
    related_metrics: list[NodeMetrics]       # Raw metric window around the event
    correlated_events: list[AnomalyEvent]    # Other anomalies in the same time window
    kb_context: str                          # RAG-retrieved knowledge base passages
    rca_report: Optional[RCAReport]          # Final generated report
    remediation_steps: list[str]
    confidence_score: float
    feedback: Optional[int]                  # 1 = helpful, 0 = not helpful
    error: Optional[str]                     # Non-None if a node failed
