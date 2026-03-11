"""Metrics routes: ingest and retrieve node metrics."""

from __future__ import annotations
from fastapi import APIRouter, HTTPException
from clustersentinel.simulator.schemas import NodeMetrics
from clustersentinel.storage.db import get_session
from clustersentinel.storage import repository as repo

router = APIRouter()


@router.post("/ingest", status_code=201)
def ingest_metrics(batch: list[NodeMetrics]):
    """Ingest a batch of NodeMetrics records."""
    with get_session() as session:
        for nm in batch:
            repo.save_node_metrics(session, nm)
    return {"ingested": len(batch)}


@router.get("/{node_id}", response_model=list[NodeMetrics])
def get_node_metrics(node_id: str):
    """Get full metric history for a node."""
    with get_session() as session:
        records = repo.get_all_metrics_for_node(session, node_id)
    if not records:
        raise HTTPException(status_code=404, detail=f"No metrics found for node '{node_id}'")
    return records
