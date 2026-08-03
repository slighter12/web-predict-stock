"""Shared logging setup for command-line scripts."""

from __future__ import annotations

import logging
import os


def configure_cli_logging() -> None:
    """Configure the process root logger for a command-line entrypoint."""

    logging.basicConfig(
        level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
