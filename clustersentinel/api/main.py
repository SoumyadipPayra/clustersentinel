"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from clustersentinel.storage.db import init_db
from .routes import metrics, anomalies, rca, feedback


def create_app() -> FastAPI:
    app = FastAPI(
        title="ClusterSentinel API",
        description="AI-powered anomaly detection and RCA for HCI clusters",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def startup():
        init_db()

    @app.get("/api/v1/health", tags=["health"])
    def health():
        return {"status": "ok"}

    app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["metrics"])
    app.include_router(anomalies.router, prefix="/api/v1/anomalies", tags=["anomalies"])
    app.include_router(rca.router, prefix="/api/v1/rca", tags=["rca"])
    app.include_router(feedback.router, prefix="/api/v1/feedback", tags=["feedback"])

    return app


app = create_app()
