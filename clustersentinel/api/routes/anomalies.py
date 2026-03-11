"""Anomaly event routes."""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from clustersentinel.simulator.schemas import AnomalyEvent, Severity
from clustersentinel.storage.db import get_session
from clustersentinel.storage import repository as repo

router = APIRouter()


@router.get("", response_model=list[AnomalyEvent])
def list_anomalies(
    severity: Optional[Severity] = Query(default=None),
    since: Optional[datetime] = Query(default=None),
    limit: int = Query(default=100, le=500),
):
    """List anomaly events, optionally filtered by severity and time."""
    with get_session() as session:
        return repo.get_anomaly_events(session, severity=severity, since=since, limit=limit)


@router.get("/{event_id}", response_model=AnomalyEvent)
def get_anomaly(event_id: str):
    """Get a specific anomaly event by ID."""
    with get_session() as session:
        event = repo.get_anomaly_event_by_id(session, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Anomaly event not found")
    return event
