"""CLI: run the cluster simulator for N hours and stream metrics to DB.

Usage:
    python scripts/run_simulation.py --nodes 4 --duration-hours 24 --inject NODE_DEGRADATION,NOISY_NEIGHBOR
"""

from __future__ import annotations
import random
from datetime import datetime, timedelta
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
from clustersentinel.simulator.cluster import ClusterSimulator
from clustersentinel.simulator.failure_injector import FailureMode
from clustersentinel.storage.db import init_db, get_session
from clustersentinel.storage import repository as repo
from clustersentinel.config import settings

app = typer.Typer()
console = Console()


@app.command()
def run(
    nodes: int = typer.Option(settings.default_cluster_nodes, help="Number of cluster nodes"),
    duration_hours: float = typer.Option(1.0, help="Simulation duration in hours"),
    inject: str = typer.Option("", help="Comma-separated failure modes to inject"),
    seed: int = typer.Option(42, help="Random seed for reproducibility"),
    realtime: bool = typer.Option(False, help="Sleep between ticks to simulate real time"),
):
    """Run cluster simulation and persist metrics to DB."""
    init_db()
    sim = ClusterSimulator(
        num_nodes=nodes,
        interval_seconds=settings.metric_interval_seconds,
        seed=seed,
    )

    start = datetime.utcnow()

    # Schedule requested failure injections at random times during the run
    if inject:
        modes = [FailureMode(m.strip()) for m in inject.split(",")]
        for mode in modes:
            offset_minutes = random.randint(5, max(6, int(duration_hours * 60 * 0.4)))
            inject_time = start + timedelta(minutes=offset_minutes)
            sim.inject_failure(mode, inject_time)
            console.print(f"[yellow]Scheduled {mode.value} at +{offset_minutes}min[/yellow]")

    total_ticks = int(duration_hours * 3600 / settings.metric_interval_seconds)
    tick_count = 0

    with Progress(SpinnerColumn(), *Progress.get_default_columns(), TimeElapsedColumn()) as progress:
        task = progress.add_task(f"Simulating {nodes} nodes for {duration_hours}h...", total=total_ticks)

        for node_metrics, cluster_metrics in sim.run(start, duration_hours):
            with get_session() as session:
                for nm in node_metrics:
                    repo.save_node_metrics(session, nm)

            tick_count += 1
            progress.advance(task)

            if realtime:
                import time
                time.sleep(settings.metric_interval_seconds)

    console.print(f"[green]✓ Simulation complete: {tick_count} ticks, {tick_count * nodes} metric records[/green]")


if __name__ == "__main__":
    app()
