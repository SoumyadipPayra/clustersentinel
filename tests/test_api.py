"""Tests for the FastAPI layer."""

from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from clustersentinel.api.main import app
from clustersentinel.storage.db import init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_health_endpoint():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ingest_metrics():
    payload = [
        {
            "timestamp": datetime.utcnow().isoformat(),
            "cluster_id": "cluster-test",
            "node_id": "node-01",
            "cpu_usage_pct": 45.0,
            "memory_usage_pct": 60.0,
            "storage_read_iops": 3000,
            "storage_write_iops": 1500,
            "storage_read_latency_ms": 2.0,
            "storage_write_latency_ms": 3.0,
            "network_rx_mbps": 400,
            "network_tx_mbps": 350,
            "controller_vm_cpu_pct": 20.0,
            "controller_vm_mem_pct": 35.0,
            "disk_throughput_mbps": 200,
            "active_vms": 12,
        }
    ]
    resp = client.post("/api/v1/metrics/ingest", json=payload)
    assert resp.status_code == 201
    assert resp.json()["ingested"] == 1


def test_get_node_metrics_not_found():
    resp = client.get("/api/v1/metrics/nonexistent-node")
    assert resp.status_code == 404


def test_list_anomalies_empty():
    resp = client.get("/api/v1/anomalies")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_anomaly_not_found():
    resp = client.get("/api/v1/anomalies/nonexistent-id")
    assert resp.status_code == 404


def test_get_rca_not_found():
    resp = client.get("/api/v1/rca/nonexistent-id")
    assert resp.status_code == 404


def test_submit_feedback():
    payload = {
        "rca_report_id": "report-123",
        "timestamp": datetime.utcnow().isoformat(),
        "helpful": True,
        "comment": "Very accurate diagnosis",
    }
    resp = client.post("/api/v1/feedback", json=payload)
    assert resp.status_code == 201
