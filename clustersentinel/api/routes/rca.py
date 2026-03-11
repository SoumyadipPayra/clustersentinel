"""RCA routes: trigger analysis and retrieve reports."""

from __future__ import annotations
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, BackgroundTasks
from clustersentinel.simulator.schemas import RCAReport
from clustersentinel.storage.db import get_session
from clustersentinel.storage import repository as repo
from clustersentinel.rca_agent.graph import run_rca

router = APIRouter()

# In-memory job status for async RCA runs
_jobs: dict[str, str] = {}  # anomaly_id → rca_report_id | "pending" | "error:..."


class TriggerRequest(BaseModel):
    anomaly_id: str


@router.post("/trigger", status_code=202)
def trigger_rca(request: TriggerRequest, background_tasks: BackgroundTasks):
    """Trigger RCA asynchronously for a given anomaly event ID."""
    anomaly_id = request.anomaly_id
    with get_session() as session:
        event = repo.get_anomaly_event_by_id(session, anomaly_id)
    if not event:
        raise HTTPException(status_code=404, detail="Anomaly event not found")

    _jobs[anomaly_id] = "pending"
    background_tasks.add_task(_run_rca_task, event, anomaly_id)
    return {"status": "accepted", "anomaly_id": anomaly_id}


def _run_rca_task(event, anomaly_id: str) -> None:
    try:
        final_state = run_rca(event)
        report = final_state.get("rca_report")
        _jobs[anomaly_id] = report.id if report else "error:no_report"
    except Exception as exc:
        _jobs[anomaly_id] = f"error:{exc}"


@router.get("/status/{anomaly_id}")
def rca_status(anomaly_id: str):
    """Check the status of an RCA job."""
    status = _jobs.get(anomaly_id)
    if status is None:
        raise HTTPException(status_code=404, detail="No RCA job found for this anomaly ID")
    if status == "pending":
        return {"status": "pending"}
    if status.startswith("error:"):
        return {"status": "error", "detail": status[6:]}
    return {"status": "completed", "rca_report_id": status}


@router.get("/{report_id}", response_model=RCAReport)
def get_rca_report(report_id: str):
    """Retrieve an RCA report by ID."""
    with get_session() as session:
        report = repo.get_rca_report_by_id(session, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="RCA report not found")
    return report
