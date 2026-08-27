from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional

CONFIG_FILENAME = "config.json"
SESSIONID_FILENAME = "sessionid.txt"
COOKIES_FILENAME = "cookies.txt"

DEFAULTS = {
    "output_dir": "profiles",
    "cache_file": "link_cache.json",
    "batch_delay_sec": 2,
    "naming_template": "{date} - {profile_uid} - {username} - {video_id}{ext}",
    "request_timeout": 25,
    "poll_interval": 1.0,
    "poll_attempts": 60,
    "clipboard_monitor": False,
    "clipboard_poll_sec": 1.5,
    "clipboard_dedupe_sec": 30,
}


@dataclass
class AppConfig:
    output_dir: str = "profiles"
    cache_file: str = "link_cache.json"
    batch_delay_sec: float = 2
    naming_template: str = "{date} - {profile_uid} - {username} - {video_id}{ext}"
    request_timeout: int = 25
    poll_interval: float = 1.0
    poll_attempts: int = 60
    clipboard_monitor: bool = False
    clipboard_poll_sec: float = 1.5
    clipboard_dedupe_sec: float = 30
    base_dir: str = field(default_factory=os.getcwd)

    @property
    def output_path(self) -> str:
        p = self.output_dir
        if os.path.isabs(p):
            return p
        return os.path.join(self.base_dir, p)

    @property
    def cache_path(self) -> str:
        p = self.cache_file
        if os.path.isabs(p):
            return p
        return os.path.join(self.base_dir, p)

    @property
    def sessionid_path(self) -> str:
        return os.path.join(self.base_dir, SESSIONID_FILENAME)

    @property
    def cookies_path(self) -> str:
        return os.path.join(self.base_dir, COOKIES_FILENAME)


_config: Optional[AppConfig] = None


def load_config(base_dir: Optional[str] = None) -> AppConfig:
    global _config
    if _config is not None and (base_dir is None or base_dir == _config.base_dir):
        return _config

    root = base_dir or os.environ.get("EZTIKTOK_DATA") or os.getcwd()
    data = dict(DEFAULTS)
    cfg_path = os.path.join(root, CONFIG_FILENAME)
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data.update(loaded)
        except Exception:
            pass

    _config = AppConfig(
        output_dir=str(data["output_dir"]),
        cache_file=str(data["cache_file"]),
        batch_delay_sec=float(data["batch_delay_sec"]),
        naming_template=str(data["naming_template"]),
        request_timeout=int(data["request_timeout"]),
        poll_interval=float(data["poll_interval"]),
        poll_attempts=int(data["poll_attempts"]),
        clipboard_monitor=bool(data["clipboard_monitor"]),
        clipboard_poll_sec=float(data["clipboard_poll_sec"]),
        clipboard_dedupe_sec=float(data["clipboard_dedupe_sec"]),
        base_dir=root,
    )
    return _config


def reset_config() -> None:
    global _config
    _config = None
