"""Feedback node: persists the RCA report and captures user rating."""

from __future__ import annotations
from clustersentinel.rca_agent.state import RCAState
from clustersentinel.storage.db import get_session
from clustersentinel.storage import repository as repo


def feedback_node(state: RCAState) -> RCAState:
    """Persist RCA report to DB. Feedback rating (if set) is also saved."""
    report = state.get("rca_report")
    if report is None:
        return state

    try:
        with get_session() as session:
            repo.save_rca_report(session, report)

            # If feedback has already been captured (e.g. from UI), persist it
            feedback_val = state.get("feedback")
            if feedback_val is not None and report.id:
                from clustersentinel.simulator.schemas import FeedbackRecord
                from datetime import datetime
                fb = FeedbackRecord(
                    rca_report_id=report.id,
                    timestamp=datetime.utcnow(),
                    helpful=bool(feedback_val),
                )
                repo.save_feedback(session, fb)

        return {**state, "error": None}
    except Exception as exc:
        return {**state, "error": str(exc)}
