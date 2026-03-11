"""Tests for the RCA agent (mocking LLM calls)."""

from __future__ import annotations
import json
from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest
from clustersentinel.simulator.schemas import AnomalyEvent, Severity
from clustersentinel.rca_agent.state import RCAState
from clustersentinel.rca_agent.agents.detector_node import detector_node
from clustersentinel.rca_agent.agents.correlator_node import correlator_node
from clustersentinel.storage.db import init_db


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def _make_event() -> AnomalyEvent:
    return AnomalyEvent(
        id="test-event-001",
        timestamp=datetime(2024, 1, 1, 10, 0),
        node_id="node-01",
        cluster_id="cluster-test",
        affected_metrics=["controller_vm_cpu_pct", "storage_write_latency_ms"],
        severity=Severity.HIGH,
        ensemble_score=0.82,
    )


def _make_initial_state(event: AnomalyEvent) -> RCAState:
    return {
        "anomaly_event": event,
        "related_metrics": [],
        "correlated_events": [],
        "kb_context": "",
        "rca_report": None,
        "remediation_steps": [],
        "confidence_score": 0.0,
        "feedback": None,
        "error": None,
    }


def test_detector_node_runs_without_error():
    event = _make_event()
    state = _make_initial_state(event)
    result = detector_node(state)
    assert "related_metrics" in result
    assert isinstance(result["related_metrics"], list)


def test_correlator_node_runs_without_error():
    event = _make_event()
    state = _make_initial_state(event)
    result = correlator_node(state)
    assert "correlated_events" in result
    assert isinstance(result["correlated_events"], list)


def test_explainer_node_with_mocked_llm():
    from clustersentinel.rca_agent.agents.explainer_node import explainer_node
    event = _make_event()
    state: RCAState = {
        **_make_initial_state(event),
        "kb_context": "Sample KB context about NODE_DEGRADATION.",
    }

    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "root_cause": "CVM CPU exhaustion due to disk retries",
        "causal_chain": "Disk sectors failing → CVM retries → CPU saturation → write IOPS drop",
        "blast_radius": "node-01 and co-located VMs",
        "remediation_steps": ["Step 1", "Step 2", "Step 3"],
        "time_to_resolution_estimate": "30–45 minutes with intervention",
        "confidence_score": 0.85,
    })

    with patch("clustersentinel.rca_agent.agents.explainer_node._get_llm") as mock_llm_factory:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response
        mock_llm_factory.return_value = mock_llm

        result = explainer_node(state)

    assert result["rca_report"] is not None
    assert result["rca_report"].root_cause == "CVM CPU exhaustion due to disk retries"
    assert len(result["rca_report"].remediation_steps) == 3
    assert result["confidence_score"] == pytest.approx(0.85)


def test_graph_runs_end_to_end_with_mocked_llm():
    from clustersentinel.rca_agent.graph import run_rca

    event = _make_event()
    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "root_cause": "Node degradation",
        "causal_chain": "Disk → CVM → IOPS",
        "blast_radius": "node-01",
        "remediation_steps": ["Evacuate VMs", "Check disks"],
        "time_to_resolution_estimate": "1 hour",
        "confidence_score": 0.75,
    })

    with patch("clustersentinel.rca_agent.agents.explainer_node._get_llm") as mock_llm_factory:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response
        mock_llm_factory.return_value = mock_llm

        final_state = run_rca(event)

    assert final_state["rca_report"] is not None
    assert final_state["error"] is None
