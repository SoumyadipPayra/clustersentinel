# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

ClusterSentinel — open-source AIOps platform for Hyperconverged Infrastructure (HCI). Simulates multi-node cluster telemetry, detects anomalies, and runs a LangGraph RCA agent backed by Anthropic Claude (or Ollama).

## Commands

```bash
# Install (uv recommended)
uv venv && uv pip install -e ".[dev]"
# or: pip install -e .

# Run API server
uvicorn clustersentinel.api.main:app --reload --port 8000

# Run Streamlit dashboard
streamlit run clustersentinel/ui/dashboard.py

# Run simulator (1 hour, 4 nodes, inject two failure modes)
python scripts/run_simulation.py --nodes 4 --duration-hours 1 --inject NODE_DEGRADATION,NOISY_NEIGHBOR

# Train detection models (on 7 days of synthetic baseline)
python scripts/train_models.py --baseline-hours 168

# Seed ChromaDB knowledge base
python scripts/seed_knowledge_base.py

# Run all tests
pytest

# Run a single test file
pytest tests/test_simulator.py -v

# Run a single test
pytest tests/test_api.py::test_ingest_metrics -v
```

## Architecture

```
Simulator → Storage (SQLite) → Detection Pipeline → EnsembleDetector
                                                          ↓
                                              AnomalyEvent emitted
                                                          ↓
                                        LangGraph RCA Agent (4 nodes):
                                          detector_node → correlator_node
                                               → kb_retrieval → explainer_node
                                                   → feedback_node
                                                          ↓
                                              RCAReport saved to DB
                                                          ↓
                                        FastAPI ←→ Streamlit Dashboard
```

### Key layers

**Simulator** (`clustersentinel/simulator/`)
- `cluster.py` — orchestrates N nodes, applies `FailureInjector` overrides per tick
- `telemetry.py` — generates `NodeMetrics` with diurnal patterns (higher load 09:00–18:00) + Gaussian noise
- `failure_injector.py` — 7 failure modes as additive metric deltas; multiple can be active simultaneously
- `schemas.py` — all Pydantic data models (`NodeMetrics`, `ClusterMetrics`, `AnomalyEvent`, `RCAReport`, `FeedbackRecord`)

**Detection** (`clustersentinel/detection/`)
- `base.py` — `DetectorBase` ABC with `fit(df)` / `detect(df)` interface; new detectors just subclass this
- `prophet_detector.py` — one Prophet model per (node, metric); anomaly = outside [yhat_lower, yhat_upper]
- `isolation_forest.py` — one IsolationForest per node on all 11 feature metrics
- `lstm_autoencoder.py` — sliding window (60 steps) LSTM; threshold = 95th pct training reconstruction error
- `ensemble.py` — fuses Prophet (35%) + IsolationForest (30%) + LSTM (35%); emits `AnomalyEvent` if score ≥ threshold

**RCA Agent** (`clustersentinel/rca_agent/`)
- `graph.py` — LangGraph `StateGraph`; `run_rca(anomaly_event)` is the main entry point
- `state.py` — `RCAState` TypedDict shared across all graph nodes
- `agents/` — four nodes: `detector_node` (fetch metric window), `correlator_node` (co-occurring anomalies), `kb_retrieval` (ChromaDB RAG), `explainer_node` (LLM call → structured JSON RCAReport)
- `knowledge_base/loader.py` — chunks `.md` docs into ChromaDB; `retrieve_context(query)` for RAG

**Storage** (`clustersentinel/storage/`)
- `db.py` — SQLAlchemy engine + `get_session()` context manager
- `models.py` — ORM: `MetricRecord`, `AnomalyEventRecord`, `RCAReportRecord`, `FeedbackRecordORM`
- `repository.py` — all CRUD; import functions directly (no class wrapper)

**API** (`clustersentinel/api/`)
- FastAPI app with four route modules under `/api/v1/`: `metrics`, `anomalies`, `rca`, `feedback`
- RCA trigger is async (BackgroundTasks); poll `/api/v1/rca/status/{anomaly_id}` for completion

**Config** (`clustersentinel/config.py`)
- `settings` singleton from `.env`; LLM provider switchable via `LLM_PROVIDER=ollama`

## LLM Provider

Default: Anthropic (`claude-sonnet-4-20250514`). Set `LLM_PROVIDER=ollama` in `.env` to use local Ollama — no other code changes needed. The `explainer_node` calls `_get_llm()` which returns the correct LangChain chat model.

## Adding a New Detector

1. Subclass `DetectorBase` in `clustersentinel/detection/`
2. Implement `fit(df)` and `detect(df) → list[AnomalyScore]`
3. Register it in `EnsembleDetector.__init__()` and add its weight to `_WEIGHTS`

## Adding a New Failure Mode

1. Add enum value to `FailureMode` in `failure_injector.py`
2. Write an injector function `_my_failure(f, node_id, nodes, rng) → dict[str, float]`
3. Add duration bounds to `_DURATIONS` and register in `_INJECTORS`

## Database

SQLite by default (`clustersentinel.db` in project root). Change `DATABASE_URL` in `.env` for Postgres. `init_db()` creates all tables; call it once at startup.
