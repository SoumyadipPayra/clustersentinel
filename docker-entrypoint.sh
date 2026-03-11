#!/bin/bash
set -e

MODE="${MODE:-api}"

case "$MODE" in
  api)
    echo "Starting ClusterSentinel API on port ${API_PORT:-8000}..."
    exec uvicorn clustersentinel.api.main:app \
      --host "${API_HOST:-0.0.0.0}" \
      --port "${API_PORT:-8000}"
    ;;
  dashboard)
    echo "Starting ClusterSentinel Dashboard on port 8501..."
    exec streamlit run clustersentinel/ui/dashboard.py \
      --server.port 8501 \
      --server.address 0.0.0.0 \
      --server.headless true
    ;;
  simulate)
    echo "Running simulation..."
    exec python scripts/run_simulation.py "$@"
    ;;
  seed-kb)
    echo "Seeding knowledge base..."
    exec python scripts/seed_knowledge_base.py
    ;;
  train)
    echo "Training models..."
    exec python scripts/train_models.py "$@"
    ;;
  *)
    echo "Unknown MODE: $MODE. Valid: api | dashboard | simulate | seed-kb | train"
    exit 1
    ;;
esac
