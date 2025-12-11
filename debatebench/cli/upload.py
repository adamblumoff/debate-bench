"""`debatebench upload-results` command."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import boto3
import typer
from botocore.config import Config
from botocore.exceptions import BotoCoreError, NoCredentialsError

from .common import console
from ..settings import load_settings


def upload_results_command(
    source: Path = typer.Option(
        Path("results"), help="File or directory to upload recursively."
    ),
    bucket: Optional[str] = typer.Option(
        None,
        help="Destination bucket name. Defaults from env (DEBATEBENCH_S3_BUCKET/S3_BUCKET) or 'debatebench-results'.",
    ),
    prefix: str = typer.Option(
        "", help="Key prefix inside the bucket (omit leading slash)."
    ),
    profile: Optional[str] = typer.Option(
        None, help="AWS profile name to use (falls back to env/default)."
    ),
    region: Optional[str] = typer.Option(
        None, help="AWS region override (otherwise boto3 default chain)."
    ),
    endpoint_url: Optional[str] = typer.Option(
        None,
        help="Custom S3-compatible endpoint URL (e.g., Railway Bucket endpoint). Defaults from env (DEBATEBENCH_S3_ENDPOINT/S3_ENDPOINT/AWS_S3_ENDPOINT).",
    ),
    force_path_style: Optional[bool] = typer.Option(
        None,
        help="Force path-style addressing for S3-compatible endpoints. Defaults from env (DEBATEBENCH_S3_FORCE_PATH_STYLE/S3_FORCE_PATH_STYLE) or inferred for Railway.",
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

    settings = load_settings()
    bucket_name = bucket or settings.s3_bucket
    if not bucket_name:
        raise typer.BadParameter(
            "No bucket provided. Set DEBATEBENCH_S3_BUCKET (or pass --bucket)."
        )

    endpoint = endpoint_url or settings.s3_endpoint
    path_style = force_path_style if force_path_style is not None else settings.s3_force_path_style
    if path_style is None and endpoint and "railway" in endpoint:
        path_style = True

    session_kwargs = {}
    if profile:
        session_kwargs["profile_name"] = profile
    elif settings.aws_profile and not endpoint:
        # Only auto-use a profile for AWS-native endpoints.
        session_kwargs["profile_name"] = settings.aws_profile
    if region:
        session_kwargs["region_name"] = region
    elif settings.s3_region:
        session_kwargs["region_name"] = settings.s3_region
    session = boto3.Session(**session_kwargs)
    client_kwargs = {}
    if endpoint:
        client_kwargs["endpoint_url"] = endpoint
    if path_style:
        client_kwargs["config"] = Config(s3={"addressing_style": "path"})
    s3 = session.client("s3", **client_kwargs)

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

    console.print(f"[cyan]Prepared {len(files)} uploads to s3://{bucket_name}/{prefix or ''}[/cyan]")
    if dry_run:
        for p, k in files:
            console.print(f"DRY-RUN {p} -> s3://{bucket_name}/{k}")
        return

    for idx, (path, key) in enumerate(files, start=1):
        console.print(f"[blue]{idx}/{len(files)}[/blue] {path} -> s3://{bucket_name}/{key}")
        try:
            s3.upload_file(
                Filename=str(path),
                Bucket=bucket_name,
                Key=key,
                ExtraArgs={"ServerSideEncryption": "AES256"},
            )
        except (BotoCoreError, NoCredentialsError) as e:
            raise typer.BadParameter(f"AWS upload failed: {e}") from e

    console.print(f"[green]Uploaded {len(files)} files to s3://{bucket_name}/{prefix or ''}[/green]")


__all__ = ["upload_results_command"]
