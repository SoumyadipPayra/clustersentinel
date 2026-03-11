"""CLI: load knowledge base docs into ChromaDB.

Usage:
    python scripts/seed_knowledge_base.py
"""

import typer
from rich.console import Console
from clustersentinel.rca_agent.knowledge_base.loader import seed_knowledge_base

app = typer.Typer()
console = Console()


@app.command()
def seed():
    """Load all .md docs from rca_agent/knowledge_base/docs/ into ChromaDB."""
    console.print("[bold]Seeding knowledge base...[/bold]")
    added = seed_knowledge_base()
    console.print(f"[green]✓ Added {added} new chunks to ChromaDB[/green]")


if __name__ == "__main__":
    app()
