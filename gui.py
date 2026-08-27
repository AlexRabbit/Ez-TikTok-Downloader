#!/usr/bin/env python3
"""Ez-TikTok-Downloader GUI — by AlexRabbit."""
from typing import Optional
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk

from eztiktok.bulk import is_profile_input, process_profile
from eztiktok.cache import load_cache
from eztiktok.clipboard import ClipboardMonitor
from eztiktok.config import load_config
from eztiktok.download import process_one_url
from eztiktok.tikwm import load_sessionid


class EzTikTokGUI:
    def __init__(self) -> None:
        self.cfg = load_config()
        self.cache = load_cache(self.cfg.cache_path)
        self.output_dir = self.cfg.output_path
        self.monitor: ClipboardMonitor | None = None
        self._busy = False

        self.root = tk.Tk()
        self.root.title("Ez-TikTok-Downloader — AlexRabbit")
        self.root.geometry("620x480")
        self.root.minsize(480, 360)

        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main, text="TikTok URL:").pack(anchor=tk.W)
        url_row = ttk.Frame(main)
        url_row.pack(fill=tk.X, pady=(0, 8))
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(url_row, textvariable=self.url_var)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.url_entry.bind("<Return>", lambda e: self._download_url())
        ttk.Button(url_row, text="Download", command=self._download_url).pack(side=tk.LEFT)

        ttk.Label(main, text="Profile (@username):").pack(anchor=tk.W)
        prof_row = ttk.Frame(main)
        prof_row.pack(fill=tk.X, pady=(0, 8))
        self.profile_var = tk.StringVar()
        ttk.Entry(prof_row, textvariable=self.profile_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(prof_row, text="Download profile", command=self._download_profile).pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(main, textvariable=self.status_var).pack(anchor=tk.W, pady=(0, 4))

        self.progress = ttk.Progressbar(main, mode="indeterminate")
        self.progress.pack(fill=tk.X, pady=(0, 8))

        self.clipboard_var = tk.BooleanVar(value=self.cfg.clipboard_monitor)
        ttk.Checkbutton(
            main, text="Clipboard monitor (auto-download copied links)",
            variable=self.clipboard_var, command=self._toggle_clipboard,
        ).pack(anchor=tk.W, pady=(0, 8))

        ttk.Label(main, text="Log:").pack(anchor=tk.W)
        self.log = scrolledtext.ScrolledText(main, height=12, state=tk.DISABLED)
        self.log.pack(fill=tk.BOTH, expand=True)

        if load_sessionid(self.cfg):
            self._log("Using session ID from sessionid.txt (private videos supported).")

        if self.clipboard_var.get():
            self._toggle_clipboard()

    def _log(self, msg: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _set_busy(self, busy: bool, status: str = "") -> None:
        self._busy = busy
        if status:
            self.status_var.set(status)
        if busy:
            self.progress.configure(mode="indeterminate")
            self.progress.start(10)
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate", value=0)

    def _progress_cb(self, downloaded: int, total: Optional[int]) -> None:
        if total:
            pct = min(100, int(downloaded * 100 / total))
            self.root.after(0, lambda: self._update_progress(pct, total, downloaded))

    def _update_progress(self, pct: int, total: int, downloaded: int) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate", maximum=100, value=pct)
        self.status_var.set(f"Downloading… {pct}% ({downloaded // 1024} KB / {total // 1024} KB)")

    def _run_task(self, fn) -> None:
        if self._busy:
            self._log("Already working — please wait.")
            return

        def worker():
            self.root.after(0, lambda: self._set_busy(True, "Working…"))
            try:
                fn()
            except Exception as e:
                self.root.after(0, lambda: self._log(f"Error: {e}"))
            finally:
                self.root.after(0, lambda: self._set_busy(False, "Ready"))

        threading.Thread(target=worker, daemon=True).start()

    def _download_url(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            return

        def task():
            self.root.after(0, lambda: self._log(f"Processing: {url[:80]}…"))
            if is_profile_input(url):
                n = process_profile(url, self.cache, self.output_dir, self.cfg, self._progress_cb)
                self.root.after(0, lambda: self._log(f"Profile done: {n} item(s)"))
            else:
                ok = process_one_url(url, self.cache, self.output_dir, self.cfg, self._progress_cb)
                self.root.after(0, lambda: self._log("Done!" if ok else "Failed or skipped."))
            self.root.after(0, lambda: self.url_var.set(""))

        self._run_task(task)

    def _download_profile(self) -> None:
        user = self.profile_var.get().strip()
        if not user:
            return
        if not user.startswith("@"):
            user = "@" + user

        def task():
            self.root.after(0, lambda: self._log(f"Profile: {user}"))
            n = process_profile(user, self.cache, self.output_dir, self.cfg, self._progress_cb)
            self.root.after(0, lambda: self._log(f"Profile done: {n} item(s)"))

        self._run_task(task)

    def _toggle_clipboard(self) -> None:
        if self.clipboard_var.get():
            def on_url(u: str) -> None:
                self.root.after(0, lambda: self._log(f"[Clipboard] {u[:60]}…"))
                process_one_url(u, self.cache, self.output_dir, self.cfg, self._progress_cb)
                self.root.after(0, lambda: self._log("Clipboard download done."))

            self.monitor = ClipboardMonitor(on_url, self.cfg)
            if self.monitor.start():
                self._log("Clipboard monitor enabled.")
            else:
                self.clipboard_var.set(False)
        else:
            if self.monitor:
                self.monitor.stop()
                self.monitor = None
            self._log("Clipboard monitor disabled.")

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    EzTikTokGUI().run()


if __name__ == "__main__":
    main()
