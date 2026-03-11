"""Detector node: validates the anomaly event and fetches the metric window from DB."""

from __future__ import annotations
from clustersentinel.rca_agent.state import RCAState
from clustersentinel.storage.db import get_session
from clustersentinel.storage import repository as repo


def detector_node(state: RCAState) -> RCAState:
    """Fetch raw metric history for the anomaly event's node and time window."""
    event = state["anomaly_event"]
    try:
        with get_session() as session:
            related = repo.get_metrics_window(
                session,
                node_id=event.node_id,
                end_time=event.timestamp,
                window_minutes=30,
            )
        return {**state, "related_metrics": related, "error": None}
    except Exception as exc:
        return {**state, "related_metrics": [], "error": str(exc)}
