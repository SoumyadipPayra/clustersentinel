FROM python:3.12-slim

WORKDIR /app

# System deps for Prophet (pystan) and torch
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer cache)
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        fastapi>=0.111 \
        uvicorn[standard]>=0.29 \
        streamlit>=1.35 \
        langchain>=0.2 \
        langgraph>=0.1 \
        langchain-anthropic>=0.1 \
        langchain-ollama>=0.1 \
        anthropic>=0.28 \
        chromadb>=0.5 \
        prophet>=1.1 \
        scikit-learn>=1.4 \
        "torch>=2.2" \
        sqlalchemy>=2.0 \
        pydantic>=2.7 \
        pydantic-settings>=2.3 \
        numpy>=1.26 \
        pandas>=2.2 \
        python-dotenv>=1.0 \
        rich>=13.7 \
        typer>=0.12 \
        httpx>=0.27 \
        plotly>=5.20

# Copy application code
COPY clustersentinel/ ./clustersentinel/
COPY scripts/ ./scripts/

# Install the package itself
RUN pip install --no-cache-dir -e . --no-deps

# Create data directories
RUN mkdir -p /data/db /data/chroma /data/models

# Default env (override via ConfigMap/Secret)
ENV DATABASE_URL=sqlite:////data/db/clustersentinel.db \
    CHROMA_PERSIST_DIR=/data/chroma \
    MODELS_DIR=/data/models \
    API_HOST=0.0.0.0 \
    API_PORT=8000

EXPOSE 8000 8501

# Entry point selects the service based on MODE env var
COPY docker-entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
