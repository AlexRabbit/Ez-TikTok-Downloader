from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Callable, Optional

import requests

from .cache import load_cache, save_cache
from .config import AppConfig, load_config
from .tikwm import (
    TIKWM_HEADERS,
    content_type_from_url,
    extract_media_id_from_url,
    extract_username_from_url,
    load_sessionid,
    resolve_tiktok_redirect,
    sanitize_filename,
    submit_tikwm_task,
)

ProgressCallback = Optional[Callable[[int, Optional[int]], None]]


def build_date_str(create_time: Optional[int]) -> str:
    if create_time is not None:
        try:
            return datetime.fromtimestamp(int(create_time), tz=timezone.utc).strftime("%y-%m-%d")
        except (ValueError, OSError):
            pass
    return datetime.now(timezone.utc).strftime("%y-%m-%d")


def build_filename(entry: dict, ext: str = ".mp4", cfg: Optional[AppConfig] = None) -> str:
    cfg = cfg or load_config()
    username = sanitize_filename(entry.get("username") or "unknown")
    date_str = build_date_str(entry.get("create_time"))
    profile_uid = entry.get("profile_uid") or "unknown"
    if isinstance(profile_uid, (int, float)):
        profile_uid = str(int(profile_uid))
    video_id = entry.get("video_id") or "unknown"
    template = cfg.naming_template
    return template.format(
        date=date_str,
        profile_uid=profile_uid,
        username=username,
        video_id=video_id,
        ext=ext,
    )


def subfolder_for_content_type(content_type: str) -> str:
    if content_type == "story":
        return "story"
    if content_type == "highlight":
        return "highlight"
    return ""


def count_images_in_folder(folder: str) -> int:
    if not os.path.isdir(folder):
        return 0
    total = 0
    for name in os.listdir(folder):
        p = os.path.join(folder, name)
        if not os.path.isfile(p):
            continue
        if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            total += 1
    return total


def gallery_dl_photo_fallback(tiktok_url: str, output_dir: str, username: str, cfg: Optional[AppConfig] = None) -> bool:
    cfg = cfg or load_config()
    folder = os.path.join(output_dir, sanitize_filename(username or "unknown"), "photo")
    os.makedirs(folder, exist_ok=True)
    before_images = count_images_in_folder(folder)
    cookies = cfg.cookies_path
    cmd = [sys.executable, "-m", "gallery_dl", "--no-skip", "-D", folder]
    if os.path.isfile(cookies):
        cmd.extend(["--cookies", cookies])
    cmd.append(tiktok_url)
    try:
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except Exception:
        return False
    if run.returncode != 0:
        err = (run.stderr or run.stdout or "").strip()
        if err:
            print(f"gallery-dl failed: {err[:500]}")
        return False
    after_images = count_images_in_folder(folder)
    if after_images <= before_images:
        return False
    print(f"Downloaded {after_images - before_images} image(s) with gallery-dl -> {folder}")
    return True


def download_to_file(
    url: str,
    filepath: str,
    headers: Optional[dict] = None,
    cfg: Optional[AppConfig] = None,
    progress_callback: ProgressCallback = None,
) -> bool:
    cfg = cfg or load_config()
    h = headers or TIKWM_HEADERS
    try:
        r = requests.get(url, headers=h, timeout=cfg.request_timeout, stream=True)
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0)) or None
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        downloaded = 0
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)
        return True
    except Exception:
        return False


def do_download(
    entry: dict,
    output_dir: str,
    cfg: Optional[AppConfig] = None,
    progress_callback: ProgressCallback = None,
) -> bool:
    cfg = cfg or load_config()
    username = entry.get("username") or "unknown"
    video_id = entry.get("video_id") or "unknown"
    play_url = entry.get("play_url")
    images = entry.get("images") or []
    content_type = entry.get("content_type") or "video"
    sub = subfolder_for_content_type(content_type)
    folder = os.path.join(output_dir, username, sub) if sub else os.path.join(output_dir, username)
    os.makedirs(folder, exist_ok=True)

    if images and (not play_url or content_type == "photo"):
        ok = 0
        base_name = build_filename(entry, "", cfg) or f"{username}_{video_id}"
        for i, item in enumerate(images):
            img_url = item if isinstance(item, str) else (item.get("url") or item.get("image_url") or "")
            if not img_url:
                continue
            ext = ".jpg"
            if "." in img_url.split("?")[0]:
                ext = "." + img_url.split("?")[0].rsplit(".", 1)[-1].lower()
            if ext not in (".jpg", ".jpeg", ".png", ".webp"):
                ext = ".jpg"
            filepath = os.path.join(folder, f"{base_name}_img_{i + 1}{ext}")
            if os.path.exists(filepath):
                ok += 1
                continue
            if download_to_file(img_url, filepath, progress_callback=progress_callback, cfg=cfg):
                ok += 1
        if ok:
            print(f"Downloaded {ok} image(s) -> {folder}")
        return ok > 0

    if not play_url:
        return False
    if play_url.startswith("//"):
        play_url = "https:" + play_url
    fname = build_filename(entry, ".mp4", cfg)
    filepath = os.path.join(folder, fname)
    if os.path.exists(filepath):
        print(f"Already exists: {filepath}")
        return True
    h = {**TIKWM_HEADERS, "Referer": "https://www.tiktok.com/", "Origin": "https://www.tiktok.com"}
    if download_to_file(play_url, filepath, h, cfg, progress_callback):
        print(f"Downloaded: {filepath}")
        return True
    return False


def process_one_url(
    tiktok_url: str,
    cache: dict,
    output_dir: str,
    cfg: Optional[AppConfig] = None,
    progress_callback: ProgressCallback = None,
) -> bool:
    cfg = cfg or load_config()
    tiktok_url = tiktok_url.strip()
    if "tiktok.com" not in tiktok_url and "douyin.com" not in tiktok_url:
        print(f"Skipped (not TikTok): {tiktok_url[:60]}...")
        return False

    tiktok_url = resolve_tiktok_redirect(tiktok_url, cfg)
    video_id = extract_media_id_from_url(tiktok_url) or "unknown"
    username_from_url = extract_username_from_url(tiktok_url) or "unknown"
    content_type = content_type_from_url(tiktok_url)

    if video_id in cache:
        ent = dict(cache[video_id])
        ent.setdefault("video_id", video_id)
        ent.setdefault("username", username_from_url)
        ent.setdefault("content_type", content_type)
        ent.setdefault("create_time", None)
        ent.setdefault("profile_uid", "unknown")
        if ent.get("play_url") or (ent.get("images") and len(ent.get("images", [])) > 0):
            print(f"[Cache] Using cached link for {video_id}")
            return do_download(ent, output_dir, cfg, progress_callback)

    print(f"Extracting link for {video_id}...")
    result = submit_tikwm_task(tiktok_url, cfg)
    if not result:
        if content_type == "photo":
            print(f"TikWM extraction failed for photo/slideshow {video_id}, trying gallery-dl fallback...")
            return gallery_dl_photo_fallback(tiktok_url, output_dir, username_from_url, cfg)
        print(f"Extraction failed for {video_id}")
        return False

    cache[video_id] = {
        "username": result.get("username") or username_from_url,
        "play_url": result.get("play_url"),
        "video_id": result.get("video_id") or video_id,
        "images": result.get("images") or [],
        "create_time": result.get("create_time"),
        "profile_uid": result.get("profile_uid") or "unknown",
        "content_type": content_type,
    }
    save_cache(cache, cfg.cache_path)
    return do_download(cache[video_id], output_dir, cfg, progress_callback)
