"""Service entrypoint for running Streamlit alongside the background scheduler."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Final

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_PORT: Final[str] = "8501"


def _scheduler_enabled() -> bool:
    return os.getenv("ENABLE_INTERNAL_SCHEDULER", "false").strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    from scheduler.jobs import start_scheduler

    scheduler = start_scheduler() if _scheduler_enabled() else None
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "dashboard/app.py",
        "--server.port",
        os.getenv("PORT", DEFAULT_PORT),
        "--server.address",
        "0.0.0.0",
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]

    try:
        return subprocess.call(command)
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


if __name__ == "__main__":
    raise SystemExit(main())
