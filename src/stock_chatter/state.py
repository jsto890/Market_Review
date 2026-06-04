from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .io_utils import read_json, write_json

STATE_PATH = Path("data/state/monitor_state.json")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_state(path: str | Path = STATE_PATH) -> dict:
    return read_json(path)


def save_state(state: dict, path: str | Path = STATE_PATH) -> None:
    write_json(path, state)


def get_timestamp(state: dict, key: str) -> datetime | None:
    value = state.get(key)
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def set_timestamp(state: dict, key: str, value: datetime | None = None) -> None:
    value = value or datetime.now(timezone.utc)
    state[key] = value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def set_max_timestamp(state: dict, key: str, value: datetime | None) -> None:
    if value is None:
        return
    existing = get_timestamp(state, key)
    if existing is None or value.astimezone(timezone.utc) > existing.astimezone(timezone.utc):
        set_timestamp(state, key, value)
