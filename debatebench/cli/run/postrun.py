"""Post-run aggregation for the `debatebench run` command."""
from __future__ import annotations

from pathlib import Path
import os

import typer

from ..common import console
from ..leaderboard import show_leaderboard
from ..plot import plot_command
from .estimate import write_timing_snapshot
from ..rate import rate_command
from ..summarize import summarize
from .types import RunSetup


def run_postrun(setup: RunSetup) -> None:
    """Generate summaries/plots and optional ratings/leaderboard."""
    opts = setup.options
    if not opts.quick_test:
        console.print(
            f"[green]Run complete. Writing summaries to {setup.viz_dir} and plots to {setup.plots_dir}"
        )
        summarize(debates_path=setup.debates_path, out_dir=setup.viz_dir)
        plot_command(viz_dir=setup.viz_dir, out_dir=setup.plots_dir)
    else:
        console.print("[green]Run complete.[/green]")
    max_workers = min(32, (os.cpu_count() or 4) * 4)
    per_model_cap = 4
    write_timing_snapshot(
        debates_path=setup.debates_path,
        out_path=setup.run_dir / "timing_snapshot.json",
        run_tag=setup.run_tag,
        max_workers=max_workers,
        per_model_cap=per_model_cap,
    )
    if opts.postrate:
        console.print(f"[cyan]Recomputing ratings and showing leaderboard (top 10).[/cyan]")
        rate_command(debates_path=setup.debates_path, config_path=opts.config_path, ratings_path=setup.ratings_path)
        show_leaderboard(ratings_path=setup.ratings_path, top=10)

    if opts.postupload:
        # Import lazily to avoid requiring boto3 unless postupload is enabled.
        from ..upload import upload_results_command  # noqa: WPS433
        from botocore.exceptions import BotoCoreError, NoCredentialsError  # type: ignore

        bucket = opts.postupload_bucket or setup.settings.s3_bucket
        if not bucket:
            console.print(
                "[yellow]Postupload skipped: no bucket configured. Set DEBATEBENCH_S3_BUCKET (or pass --postupload-bucket) to enable uploads.[/yellow]"
            )
            return

        # If user didn't pass a prefix and no env prefix is set, default to runs/<tag>.
        raw_prefix = opts.postupload_prefix or setup.settings.s3_prefix or f"runs/{setup.run_tag}"
        base_prefix = raw_prefix.strip("/")

        profile = opts.postupload_profile or (None if setup.settings.s3_endpoint else setup.settings.aws_profile)
        region = opts.postupload_region or setup.settings.s3_region

        def _join_prefix(*parts: str) -> str:
            segs = [p.strip("/") for p in parts if p and p.strip("/")]
            return "/".join(segs)

        console.print(
            f"[cyan]Postupload enabled:[/cyan] uploading debates to s3://{bucket}/{_join_prefix(base_prefix, setup.debates_path.name)}"
        )
        try:
            upload_results_command(
                source=setup.debates_path,
                bucket=bucket,
                prefix=base_prefix,
                profile=profile,
                region=region,
                dry_run=opts.postupload_dry_run,
            )
        except (NoCredentialsError, BotoCoreError, typer.BadParameter, Exception) as e:  # noqa: BLE001
            console.print(
                f"[yellow]Postupload failed (continuing without aborting run): {e}[/yellow]"
            )
            return

        if opts.postupload_include_artifacts:
            artifact_sources: list[Path] = [setup.run_dir, setup.viz_dir, setup.plots_dir]
            if setup.ratings_path.exists():
                artifact_sources.append(setup.ratings_path)
            for src in artifact_sources:
                artifact_prefix = _join_prefix(base_prefix, src.name)
                console.print(
                    f"[cyan]Postupload:[/cyan] uploading {src} to s3://{bucket}/{artifact_prefix}"
                )
                try:
                    upload_results_command(
                        source=src,
                        bucket=bucket,
                        prefix=artifact_prefix,
                        profile=profile,
                        region=region,
                        dry_run=opts.postupload_dry_run,
                    )
                except (NoCredentialsError, BotoCoreError, typer.BadParameter, Exception) as e:  # noqa: BLE001
                    console.print(
                        f"[yellow]Postupload failed for {src} (continuing): {e}[/yellow]"
                    )


__all__ = ["run_postrun"]
