"""`debatebench sample-debates` command."""

from __future__ import annotations

from pathlib import Path
import random
from typing import Optional

import typer

from ..storage import load_debate_records
from .common import console


def _debates_path_from_run_tag(run_tag: str) -> Path:
    return Path("results") / f"debates_{run_tag}.jsonl"


def _blockquote(text: str) -> str:
    if not text:
        return "> "
    cleaned = text.rstrip("\n")
    return "> " + cleaned.replace("\n", "\n> ")


def sample_debates(
    run_tag: Optional[str] = typer.Option(
        None,
        "--run-tag",
        help="Run tag used to locate results/debates_<tag>.jsonl.",
    ),
    debates_path: Path = typer.Option(
        Path("results/debates.jsonl"),
        help="Path to debates file (ignored if --run-tag is provided).",
    ),
    count: int = typer.Option(5, "--count", min=1, help="Number of debates to sample."),
    seed: Optional[int] = typer.Option(
        None, "--seed", help="Optional RNG seed for reproducible sampling."
    ),
    out_path: Optional[Path] = typer.Option(
        None,
        "--out",
        help="Output Markdown path (defaults to results/run_<tag>/sample_debates.md).",
    ),
):
    """
    Sample debates from a run and write a readable Markdown report.
    """
    path_in = debates_path
    if run_tag:
        path_in = _debates_path_from_run_tag(run_tag)

    if not path_in.exists():
        console.print(f"[red]Debates file not found: {path_in}")
        raise typer.Exit(code=1)

    debates = load_debate_records(path_in)
    if not debates:
        console.print(f"[red]No debates found at {path_in}")
        raise typer.Exit(code=1)

    if count >= len(debates):
        sample = debates[:]
    else:
        rng = random.Random(seed)
        sample = rng.sample(debates, count)

    if out_path is None:
        if run_tag:
            out_path = Path("results") / f"run_{run_tag}" / "sample_debates.md"
        else:
            out_path = Path("results") / "sample_debates.md"

    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    header_tag = run_tag or "custom"
    lines.append(f"# DebateBench Sample ({header_tag})")
    lines.append("")
    lines.append(f"- Source: `{path_in}`")
    lines.append(f"- Sample size: {len(sample)}")
    if seed is not None:
        lines.append(f"- Seed: {seed}")
    lines.append("")

    for idx, record in enumerate(sample, start=1):
        transcript = record.transcript
        lines.append(f"## Debate {idx}: {transcript.debate_id}")
        lines.append("")
        lines.append(f"- Created: {record.created_at}")
        lines.append(f"- Motion: {transcript.topic.motion}")
        lines.append(f"- Pro model: `{transcript.pro_model_id}`")
        lines.append(f"- Con model: `{transcript.con_model_id}`")
        lines.append(f"- Winner: **{record.aggregate.winner}**")
        lines.append("")
        if record.judges:
            lines.append("### Judges")
            for judge in record.judges:
                lines.append(
                    f"- `{judge.judge_id}` winner={judge.winner} pro={judge.pro.scores} con={judge.con.scores}"
                )
            lines.append("")
        lines.append("### Transcript")
        for turn in transcript.turns:
            speaker = turn.speaker.upper()
            stage = turn.stage
            lines.append(f"#### Turn {turn.index} ({speaker} - {stage})")
            lines.append(_blockquote(turn.content))
            lines.append("")

    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    console.print(f"[green]Wrote {len(sample)} debates to {out_path}")


__all__ = ["sample_debates"]
