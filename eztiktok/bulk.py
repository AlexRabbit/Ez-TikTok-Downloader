from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from typing import Callable, Optional

from .config import AppConfig, load_config
from .download import process_one_url

PROFILE_PATTERN = re.compile(r"^@?([\w.-]+)$")
PROFILE_URL_PATTERN = re.compile(r"tiktok\.com/@([\w.-]+)/?(?:\?|$)", re.IGNORECASE)


def is_profile_input(text: str) -> bool:
    text = text.strip()
    if PROFILE_PATTERN.match(text):
        return True
    if PROFILE_URL_PATTERN.search(text) and "/video/" not in text and "/photo/" not in text:
        return True
    return False


def extract_profile_username(text: str) -> Optional[str]:
    text = text.strip()
    m = PROFILE_PATTERN.match(text)
    if m:
        return m.group(1)
    m = PROFILE_URL_PATTERN.search(text)
    if m:
        return m.group(1)
    return None


def fetch_profile_urls(username: str, cfg: Optional[AppConfig] = None) -> list[str]:
    cfg = cfg or load_config()
    profile_url = f"https://www.tiktok.com/@{username}"
    cmd = [sys.executable, "-m", "gallery_dl", "--flat-list", profile_url]
    if os.path.isfile(cfg.cookies_path):
        cmd = [sys.executable, "-m", "gallery_dl", "--flat-list", "--cookies", cfg.cookies_path, profile_url]

    try:
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except Exception as e:
        print(f"Failed to list profile @{username}: {e}")
        return []

    if run.returncode != 0:
        err = (run.stderr or run.stdout or "").strip()
        print(f"gallery-dl profile list failed: {err[:500]}")
        print("Tip: add cookies.txt for private or restricted profiles.")
        return []

    urls = []
    for line in (run.stdout or "").splitlines():
        line = line.strip()
        if "tiktok.com" in line and ("/video/" in line or "/photo/" in line):
            urls.append(line)
    return urls


def process_profile(
    username_or_url: str,
    cache: dict,
    output_dir: str,
    cfg: Optional[AppConfig] = None,
    progress_callback: Optional[Callable[[int, Optional[int]], None]] = None,
) -> int:
    cfg = cfg or load_config()
    username = extract_profile_username(username_or_url)
    if not username:
        print(f"Could not parse profile: {username_or_url}")
        return 0

    print(f"Fetching video list for @{username}...")
    urls = fetch_profile_urls(username, cfg)
    if not urls:
        print(f"No videos found for @{username}")
        return 0

    print(f"Found {len(urls)} post(s) for @{username}")
    ok = 0
    for i, url in enumerate(urls):
        if i > 0:
            time.sleep(cfg.batch_delay_sec)
        if process_one_url(url, cache, output_dir, cfg, progress_callback):
            ok += 1
    print(f"Profile @{username}: {ok}/{len(urls)} downloaded")
    return ok
