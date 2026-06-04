from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path
from typing import Iterable


def ensure_parent(path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def read_jsonl(path: str | Path) -> list[dict]:
    target = Path(path)
    if not target.exists():
        return []
    rows: list[dict] = []
    with target.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def append_jsonl(path: str | Path, rows: Iterable[dict]) -> int:
    target = ensure_parent(path)
    count = 0
    with target.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
            count += 1
    return count


def append_new_jsonl(path: str | Path, rows: Iterable[dict], id_key: str = "id") -> int:
    existing = {row.get(id_key) for row in read_jsonl(path) if row.get(id_key)}
    fresh = []
    for row in rows:
        row_id = row.get(id_key)
        if row_id and row_id not in existing:
            existing.add(row_id)
            fresh.append(row)
    return append_jsonl(path, fresh)


def write_json(path: str | Path, value: dict) -> None:
    target = ensure_parent(path)
    _atomic_write_text(target, json.dumps(value, indent=2, sort_keys=True) + "\n")


def read_json(path: str | Path) -> dict:
    target = Path(path)
    if not target.exists():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


def read_csv_dicts(path: str | Path) -> list[dict[str, str]]:
    target = Path(path)
    if not target.exists():
        return []
    with target.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_dicts(path: str | Path, rows: Iterable[dict], fieldnames: list[str]) -> int:
    target = ensure_parent(path)
    count = 0
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    os.replace(tmp_name, target)
    return count


def write_text(path: str | Path, text: str) -> None:
    target = ensure_parent(path)
    _atomic_write_text(target, text)


def _atomic_write_text(target: Path, text: str) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(tmp_name, target)
