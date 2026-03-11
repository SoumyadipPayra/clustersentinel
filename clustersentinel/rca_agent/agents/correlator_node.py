"""Correlator node: queries DB for co-occurring anomalies and builds causal context."""

from __future__ import annotations
from clustersentinel.rca_agent.state import RCAState
from clustersentinel.storage.db import get_session
from clustersentinel.storage import repository as repo


def correlator_node(state: RCAState) -> RCAState:
    """Find other anomalies in the same cluster within ±10 minutes of this event."""
    event = state["anomaly_event"]
    try:
        with get_session() as session:
            correlated = repo.get_correlated_anomalies(
                session,
                cluster_id=event.cluster_id,
                center_time=event.timestamp,
                window_minutes=10,
            )
        # Exclude the triggering event itself
        correlated = [e for e in correlated if e.id != event.id]
        return {**state, "correlated_events": correlated, "error": None}
    except Exception as exc:
        return {**state, "correlated_events": [], "error": str(exc)}
