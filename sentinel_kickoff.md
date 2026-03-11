# ClusterSentinel — Claude Code Project Kickoff

## GitHub Repo Name
**`clustersentinel`**

Tagline: *Open-source AI-powered anomaly detection and root cause analysis for HCI clusters.*

---

## Project Overview

ClusterSentinel is an open-source, end-to-end AIOps platform for **Hyperconverged Infrastructure (HCI)** environments. It simulates realistic multi-node cluster telemetry, detects anomalies across infrastructure metrics, and drives a conversational LangGraph-based RCA (Root Cause Analysis) agent that explains failures in plain English — with a feedback loop for continuous model improvement.

The project is intentionally **generic and infrastructure-agnostic**: it works conceptually for any HCI platform (Nutanix, VMware vSAN, Dell VxRail, etc.) but models its metric schema and failure patterns on realistic enterprise HCI behavior. It is 100% built on synthetic, self-authored data.

---

## Tech Stack

```
Language:         Python 3.11
Simulation:       NumPy, Pandas
ML/Detection:     scikit-learn (Isolation Forest), Prophet (Facebook), PyTorch (LSTM autoencoder)
LLM Orchestration: LangGraph, LangChain
LLM Backend:      Anthropic Claude API (claude-sonnet-4-20250514) with Ollama fallback
Vector Store:     ChromaDB (RAG knowledge base)
Time-Series DB:   SQLite via SQLAlchemy
API Layer:        FastAPI
Dashboard UI:     Streamlit
Config:           Pydantic Settings + .env
Testing:          pytest
Packaging:        pyproject.toml (uv-compatible)
```

---

## Full Directory Structure to Scaffold

```
clustersentinel/
│
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
│
├── clustersentinel/
│   ├── __init__.py
│   │
│   ├── simulator/
│   │   ├── __init__.py
│   │   ├── cluster.py           # Multi-node cluster state machine
│   │   ├── telemetry.py         # Per-node metric emission (CPU, mem, IOPS, latency, network)
│   │   ├── failure_injector.py  # Injects named failure scenarios
│   │   └── schemas.py           # Pydantic models for metric payloads
│   │
│   ├── detection/
│   │   ├── __init__.py
│   │   ├── base.py              # Abstract DetectorBase class
│   │   ├── prophet_detector.py  # Seasonal baseline + band breach
│   │   ├── isolation_forest.py  # Multi-metric outlier scoring
│   │   ├── lstm_autoencoder.py  # Temporal pattern anomaly (PyTorch)
│   │   └── ensemble.py          # Score fusion across detectors
│   │
│   ├── rca_agent/
│   │   ├── __init__.py
│   │   ├── graph.py             # LangGraph StateGraph definition (the main agent)
│   │   ├── state.py             # Shared agent state schema
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── detector_node.py     # Pulls anomaly signals, queries time-series store
│   │   │   ├── correlator_node.py   # Cross-node/metric causal chaining
│   │   │   ├── explainer_node.py    # LLM call: generates RCA narrative + remediation
│   │   │   └── feedback_node.py     # Captures user rating, queues for retraining
│   │   └── knowledge_base/
│   │       ├── loader.py            # Loads .md docs into ChromaDB
│   │       └── docs/
│   │           ├── hci_concepts.md       # What is HCI, CVM, distributed storage fabric
│   │           ├── failure_patterns.md   # Known failure signatures + meanings
│   │           ├── metric_glossary.md    # Definitions of every tracked metric
│   │           └── remediation_runbook.md # Standard remediation steps per failure type
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── db.py                # SQLAlchemy setup, session management
│   │   ├── models.py            # ORM models: MetricRecord, AnomalyEvent, RCAReport, Feedback
│   │   └── repository.py        # CRUD helpers
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app factory
│   │   └── routes/
│   │       ├── metrics.py       # GET /metrics, POST /ingest
│   │       ├── anomalies.py     # GET /anomalies, GET /anomalies/{id}
│   │       ├── rca.py           # POST /rca/trigger, GET /rca/{id}
│   │       └── feedback.py      # POST /feedback
│   │
│   ├── ui/
│   │   └── dashboard.py         # Streamlit: cluster timeline, anomaly heatmap, RCA chat panel
│   │
│   └── config.py                # Pydantic BaseSettings (API keys, DB path, model params)
│
├── scripts/
│   ├── run_simulation.py        # CLI: run simulator for N hours, stream to DB
│   ├── train_models.py          # CLI: train/retrain all detection models
│   └── seed_knowledge_base.py   # CLI: load docs/ into ChromaDB
│
└── tests/
    ├── test_simulator.py
    ├── test_detectors.py
    ├── test_rca_agent.py
    └── test_api.py
```

---

## Simulator: Metric Schema

Each node in the simulated cluster emits the following metrics every 30 seconds (configurable):

```python
@dataclass
class NodeMetrics:
    timestamp: datetime
    cluster_id: str
    node_id: str                  # e.g. "node-01", "node-02"
    cpu_usage_pct: float          # 0–100
    memory_usage_pct: float       # 0–100
    storage_read_iops: float
    storage_write_iops: float
    storage_read_latency_ms: float
    storage_write_latency_ms: float
    network_rx_mbps: float
    network_tx_mbps: float
    controller_vm_cpu_pct: float  # CVM equivalent — management overhead
    controller_vm_mem_pct: float
    disk_throughput_mbps: float
    active_vms: int
```

Cluster-level aggregates (computed):
```python
@dataclass  
class ClusterMetrics:
    timestamp: datetime
    cluster_id: str
    total_cpu_usage_pct: float
    total_memory_usage_pct: float
    storage_utilization_pct: float
    avg_read_latency_ms: float
    avg_write_latency_ms: float
    degraded_nodes: int           # nodes with health_score < threshold
    replication_lag_ms: float     # data sync lag across nodes
```

---

## Simulator: Failure Scenarios to Implement

Each scenario has a named `FailureMode` enum and an `inject()` method that perturbs metric generation:

| Failure Name | Description | Affected Metrics | Duration |
|---|---|---|---|
| `NODE_DEGRADATION` | Single node slowly fails; CVM CPU spikes, IOPS drop | `controller_vm_cpu_pct`, `storage_write_iops`, `storage_write_latency_ms` | 15–45 min |
| `NOISY_NEIGHBOR` | VM on node-02 consumes excessive CPU/IOPS, starving co-located VMs | `cpu_usage_pct`, `storage_read_iops`, `active_vms` | 5–20 min |
| `STORAGE_REBALANCE` | Distributed storage rebalancing event; high disk throughput, latency spikes | `disk_throughput_mbps`, `storage_write_latency_ms`, `replication_lag_ms` | 30–90 min |
| `MEMORY_PRESSURE` | Gradual memory exhaustion on two nodes | `memory_usage_pct`, `controller_vm_mem_pct` | 20–60 min |
| `NETWORK_SATURATION` | East-west traffic spike; RX/TX saturate, replication lags | `network_rx_mbps`, `network_tx_mbps`, `replication_lag_ms` | 10–30 min |
| `DISK_PRE_FAILURE` | Slow degradation: rising latency + IOPS drops before disk failure | `storage_read_latency_ms`, `storage_write_latency_ms`, `storage_read_iops` | 60–180 min |
| `CASCADING_FAILURE` | NODE_DEGRADATION triggers STORAGE_REBALANCE on remaining nodes | Multiple | 45–120 min |

---

## Detection Pipeline

### 1. ProphetDetector
- Trains a per-metric Prophet model on 7 days of simulated baseline data
- Predicts expected band (yhat_lower, yhat_upper) for the next window
- Anomaly = actual value outside the predicted band
- Returns: `AnomalyScore(metric, node_id, score, expected_range, actual_value)`

### 2. IsolationForestDetector
- Multi-metric input: all NodeMetrics fields for a given node as a feature vector
- Trained on clean baseline data; contamination=0.05
- Returns outlier score per node per timestep

### 3. LSTMAutoencoderDetector
- Input: sliding window of 60 timesteps × N metrics (per node)
- Architecture: LSTM encoder → bottleneck → LSTM decoder
- Anomaly = reconstruction error above dynamic threshold (95th percentile of training errors)
- Captures temporal patterns invisible to point-in-time detectors

### 4. EnsembleDetector
- Fuses scores from all three detectors with configurable weights
- Emits a final `AnomalyEvent` only if ensemble score exceeds threshold
- `AnomalyEvent` fields: `timestamp, node_id, cluster_id, affected_metrics, severity (LOW/MEDIUM/HIGH/CRITICAL), individual_scores, ensemble_score`

---

## LangGraph RCA Agent

### State Schema
```python
class RCAState(TypedDict):
    anomaly_event: AnomalyEvent
    related_metrics: list[MetricRecord]     # Raw metric window around the event
    correlated_events: list[AnomalyEvent]   # Other anomalies in same time window
    kb_context: str                          # RAG-retrieved knowledge base passages
    rca_report: str                          # Final generated narrative
    remediation_steps: list[str]
    confidence_score: float
    feedback: Optional[int]                  # 1 (helpful) or 0 (not helpful)
```

### Agent Graph (LangGraph StateGraph)
```
START
  → detector_node        # Fetches metric window, validates anomaly event
  → correlator_node      # Queries DB for co-occurring anomalies; builds causal chain
  → kb_retrieval_node    # RAG lookup in ChromaDB using anomaly + metric context
  → explainer_node       # LLM call: generates RCA narrative using chain + KB context
  → feedback_node        # Exposes RCA to user; captures rating; logs to feedback queue
END
```

### Explainer Node — LLM Prompt Template
```
System: You are an expert HCI infrastructure engineer. You diagnose failures in 
hyperconverged infrastructure clusters by analyzing telemetry data. You explain 
failures clearly and suggest actionable remediation. Be specific about nodes, 
metrics, and timings. Use technical language appropriate for a senior SRE.

Context from knowledge base:
{kb_context}

Anomaly detected:
- Node: {node_id}  
- Time: {timestamp}
- Severity: {severity}
- Affected metrics: {affected_metrics}

Correlated events in the same time window:
{correlated_events}

Raw metric trajectory (last 30 minutes):
{metric_table}

Task: 
1. Identify the most likely root cause
2. Explain the causal chain (what triggered what)
3. Assess blast radius (which workloads/nodes are affected)
4. Provide 3–5 specific remediation steps in priority order
5. Estimate time-to-resolution if no action is taken
```

---

## Knowledge Base Documents to Author

Create these files in `clustersentinel/rca_agent/knowledge_base/docs/`:

### `hci_concepts.md`
Cover: what is a hyperconverged cluster, node roles, controller VMs (the management process that runs per node handling storage I/O), distributed storage fabric (how data is replicated across nodes), replication factor (RF2 = 2 copies of all data), storage tiering (hot SSD vs cold HDD tiers), ADS-style dynamic scheduling.

### `failure_patterns.md`
Cover each of the 7 failure scenarios above: what metrics deviate, in what order, and what the causal mechanism is. E.g.: *"Disk pre-failure typically presents as gradually increasing write latency (>5ms baseline creep over 2+ hours) followed by IOPS degradation. This is caused by the storage controller retrying writes as disk sectors become unreliable."*

### `metric_glossary.md`
Define every metric in `NodeMetrics` and `ClusterMetrics`: what it measures, normal range, warning threshold, critical threshold, and what high/low values mean.

### `remediation_runbook.md`
Standard runbook entries for each failure type: immediate triage steps, isolation procedures, recovery actions, post-incident checks.

---

## FastAPI Endpoints

```
POST   /api/v1/metrics/ingest          # Ingest a batch of NodeMetrics
GET    /api/v1/metrics/{node_id}       # Get metric history for a node
GET    /api/v1/anomalies               # List all anomaly events (filterable by severity, time)
GET    /api/v1/anomalies/{id}          # Get a specific anomaly event
POST   /api/v1/rca/trigger             # Manually trigger RCA for an anomaly_id
GET    /api/v1/rca/{id}                # Get RCA report by ID
POST   /api/v1/feedback                # Submit feedback (helpful/not helpful + comment)
GET    /api/v1/health                  # Service health check
```

---

## Streamlit Dashboard (ui/dashboard.py)

Three-panel layout:

**Panel 1 — Cluster Health Timeline**
- Multi-line chart: one line per node, showing ensemble anomaly score over time
- Color band: green (normal) → yellow (warning) → red (critical)
- Click on a spike to open the RCA panel

**Panel 2 — Anomaly Heatmap**
- Grid: nodes (rows) × metrics (columns)
- Cell color = current anomaly score for that node/metric pair
- Updates in near-real-time as simulator runs

**Panel 3 — RCA Chat Panel**
- Shows the latest RCA report as a structured card: root cause summary, causal chain, remediation steps
- Thumbs up / thumbs down feedback buttons
- Text input: "Ask a follow-up question about this incident" → routes to LLM with full RCA context

---

## Scripts

### `scripts/run_simulation.py`
```
Usage: python scripts/run_simulation.py --nodes 4 --duration-hours 24 --inject NODE_DEGRADATION,NOISY_NEIGHBOR
```
- Generates N hours of synthetic cluster data
- Optionally injects one or more failure scenarios at random timestamps
- Streams metrics to SQLite via the storage layer
- Triggers the detection pipeline in real time

### `scripts/train_models.py`
```
Usage: python scripts/train_models.py --baseline-hours 168
```
- Reads 7 days of clean baseline data from DB (or generates it fresh)
- Trains Prophet, IsolationForest, and LSTM autoencoder
- Saves model artifacts to `models/` directory

### `scripts/seed_knowledge_base.py`
```
Usage: python scripts/seed_knowledge_base.py
```
- Reads all `.md` files from `rca_agent/knowledge_base/docs/`
- Chunks and embeds them into ChromaDB

---

## Configuration (.env.example)

```env
# LLM
ANTHROPIC_API_KEY=your_key_here
LLM_MODEL=claude-sonnet-4-20250514
LLM_MAX_TOKENS=1500

# Database
DATABASE_URL=sqlite:///./clustersentinel.db
CHROMA_PERSIST_DIR=./chroma_db

# Simulation
DEFAULT_CLUSTER_NODES=4
METRIC_INTERVAL_SECONDS=30
ANOMALY_ENSEMBLE_THRESHOLD=0.65

# Model paths
MODELS_DIR=./models

# API
API_HOST=0.0.0.0
API_PORT=8000
```

---

## pyproject.toml Dependencies

```toml
[project]
name = "clustersentinel"
version = "0.1.0"
description = "AI-powered anomaly detection and RCA for HCI clusters"
requires-python = ">=3.11"

[project.dependencies]
fastapi = ">=0.111"
uvicorn = ">=0.29"
streamlit = ">=1.35"
langchain = ">=0.2"
langgraph = ">=0.1"
langchain-anthropic = ">=0.1"
anthropic = ">=0.28"
chromadb = ">=0.5"
prophet = ">=1.1"
scikit-learn = ">=1.4"
torch = ">=2.2"
sqlalchemy = ">=2.0"
pydantic = ">=2.7"
pydantic-settings = ">=2.3"
numpy = ">=1.26"
pandas = ">=2.2"
python-dotenv = ">=1.0"
rich = ">=13.7"
typer = ">=0.12"
pytest = ">=8.0"
httpx = ">=0.27"
```

---

## Claude Code Instructions

When you start this project in Claude Code, use this prompt:

---

**Prompt to paste into Claude Code:**

```
Bootstrap the `clustersentinel` Python project according to the architecture in this spec.

Start with these steps in order:

1. Create the full directory structure and all __init__.py files
2. Create pyproject.toml with all dependencies listed
3. Create .env.example and config.py (Pydantic BaseSettings)
4. Implement clustersentinel/simulator/schemas.py — all Pydantic models for NodeMetrics, ClusterMetrics, AnomalyEvent, RCAReport, FeedbackRecord
5. Implement clustersentinel/simulator/telemetry.py — the metric generator for a single node using numpy for realistic noise + diurnal patterns (higher load during 9am-6pm)
6. Implement clustersentinel/simulator/failure_injector.py — all 7 failure scenarios as injectable perturbations on top of baseline telemetry
7. Implement clustersentinel/simulator/cluster.py — orchestrates N nodes, calls telemetry.py per node, applies failure injector if active
8. Implement clustersentinel/storage/ — SQLAlchemy ORM models, db setup, repository CRUD
9. Implement clustersentinel/detection/prophet_detector.py
10. Implement clustersentinel/detection/isolation_forest.py
11. Implement clustersentinel/detection/lstm_autoencoder.py (PyTorch)
12. Implement clustersentinel/detection/ensemble.py
13. Implement the knowledge base docs (all 4 .md files in rca_agent/knowledge_base/docs/)
14. Implement clustersentinel/rca_agent/state.py and graph.py (LangGraph StateGraph)
15. Implement all 4 agent nodes in rca_agent/agents/
16. Implement clustersentinel/api/ — FastAPI app with all routes
17. Implement clustersentinel/ui/dashboard.py — Streamlit 3-panel dashboard
18. Implement all 3 scripts in scripts/
19. Write tests for simulator, detectors, and RCA agent
20. Write a comprehensive README.md with architecture diagram (ASCII), quickstart, and usage examples

Use type hints everywhere. Use Pydantic models for all data contracts. Each module should have a clear docstring explaining its role. Keep all modules under 300 lines — split if needed.
```

---

## README Structure to Generate

```
# ClusterSentinel

> AI-powered anomaly detection and root cause analysis for HCI clusters

## Architecture
[ASCII diagram of the pipeline]

## Features
## Quickstart
## Configuration
## Running the Simulator
## Training the Models
## Running the API
## Running the Dashboard
## How the RCA Agent Works
## Knowledge Base
## Feedback Loop
## Contributing
## License (MIT)
```

---

## Key Design Principles to Enforce Throughout

1. **No real cluster required** — entire project runs on synthetic data from the simulator
2. **Pluggable detectors** — new detector = subclass `DetectorBase`, implement `fit()` and `detect()`, register in ensemble
3. **Pluggable LLM** — swap Anthropic for Ollama by changing one config value
4. **Knowledge base is plain Markdown** — domain experts can contribute without touching code
5. **Feedback loop is first-class** — every RCA gets a rating; low-rated RCAs are flagged for KB improvement
6. **Failure scenarios are composable** — multiple failures can be active simultaneously for cascading event simulation
