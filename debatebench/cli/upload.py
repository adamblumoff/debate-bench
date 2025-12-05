"""`debatebench upload-results` command."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import boto3
import typer
from botocore.exceptions import BotoCoreError, NoCredentialsError

from .common import console


def upload_results_command(
    source: Path = typer.Option(
        Path("results"), help="File or directory to upload recursively."
    ),
    bucket: str = typer.Option(..., help="Destination S3 bucket name."),
    prefix: str = typer.Option(
        "", help="Key prefix inside the bucket (omit leading slash)."
    ),
    profile: Optional[str] = typer.Option(
        None, help="AWS profile name to use (falls back to env/default)."
    ),
    region: Optional[str] = typer.Option(
        None, help="AWS region override (otherwise boto3 default chain)."
    ),
    dry_run: bool = typer.Option(False, help="List uploads without sending."),
):
    """
    Upload a file or an entire directory tree to S3 for safekeeping.

    Credentials are taken from the standard AWS chain (env vars, shared
    credentials/config, or the provided --profile). Server-side encryption uses
    AWS-managed keys (SSE-S3) by default.
    """
    if not source.exists():
        raise typer.BadParameter(f"Source not found: {source}")

    session_kwargs = {}
    if profile:
        session_kwargs["profile_name"] = profile
    if region:
        session_kwargs["region_name"] = region
    session = boto3.Session(**session_kwargs)
    s3 = session.client("s3")

    files: list[tuple[Path, str]] = []
    if source.is_file():
        rel = source.name
        key = "/".join([p for p in [prefix, rel] if p])
        files.append((source, key))
    else:
        for path in source.rglob("*"):
            if path.is_file():
                rel = path.relative_to(source)
                key = "/".join([p for p in [prefix, rel.as_posix()] if p])
                files.append((path, key))

    if not files:
        console.print(f"[yellow]No files to upload under {source}.[/yellow]")
        return

    console.print(f"[cyan]Prepared {len(files)} uploads to s3://{bucket}/{prefix or ''}[/cyan]")
    if dry_run:
        for p, k in files:
            console.print(f"DRY-RUN {p} -> s3://{bucket}/{k}")
        return

    for idx, (path, key) in enumerate(files, start=1):
        console.print(f"[blue]{idx}/{len(files)}[/blue] {path} -> s3://{bucket}/{key}")
        try:
            s3.upload_file(
                Filename=str(path),
                Bucket=bucket,
                Key=key,
                ExtraArgs={"ServerSideEncryption": "AES256"},
            )
        except (BotoCoreError, NoCredentialsError) as e:
            raise typer.BadParameter(f"AWS upload failed: {e}") from e

    console.print(f"[green]Uploaded {len(files)} files to s3://{bucket}/{prefix or ''}[/green]")


__all__ = ["upload_results_command"]
