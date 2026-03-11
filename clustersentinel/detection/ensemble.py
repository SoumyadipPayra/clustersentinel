"""Ensemble detector: fuses scores from Prophet, IsolationForest, and LSTM.

Emits an AnomalyEvent only when the weighted ensemble score exceeds threshold.
"""

from __future__ import annotations
import uuid
from collections import defaultdict
from datetime import datetime
import pandas as pd
from clustersentinel.simulator.schemas import AnomalyEvent, AnomalyScore, Severity
from clustersentinel.config import settings
from .prophet_detector import ProphetDetector
from .isolation_forest import IsolationForestDetector
from .lstm_autoencoder import LSTMAutoencoderDetector
from .base import DetectorBase


_WEIGHTS = {"prophet": 0.35, "isolation": 0.30, "lstm": 0.35}


def _severity_from_score(score: float) -> Severity:
    if score >= 0.90:
        return Severity.CRITICAL
    if score >= 0.75:
        return Severity.HIGH
    if score >= 0.60:
        return Severity.MEDIUM
    return Severity.LOW


class EnsembleDetector:
    """Combines three detectors with configurable weights."""

    def __init__(
        self,
        prophet: ProphetDetector | None = None,
        isolation: IsolationForestDetector | None = None,
        lstm: LSTMAutoencoderDetector | None = None,
        threshold: float | None = None,
    ) -> None:
        self.prophet = prophet or ProphetDetector()
        self.isolation = isolation or IsolationForestDetector()
        self.lstm = lstm or LSTMAutoencoderDetector()
        self.threshold = threshold or settings.anomaly_ensemble_threshold

    def fit(self, df: pd.DataFrame) -> None:
        """Fit all three detectors on baseline data."""
        self.prophet.fit(df)
        self.isolation.fit(df)
        self.lstm.fit(df)

    def detect(
        self,
        df: pd.DataFrame,
        cluster_id: str,
        ts: datetime | None = None,
    ) -> list[AnomalyEvent]:
        """Run all detectors and fuse scores into AnomalyEvents."""
        ts = ts or datetime.utcnow()

        prophet_scores = self.prophet.detect(df)
        isolation_scores = self.isolation.detect(df)
        lstm_scores = self.lstm.detect(df)

        # Group by node_id, accumulate per-detector max scores
        node_prophet: dict[str, list[AnomalyScore]] = defaultdict(list)
        node_isolation: dict[str, list[AnomalyScore]] = defaultdict(list)
        node_lstm: dict[str, list[AnomalyScore]] = defaultdict(list)

        for s in prophet_scores:
            node_prophet[s.node_id].append(s)
        for s in isolation_scores:
            node_isolation[s.node_id].append(s)
        for s in lstm_scores:
            node_lstm[s.node_id].append(s)

        all_nodes = set(node_prophet) | set(node_isolation) | set(node_lstm)
        events: list[AnomalyEvent] = []

        for node_id in all_nodes:
            p_score = max((s.score for s in node_prophet[node_id]), default=0.0)
            i_score = max((s.score for s in node_isolation[node_id]), default=0.0)
            l_score = max((s.score for s in node_lstm[node_id]), default=0.0)

            ensemble = (
                _WEIGHTS["prophet"] * p_score
                + _WEIGHTS["isolation"] * i_score
                + _WEIGHTS["lstm"] * l_score
            )

            if ensemble < self.threshold:
                continue

            affected = list({
                s.metric
                for scores in (node_prophet[node_id], node_isolation[node_id], node_lstm[node_id])
                for s in scores
            })

            events.append(AnomalyEvent(
                id=str(uuid.uuid4()),
                timestamp=ts,
                node_id=node_id,
                cluster_id=cluster_id,
                affected_metrics=affected,
                severity=_severity_from_score(ensemble),
                prophet_score=round(p_score, 4),
                isolation_score=round(i_score, 4),
                lstm_score=round(l_score, 4),
                ensemble_score=round(ensemble, 4),
                description=f"Ensemble anomaly detected on {node_id}: score={ensemble:.3f}",
            ))

        return events
