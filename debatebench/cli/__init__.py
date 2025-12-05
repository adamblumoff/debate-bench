"""CLI package initializer for DebateBench.

Exposes the Typer application and entrypoint for compatibility with the
existing console script target (`debatebench.cli:main`).
"""

from .app import app, main  # noqa: F401

__all__ = ["app", "main"]
