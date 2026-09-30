"""Slowly changing (type 2) histories kept as JSON: a change in a tracked field closes the current version and opens a new one."""

import json
from pathlib import Path


def load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def record(path: Path, rows: list[dict], key: str, tracked: list[str], observed: str, overwrite: list[str] | None = None) -> list[dict]:
    """Add one observation of each row to the history at path and return it.

    A version runs from valid_from up to, not including, valid_to; the current one has valid_to null and is_current true.
    Fields in overwrite describe the current version, not the thing tracked, so an unchanged row updates them in place;
    an empty new value keeps the old one. last_checked is the latest observation that confirmed the version."""
    overwrite = overwrite or []
    history = load(path)
    current = {h[key]: h for h in history if h["is_current"]}
    for row in rows:
        values = {k: row.get(k) for k in tracked}
        now = current.get(row[key])
        if now and all(now.get(k) == v for k, v in values.items()):
            now["last_checked"] = observed
            now.update({k: row[k] for k in overwrite if row.get(k)})
            continue
        if now:
            now.update(valid_to=observed, is_current=False)
        extra = {k: v for k, v in row.items() if k != key and k not in tracked and k not in overwrite}
        history.append(
            {
                key: row[key],
                **extra,
                **values,
                **{k: row.get(k, "") for k in overwrite},
                "valid_from": observed,
                "valid_to": None,
                "is_current": True,
                "last_checked": observed,
            }
        )
    history.sort(key=lambda h: (h[key], h["valid_from"]))
    path.write_text(json.dumps(history, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return history
