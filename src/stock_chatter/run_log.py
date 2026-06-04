from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .io_utils import append_jsonl

RUN_LOG_PATH = Path("reports/run_log.jsonl")


def new_run_id() -> str:
    return uuid4().hex[:12]


def log_run(event: str, *, run_id: str | None = None, path: str | Path = RUN_LOG_PATH, **fields) -> None:
    append_jsonl(
        path,
        [
            {
                "event": event,
                "run_id": run_id or new_run_id(),
                "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                **fields,
            }
        ],
    )
