from __future__ import annotations

import re
import threading
import time
from typing import Callable, Optional

from .config import AppConfig, load_config

TIKTOK_URL_RE = re.compile(
    r"https?://(?:[\w.-]+\.)?(?:tiktok\.com|vt\.tiktok\.com|vm\.tiktok\.com)/[^\s]+",
    re.IGNORECASE,
)

_clipboard_available: Optional[bool] = None


def _check_pyperclip() -> bool:
    global _clipboard_available
    if _clipboard_available is not None:
        return _clipboard_available
    try:
        import pyperclip  # noqa: F401
        _clipboard_available = True
    except ImportError:
        _clipboard_available = False
    return _clipboard_available


def extract_tiktok_url(text: str) -> Optional[str]:
    if not text:
        return None
    m = TIKTOK_URL_RE.search(text.strip())
    return m.group(0) if m else None


class ClipboardMonitor:
    def __init__(
        self,
        on_url: Callable[[str], None],
        cfg: Optional[AppConfig] = None,
    ):
        self.cfg = cfg or load_config()
        self.on_url = on_url
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_url: Optional[str] = None
        self._last_time: float = 0

    def start(self) -> bool:
        if not _check_pyperclip():
            print("Clipboard monitor requires pyperclip: pip install pyperclip")
            return False
        if self._thread and self._thread.is_alive():
            return True
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[Clipboard] Monitor started — copy a TikTok link to auto-download")
        return True

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        import pyperclip
        while not self._stop.is_set():
            try:
                text = pyperclip.paste() or ""
                url = extract_tiktok_url(text)
                if url and url != self._last_url:
                    now = time.time()
                    if now - self._last_time >= self.cfg.clipboard_dedupe_sec:
                        self._last_url = url
                        self._last_time = now
                        print(f"[Clipboard] Detected link — downloading...")
                        self.on_url(url)
            except Exception:
                pass
            self._stop.wait(self.cfg.clipboard_poll_sec)
