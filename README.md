# ClusterSentinel

> AI-powered anomaly detection and root cause analysis for HCI clusters

ClusterSentinel is an open-source AIOps platform for **Hyperconverged Infrastructure (HCI)**. It simulates realistic multi-node cluster telemetry, detects anomalies using three complementary ML models, and drives a conversational LangGraph RCA agent that explains failures in plain English — with a feedback loop for continuous improvement.

No real cluster required. Everything runs on synthetic data.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Simulator                            │
│  ClusterSimulator → NodeMetrics × N nodes per tick      │
│  FailureInjector  → 7 failure modes, composable         │
└──────────────────────────┬──────────────────────────────┘
                           │ SQLite (SQLAlchemy)
                           ▼
┌─────────────────────────────────────────────────────────┐
│                Detection Pipeline                       │
│  ProphetDetector + IsolationForest + LSTMAutoencoder    │
│  EnsembleDetector → AnomalyEvent (score ≥ threshold)   │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              LangGraph RCA Agent                        │
│  detector_node → correlator_node → kb_retrieval        │
│  → explainer_node (LLM) → feedback_node                │
│  ChromaDB RAG ← 4 HCI knowledge base docs              │
└──────────────────────────┬──────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
    FastAPI REST API           Streamlit Dashboard
    /api/v1/metrics            Timeline + Heatmap
    /api/v1/anomalies          RCA Panel + Feedback
    /api/v1/rca
    /api/v1/feedback
```

## Features

- **Realistic simulation** of 4-node HCI clusters with diurnal load patterns
- **7 failure scenarios**: NODE_DEGRADATION, NOISY_NEIGHBOR, STORAGE_REBALANCE, MEMORY_PRESSURE, NETWORK_SATURATION, DISK_PRE_FAILURE, CASCADING_FAILURE
- **Three-model detection ensemble**: Prophet (seasonal), Isolation Forest (multivariate), LSTM Autoencoder (temporal)
- **LangGraph RCA agent** with RAG-augmented HCI knowledge base
- **Pluggable LLM**: Anthropic Claude or local Ollama
- **Streamlit dashboard**: cluster timeline, anomaly heatmap, RCA chat panel
- **Feedback loop**: thumbs up/down on every RCA report

## Quickstart

```bash
# 1. Clone and install
git clone https://github.com/SoumyadipPayra/clustersentinel
cd clustersentinel
pip install -e .

# 2. Configure
cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY or set LLM_PROVIDER=ollama

# 3. Seed the knowledge base
python scripts/seed_knowledge_base.py

# 4. Generate baseline data and train models
python scripts/run_simulation.py --duration-hours 24
python scripts/train_models.py --baseline-hours 24

# 5. Run a simulation with failures
python scripts/run_simulation.py --nodes 4 --duration-hours 2 --inject NODE_DEGRADATION,NOISY_NEIGHBOR

# 6. Start the API
uvicorn clustersentinel.api.main:app --reload

# 7. Start the dashboard (new terminal)
streamlit run clustersentinel/ui/dashboard.py
```

## Configuration

Key `.env` settings:

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required for Claude backend |
| `LLM_PROVIDER` | `anthropic` | Set to `ollama` for local inference |
| `OLLAMA_MODEL` | `llama3` | Model name for Ollama |
| `DATABASE_URL` | `sqlite:///./clustersentinel.db` | SQLAlchemy DB URL |
| `ANOMALY_ENSEMBLE_THRESHOLD` | `0.65` | Score threshold for anomaly events |
| `METRIC_INTERVAL_SECONDS` | `30` | Simulation tick interval |

## Running the Simulator

```bash
# Basic: 4 nodes, 24 hours, no failures
python scripts/run_simulation.py --nodes 4 --duration-hours 24

# With failures injected at random timestamps
python scripts/run_simulation.py --inject NODE_DEGRADATION,CASCADING_FAILURE

# Real-time mode (sleeps between ticks)
python scripts/run_simulation.py --duration-hours 1 --realtime
```

Available failure modes: `NODE_DEGRADATION`, `NOISY_NEIGHBOR`, `STORAGE_REBALANCE`, `MEMORY_PRESSURE`, `NETWORK_SATURATION`, `DISK_PRE_FAILURE`, `CASCADING_FAILURE`

## Training Models

```bash
python scripts/train_models.py --baseline-hours 168  # 7 days
```

Trained artifacts are saved to `./models/`: `prophet.pkl`, `isolation_forest.pkl`, `lstm_autoencoder.pt`

## API Reference

```
POST  /api/v1/metrics/ingest          Ingest batch of NodeMetrics
GET   /api/v1/metrics/{node_id}       Get metric history for a node
GET   /api/v1/anomalies               List anomaly events (?severity=HIGH&limit=50)
GET   /api/v1/anomalies/{id}          Get specific anomaly event
POST  /api/v1/rca/trigger             Trigger RCA for anomaly_id (async)
GET   /api/v1/rca/status/{anomaly_id} Check RCA job status
GET   /api/v1/rca/{report_id}         Get RCA report
POST  /api/v1/feedback                Submit helpful/not-helpful rating
GET   /api/v1/health                  Health check
```

## How the RCA Agent Works

1. **detector_node** — fetches the 30-minute metric window for the anomalous node from SQLite
2. **correlator_node** — queries for other anomalies in the same cluster within ±10 minutes
3. **kb_retrieval** — embeds the anomaly context and retrieves relevant passages from ChromaDB (4 HCI knowledge base docs)
4. **explainer_node** — calls the LLM with a structured prompt including metric trajectory, correlated events, and KB context; parses JSON response into `RCAReport`
5. **feedback_node** — persists the report to DB; records user rating if provided

## Knowledge Base

Four Markdown documents in `clustersentinel/rca_agent/knowledge_base/docs/`:
- `hci_concepts.md` — HCI architecture, CVMs, replication, tiering
- `failure_patterns.md` — metric signatures for each of the 7 failure modes
- `metric_glossary.md` — normal ranges, warning/critical thresholds for all 15 metrics
- `remediation_runbook.md` — triage and recovery steps per failure type

Add new docs here and re-run `python scripts/seed_knowledge_base.py`.

## Feedback Loop

Every RCA report is persisted with a `confidence_score`. Users rate reports via the dashboard (👍/👎) or the `/api/v1/feedback` endpoint. Low-rated reports are stored in the `feedback` table and can be used to identify gaps in the knowledge base for improvement.

## Docker

A single image handles all modes via the `MODE` environment variable.

```bash
# Build
docker build -t clustersentinel:latest .

# Run API
docker run -p 8000:8000 -e MODE=api -e ANTHROPIC_API_KEY=your_key clustersentinel:latest

# Run Dashboard
docker run -p 8501:8501 -e MODE=dashboard clustersentinel:latest

# Run simulation inside container
docker run -e MODE=simulate clustersentinel:latest --nodes 4 --duration-hours 2

# Seed knowledge base
docker run -e MODE=seed-kb clustersentinel:latest
```

Available `MODE` values: `api` | `dashboard` | `simulate` | `seed-kb` | `train`

Data is persisted at `/data` inside the container. Mount a volume to retain it across restarts:
```bash
docker run -p 8000:8000 -v /mnt/data/clustersentinel:/data -e MODE=api clustersentinel:latest
```

## Kubernetes Deployment

Manifests are in `k8s/`. Requires a cluster with a `local-path` StorageClass (or adjust `k8s/pvc.yaml`).

```bash
# Deploy everything
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/api.yaml
kubectl apply -f k8s/dashboard.yaml
```

**Services are exposed as NodePort:**

| Service | Port | URL |
|---|---|---|
| API | 30800 | `http://<node-ip>:30800` |
| Dashboard | 30801 | `http://<node-ip>:30801` |
| API Swagger | 30800 | `http://<node-ip>:30800/docs` |

**Provide your Anthropic API key as a Secret:**
```bash
kubectl create secret generic clustersentinel-secrets \
  -n clustersentinel \
  --from-literal=ANTHROPIC_API_KEY=your_key_here
```

Or use Ollama by updating the ConfigMap:
```bash
kubectl patch configmap clustersentinel-config -n clustersentinel \
  --type merge -p '{"data":{"LLM_PROVIDER":"ollama","OLLAMA_BASE_URL":"http://your-ollama-host:11434"}}'
kubectl rollout restart deployment/clustersentinel-api -n clustersentinel
```

**Run a simulation from inside the cluster:**
```bash
kubectl exec -it -n clustersentinel \
  $(kubectl get pod -n clustersentinel -l app=clustersentinel-api -o name) \
  -- python scripts/run_simulation.py --nodes 4 --duration-hours 6 --inject NODE_DEGRADATION,CASCADING_FAILURE
```

**Useful commands:**
```bash
kubectl get all -n clustersentinel                                           # overview
kubectl logs -n clustersentinel -l app=clustersentinel-api -f               # API logs
kubectl logs -n clustersentinel -l app=clustersentinel-dashboard -f         # dashboard logs
kubectl rollout restart deployment/clustersentinel-api -n clustersentinel   # restart API
kubectl get pvc -n clustersentinel                                           # storage status
```

## License

MIT
