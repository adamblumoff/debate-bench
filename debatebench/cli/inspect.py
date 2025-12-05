"""`debatebench inspect-debate` command."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from ..storage import load_debate_records
from .common import console


def _find_latest_debates_file() -> Optional[Path]:
    results_dir = Path("results")
    candidates = list(results_dir.glob("debates_*.jsonl"))
    if candidates:
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0]
    default = results_dir / "debates.jsonl"
    return default if default.exists() else None


def inspect_debate(
    debate_id: Optional[str] = typer.Argument(
        None, help="Debate ID to inspect (omit to show the latest debate)."
    ),
    debates_path: Path = typer.Option(
        Path("results/debates.jsonl"), help="Path to debates file."
    ),
    latest: bool = typer.Option(
        False,
        "--latest",
        help="Automatically pick the newest debates_*.jsonl file and the newest debate ID.",
    ),
):
    """
    Print a single debate and its judge decisions.
    """
    path_in = debates_path
    if latest or debate_id is None:
        auto = _find_latest_debates_file()
        if auto:
            path_in = auto

    debates = load_debate_records(path_in)
    if not debates:
        console.print(f"[red]No debates found at {path_in}")
        raise typer.Exit(code=1)

    record = None
    if debate_id:
        matches = [d for d in debates if d.transcript.debate_id == debate_id]
        if matches:
            record = matches[0]
    else:
        try:
            record = max(debates, key=lambda d: d.created_at)
        except Exception:
            record = debates[-1] if debates else None

    if record is None:
        console.print(f"[red]Debate {debate_id or ''} not found in {path_in}")
        raise typer.Exit(code=1)

    console.print(f"[green]Using debates file: {path_in}")
    console.print(f"[bold]Debate {record.transcript.debate_id}[/bold]")
    console.print(f"Motion: {record.transcript.topic.motion}")
    console.print(f"Pro: {record.transcript.pro_model_id} | Con: {record.transcript.con_model_id}")
    console.print("Transcript:")
    for turn in record.transcript.turns:
        console.print(f"  [{turn.speaker}] ({turn.stage}) {turn.content}")
    console.print("Judges:")
    for j in record.judges:
        console.print(f"  {j.judge_id}: winner={j.winner}, pro={j.pro.scores}, con={j.con.scores}")
    console.print(f"Aggregate winner: {record.aggregate.winner}")


__all__ = ["inspect_debate"]
