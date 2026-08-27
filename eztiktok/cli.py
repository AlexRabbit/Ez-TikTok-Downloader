from __future__ import annotations

import argparse
import os
import sys
import time

from .bulk import is_profile_input, process_profile
from .cache import export_cache_file, import_cache_file, load_cache, merge_entries, save_cache
from .clipboard import ClipboardMonitor
from .config import load_config
from .download import process_one_url
from .tikwm import load_sessionid

PROMPT = "Enter a TikTok URL, @username, or path to a .txt file (quit to exit): "
EXIT_COMMANDS = frozenset({"quit", "exit", "q"})


def process_input(user_input: str, cache: dict, output_dir, cfg, progress_callback=None) -> None:
    user_input = user_input.strip()
    if user_input.lower().endswith(".txt"):
        if not os.path.isfile(user_input):
            print(f"File not found: {user_input}")
            return
        with open(user_input, "r", encoding="utf-8", errors="replace") as f:
            lines = [line.strip() for line in f if line.strip()]
        if not lines:
            print("No URLs found in file.")
            return
        for i, line in enumerate(lines):
            if i > 0:
                time.sleep(cfg.batch_delay_sec)
            if is_profile_input(line):
                process_profile(line, cache, output_dir, cfg, progress_callback)
            else:
                process_one_url(line, cache, output_dir, cfg, progress_callback)
        return

    if is_profile_input(user_input):
        process_profile(user_input, cache, output_dir, cfg, progress_callback)
        return

    process_one_url(user_input, cache, output_dir, cfg, progress_callback)


def run_interactive_loop(cfg, cache, output_dir, cli_arg=None, clipboard=False, progress_callback=None) -> None:
    monitor = None
    if clipboard or cfg.clipboard_monitor:
        def on_clipboard_url(url: str) -> None:
            process_one_url(url, cache, output_dir, cfg, progress_callback)
            print("\nDownload completed! Paste another link, or type quit to exit.\n")

        monitor = ClipboardMonitor(on_clipboard_url, cfg)
        monitor.start()

    if clipboard and not cli_arg:
        # Clipboard-only mode: wait until Ctrl+C
        if monitor and monitor._thread:
            try:
                while monitor._thread.is_alive():
                    monitor._thread.join(timeout=1)
            except KeyboardInterrupt:
                print("\nGoodbye!")
                monitor.stop()
        return

    while True:
        if cli_arg:
            user_input = cli_arg
            cli_arg = None
        else:
            try:
                user_input = input(PROMPT).strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

        if user_input.lower() in EXIT_COMMANDS:
            print("Goodbye!")
            break
        if not user_input:
            continue

        process_input(user_input, cache, output_dir, cfg, progress_callback)
        print("\nDownload completed! Paste another link, or type quit to exit.\n")

    if monitor:
        monitor.stop()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tt.py",
        description="Ez-TikTok-Downloader by AlexRabbit",
    )
    p.add_argument("url", nargs="?", help="TikTok URL, @username, or .txt file path")
    p.add_argument("--profile", metavar="USER", help="Download all public posts from @username")
    p.add_argument("--export-cache", nargs="?", const="link_cache_export.json", metavar="FILE",
                   help="Export cache as schema v1 JSON")
    p.add_argument("--import-cache", metavar="FILE", help="Import cache from JSON (userscript or desktop)")
    p.add_argument("--merge", action="store_true", help="Merge with existing cache on import")
    p.add_argument("--clipboard", action="store_true", help="Enable clipboard monitor mode")
    p.add_argument("--loop", action="store_true", help="With --clipboard, also run interactive prompt loop")
    p.add_argument("--config-dir", metavar="DIR", help="Base directory for config.json and data files")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    base_dir = args.config_dir or os.environ.get("EZTIKTOK_DATA") or os.getcwd()
    os.chdir(base_dir)
    cfg = load_config(base_dir)

    if load_sessionid(cfg):
        print("Using session ID from sessionid.txt (private videos supported).")

    cache = load_cache(cfg.cache_path)

    if args.export_cache is not None:
        out = args.export_cache if args.export_cache else "link_cache_export.json"
        if not os.path.isabs(out):
            out = os.path.join(base_dir, out)
        export_cache_file(cache, out)
        return

    if args.import_cache:
        incoming = import_cache_file(args.import_cache)
        if args.merge:
            cache = merge_entries(cache, incoming)
        else:
            cache = incoming
        save_cache(cache, cfg.cache_path)
        print(f"Cache saved to {cfg.cache_path} ({len(cache)} entries)")
        return

    output_dir = cfg.output_path

    if args.profile:
        process_profile(args.profile, cache, output_dir, cfg)
        return

    cli_arg = args.url
    if cli_arg and cli_arg.startswith("@") and is_profile_input(cli_arg):
        process_profile(cli_arg, cache, output_dir, cfg)
        if not args.clipboard and not args.loop:
            return

    clipboard_only = args.clipboard and not args.loop and not cli_arg
    if clipboard_only:
        run_interactive_loop(cfg, cache, output_dir, clipboard=True)
        return

    run_interactive_loop(
        cfg, cache, output_dir,
        cli_arg=cli_arg,
        clipboard=args.clipboard or cfg.clipboard_monitor,
    )


if __name__ == "__main__":
    main()
