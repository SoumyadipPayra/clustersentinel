"""Abstract base class for all anomaly detectors."""

from __future__ import annotations
from abc import ABC, abstractmethod
import pandas as pd
from clustersentinel.simulator.schemas import AnomalyScore


class DetectorBase(ABC):
    """All detectors must implement fit() and detect()."""

    @abstractmethod
    def fit(self, df: pd.DataFrame) -> None:
        """Train the detector on clean baseline data.

        Args:
            df: DataFrame with a 'timestamp' column plus metric columns.
                One row per (node_id, timestamp).
        """

    @abstractmethod
    def detect(self, df: pd.DataFrame) -> list[AnomalyScore]:
        """Score a window of recent metrics.

        Args:
            df: Same schema as fit(); typically the last N timesteps.

        Returns:
            List of AnomalyScore, one per anomalous (node, metric) pair.
        """

    def save(self, path: str) -> None:
        """Persist model artifacts. Override in subclasses."""

    def load(self, path: str) -> None:
        """Load persisted model artifacts. Override in subclasses."""
