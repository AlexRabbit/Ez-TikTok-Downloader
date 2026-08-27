from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

SCHEMA_VERSION = 1
ENTRY_FIELDS = frozenset({
    "play_url", "images", "username", "video_id", "create_time", "profile_uid", "content_type",
})


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_entry(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return bool(value.get("play_url") or (value.get("images") and len(value.get("images", [])) > 0))


def _normalize_entry(entry: dict) -> dict:
    out = dict(entry)
    if "content_type" not in out:
        out["content_type"] = "video"
    return out


def _parse_raw(data: Any) -> dict[str, dict]:
    """Accept legacy flat map or schema v1 wrapper."""
    if not isinstance(data, dict):
        return {}

    if "schema_version" in data and "entries" in data:
        entries = data.get("entries") or {}
        if isinstance(entries, dict):
            return {k: _normalize_entry(v) for k, v in entries.items() if _is_entry(v)}
        return {}

    # Legacy flat: video_id -> entry
    if any(_is_entry(v) for v in data.values() if isinstance(v, dict)):
        return {k: _normalize_entry(v) for k, v in data.items() if isinstance(v, dict) and _is_entry(v)}

    return {}


def load_cache(path: str) -> dict[str, dict]:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return _parse_raw(json.load(f))
    except Exception:
        return {}


def save_cache(entries: dict[str, dict], path: str) -> None:
    wrapper = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": _utc_now_iso(),
        "app": "ez-tiktok-downloader",
        "entries": {k: _normalize_entry(v) for k, v in entries.items()},
    }
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(wrapper, f, indent=2)
    except Exception as e:
        print(f"Warning: could not save cache: {e}")


def merge_entries(base: dict[str, dict], incoming: dict[str, dict]) -> dict[str, dict]:
    merged = dict(base)
    for vid, entry in incoming.items():
        if vid not in merged:
            merged[vid] = _normalize_entry(entry)
        else:
            # Prefer incoming if it has play_url/images the base lacks
            old = merged[vid]
            new = _normalize_entry(entry)
            if not old.get("play_url") and new.get("play_url"):
                merged[vid] = new
            elif not old.get("images") and new.get("images"):
                merged[vid] = new
    return merged


def export_cache_file(entries: dict[str, dict], out_path: str) -> None:
    save_cache(entries, out_path)
    print(f"Cache exported to {out_path} ({len(entries)} entries, schema v1)")


def import_cache_file(path: str, merge: bool = True) -> dict[str, dict]:
    incoming = load_cache(path)
    print(f"Imported {len(incoming)} entries from {path}")
    return incoming


def load_cache_from_any(path: str) -> dict[str, dict]:
    """Load from file that may be legacy flat, v1 wrapper, or userscript export."""
    return load_cache(path)
