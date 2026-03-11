"""CLI: train or retrain all detection models on baseline data.

Usage:
    python scripts/train_models.py --baseline-hours 168
"""

from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import typer
from rich.console import Console
from clustersentinel.storage.db import init_db, get_session
from clustersentinel.storage import repository as repo
from clustersentinel.simulator.cluster import ClusterSimulator
from clustersentinel.detection.prophet_detector import ProphetDetector
from clustersentinel.detection.isolation_forest import IsolationForestDetector
from clustersentinel.detection.lstm_autoencoder import LSTMAutoencoderDetector
from clustersentinel.config import settings

app = typer.Typer()
console = Console()


def _load_or_generate_baseline(hours: int, nodes: int) -> pd.DataFrame:
    """Load baseline data from DB, or generate fresh synthetic data if insufficient."""
    init_db()
    since = datetime.utcnow() - timedelta(hours=hours)

    # Try to load from DB
    all_rows = []
    node_ids = [f"node-{i:02d}" for i in range(1, nodes + 1)]
    with get_session() as session:
        for node_id in node_ids:
            metrics = repo.get_metrics_window(session, node_id, datetime.utcnow(), window_minutes=hours * 60)
            for m in metrics:
                all_rows.append(m.model_dump())

    if len(all_rows) >= 100:
        console.print(f"[blue]Loaded {len(all_rows)} records from DB[/blue]")
        return pd.DataFrame(all_rows)

    # Generate fresh baseline data
    console.print(f"[yellow]Insufficient DB data — generating {hours}h of synthetic baseline[/yellow]")
    sim = ClusterSimulator(num_nodes=nodes, seed=0)
    start = datetime.utcnow() - timedelta(hours=hours)
    rows = []
    for node_metrics, _ in sim.run(start, hours):
        for nm in node_metrics:
            rows.append(nm.model_dump())
    console.print(f"[blue]Generated {len(rows)} baseline records[/blue]")
    return pd.DataFrame(rows)


@app.command()
def train(
    baseline_hours: int = typer.Option(168, help="Hours of baseline data to train on (default: 7 days)"),
    nodes: int = typer.Option(settings.default_cluster_nodes, help="Number of nodes"),
    models_dir: Path = typer.Option(settings.models_dir, help="Directory to save model artifacts"),
):
    """Train Prophet, IsolationForest, and LSTM models on baseline cluster data."""
    models_dir.mkdir(parents=True, exist_ok=True)
    df = _load_or_generate_baseline(baseline_hours, nodes)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    console.print("[bold]Training ProphetDetector...[/bold]")
    prophet = ProphetDetector()
    prophet.fit(df)
    prophet.save(str(models_dir / "prophet.pkl"))
    console.print("[green]✓ Prophet saved[/green]")

    console.print("[bold]Training IsolationForestDetector...[/bold]")
    iso = IsolationForestDetector()
    iso.fit(df)
    iso.save(str(models_dir / "isolation_forest.pkl"))
    console.print("[green]✓ IsolationForest saved[/green]")

    console.print("[bold]Training LSTMAutoencoderDetector...[/bold]")
    lstm = LSTMAutoencoderDetector(epochs=10)
    lstm.fit(df)
    lstm.save(str(models_dir / "lstm_autoencoder.pt"))
    console.print("[green]✓ LSTM saved[/green]")

    console.print(f"\n[bold green]All models saved to {models_dir}[/bold green]")


if __name__ == "__main__":
    app()
