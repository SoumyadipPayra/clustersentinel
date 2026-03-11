"""Feedback routes."""

from datetime import datetime
from fastapi import APIRouter
from clustersentinel.simulator.schemas import FeedbackRecord
from clustersentinel.storage.db import get_session
from clustersentinel.storage import repository as repo

router = APIRouter()


@router.post("", status_code=201)
def submit_feedback(feedback: FeedbackRecord):
    """Submit feedback (helpful/not helpful + optional comment) for an RCA report."""
    if not feedback.timestamp:
        feedback = feedback.model_copy(update={"timestamp": datetime.utcnow()})
    with get_session() as session:
        repo.save_feedback(session, feedback)
    return {"status": "recorded"}
