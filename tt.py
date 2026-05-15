#!/usr/bin/env python3
"""
Ez-TikTok-Downloader - Download TikTok without watermark, with link cache.
Extracts download links via TikWM task API; caches them so a crash doesn't force re-extraction.
Saves to username/username_videoID.mp4 (or images for slideshows).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from typing import Optional
from urllib.parse import quote

import requests

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

# TikWM task API
SUBMIT_URL = "https://tikwm.com/api/video/task/submit"
RESULT_BASE = "https://tikwm.com/api/video/task/result?task_id="
REQUEST_TIMEOUT = 25
POLL_INTERVAL = 1.0
POLL_ATTEMPTS = 60
BATCH_DELAY_SEC = 2

# Cache: video_id -> { "username", "play_url", "images" (optional list) }
CACHE_FILENAME = "link_cache.json"
SESSIONID_FILENAME = "sessionid.txt"
GALLERY_DL_COOKIES_FILENAME = ".gallery_dl_cookies.txt"

TIKWM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://tikwm.com",
    "Referer": "https://tikwm.com/",
    "x-requested-with": "XMLHttpRequest",
}


def load_sessionid() -> Optional[str]:
    """
    Read session ID from sessionid.txt in current directory.
    File can contain just the value (e.g. 5b1e4c753e7f00fc5400d85856eb0d67) or sessionid=value.
    Returns the raw value or None if file missing/empty.
    """
    p = os.path.join(os.getcwd(), SESSIONID_FILENAME)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            line = f.readline().strip()
    except Exception:
        return None
    if not line:
        return None
    if line.lower().startswith("sessionid="):
        line = line[10:].strip()
    return line if line else None


def tikwm_headers_with_session(session_id: Optional[str]) -> dict:
    """Return headers for TikWM API; if session_id is set, add Referer and x-proxy-cookie for private videos."""
    h = dict(TIKWM_HEADERS)
    if session_id:
        h["Referer"] = f"https://www.tikwm.com/originalDownloader.html?cookie=sessionid={session_id}"
        h["x-proxy-cookie"] = f"sessionid={session_id}"
    return h


def cache_path() -> str:
    """Cache file in current working directory."""
    return os.path.join(os.getcwd(), CACHE_FILENAME)


def load_cache() -> dict:
    p = cache_path()
    if not os.path.isfile(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache: dict) -> None:
    try:
        with open(cache_path(), "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"Warning: could not save cache: {e}")


def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip() or "unknown"


def normalize_tiktok_url(url: str) -> str:
    u = url.strip()
    if "#" in u:
        u = u.split("#")[0]
    if "?" in u:
        u = u.split("?")[0]
    u = u.rstrip("/")
    if u.startswith("http://"):
        u = "https://" + u[7:]
    return u


def extract_username_from_url(url: str) -> Optional[str]:
    m = re.search(r"tiktok\.com/@([\w.-]+)", url, re.IGNORECASE)
    return m.group(1) if m else None


def extract_video_id_from_url(url: str) -> Optional[str]:
    m = re.search(r"/video/(\d+)", url)
    return m.group(1) if m else None


def extract_media_id_from_url(url: str) -> Optional[str]:
    m = re.search(r"/(?:video|photo)/(\d+)", url)
    return m.group(1) if m else None


def content_type_from_url(url: str) -> str:
    """Return 'story', 'highlight', 'photo', or 'video' from URL path."""
    u = url.lower()
    if "/story" in u:
        return "story"
    if "highlight" in u:
        return "highlight"
    if "/photo/" in u:
        return "photo"
    return "video"


def url_candidates(tiktok_url: str) -> list[str]:
    normalized = normalize_tiktok_url(tiktok_url)
    video_id = extract_media_id_from_url(normalized)
    candidates = [normalized]
    if video_id:
        for u in (
            video_id,
            f"https://www.tiktok.com/video/{video_id}",
            f"https://www.tiktok.com/@tiktok/video/{video_id}",
            f"https://m.tiktok.com/v/{video_id}.html",
            f"https://www.tiktok.com/@/video/{video_id}",
        ):
            if u not in candidates:
                candidates.append(u)
    return candidates


def resolve_tiktok_redirect(url: str) -> str:
    """
    Resolve TikTok short links (vt/vm) to canonical URLs.
    Falls back to original URL on network errors.
    """
    u = url.strip()
    if not re.search(r"https?://(vt|vm)\.tiktok\.com/", u, re.IGNORECASE):
        return u
    try:
        r = requests.get(
            u,
            headers={"User-Agent": TIKWM_HEADERS["User-Agent"]},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        if r.url and "tiktok.com" in r.url.lower():
            return r.url
    except requests.RequestException:
        pass
    return u


def count_images_in_folder(folder: str) -> int:
    if not os.path.isdir(folder):
        return 0
    total = 0
    for name in os.listdir(folder):
        p = os.path.join(folder, name)
        if not os.path.isfile(p):
            continue
        low = name.lower()
        if low.endswith((".jpg", ".jpeg", ".png", ".webp")):
            total += 1
    return total


def write_gallery_dl_cookies_file(session_id: str) -> str:
    """Write a Netscape cookies.txt for gallery-dl using the TikTok sessionid."""
    path = os.path.join(os.getcwd(), GALLERY_DL_COOKIES_FILENAME)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n\n")
        f.write(f"#HttpOnly_.tiktok.com\tTRUE\t/\tTRUE\t0\tsessionid\t{session_id}\n")
    return path


def gallery_dl_photo_fallback(tiktok_url: str, output_dir: str, username: str) -> bool:
    """
    Download TikTok photo/slideshow posts with gallery-dl.
    This fallback is only used for photo posts when TikWM fails.
    """
    folder = os.path.join(output_dir, sanitize_filename(username or "unknown"), "photo")
    os.makedirs(folder, exist_ok=True)
    before_images = count_images_in_folder(folder)
    cmd = [sys.executable, "-m", "gallery_dl", "--no-skip", "-D", folder]
    session_id = load_sessionid()
    if session_id:
        cookies_path = write_gallery_dl_cookies_file(session_id)
        cmd.extend(["--cookies", cookies_path])
        print("Using session ID for gallery-dl photo fallback.")
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


def submit_tikwm_task(tiktok_url: str) -> Optional[dict]:
    """Return { play_url, username, video_id, images, create_time, profile_uid } or None."""
    candidates = url_candidates(tiktok_url)
    username_from_url = extract_username_from_url(tiktok_url) or "unknown"
    video_id_from_url = extract_media_id_from_url(tiktok_url)
    session_id = load_sessionid()
    api_headers = tikwm_headers_with_session(session_id)

    for candidate in candidates:
        try:
            body = f"web=1&url={quote(candidate)}"
            r = requests.post(
                SUBMIT_URL,
                data=body,
                headers=api_headers,
                timeout=REQUEST_TIMEOUT,
            )
            r.raise_for_status()
            j = r.json()
        except (requests.RequestException, ValueError):
            continue

        code = j.get("code")
        task_id = (j.get("data") or {}).get("task_id") if isinstance(j.get("data"), dict) else None
        if code != 0 or not task_id:
            continue

        for _ in range(POLL_ATTEMPTS):
            time.sleep(POLL_INTERVAL)
            try:
                poll = requests.get(
                    RESULT_BASE + str(task_id),
                    headers=api_headers,
                    timeout=REQUEST_TIMEOUT,
                )
                if poll.status_code != 200:
                    continue
                j2 = poll.json()
                if j2.get("code") != 0 or not isinstance(j2.get("data"), dict):
                    continue
                data = j2["data"]
                status = data.get("status")
                if status == 2:
                    detail = data.get("detail") or {}
                    play_url = detail.get("play_url") or detail.get("url") or detail.get("play")
                    images = detail.get("images") or data.get("images") or []
                    author = detail.get("author") or data.get("author") or {}
                    username = (author.get("unique_id") or author.get("nickname") or username_from_url or "").strip()
                    username = sanitize_filename(username) if username else sanitize_filename(username_from_url)
                    vid = detail.get("video_id") or data.get("video_id") or video_id_from_url or "unknown"
                    if isinstance(vid, (int, float)):
                        vid = str(int(vid))
                    create_time = detail.get("create_time") or detail.get("createTime") or data.get("create_time")
                    profile_uid = author.get("id") or author.get("uid") or author.get("uniqueId")
                    if profile_uid is not None:
                        profile_uid = str(profile_uid)
                    else:
                        profile_uid = "unknown"
                    if play_url or images:
                        return {
                            "play_url": play_url,
                            "username": username,
                            "video_id": vid,
                            "images": images if isinstance(images, list) else [],
                            "create_time": create_time,
                            "profile_uid": profile_uid,
                        }
                if status == 3:
                    break
            except (requests.RequestException, ValueError):
                continue
    return None


def build_date_str(create_time: Optional[int]) -> str:
    """Format as YY-mm-dd from Unix timestamp or today."""
    if create_time is not None:
        try:
            return datetime.utcfromtimestamp(int(create_time)).strftime("%y-%m-%d")
        except (ValueError, OSError):
            pass
    return datetime.utcnow().strftime("%y-%m-%d")


def build_filename(entry: dict, ext: str = ".mp4") -> str:
    """Username - Date(YY-mm-dd) - ProfileUniqueID - idPost"""
    username = sanitize_filename(entry.get("username") or "unknown")
    date_str = build_date_str(entry.get("create_time"))
    profile_uid = entry.get("profile_uid") or "unknown"
    if isinstance(profile_uid, (int, float)):
        profile_uid = str(int(profile_uid))
    video_id = entry.get("video_id") or "unknown"
    return f"{username} - {date_str} - {profile_uid} - {video_id}{ext}"


def subfolder_for_content_type(content_type: str) -> str:
    """Return '' for video, 'story' or 'highlight' for those types."""
    if content_type == "story":
        return "story"
    if content_type == "highlight":
        return "highlight"
    return ""


def download_to_file(url: str, filepath: str, headers: Optional[dict] = None) -> bool:
    h = headers or TIKWM_HEADERS
    try:
        r = requests.get(url, headers=h, timeout=REQUEST_TIMEOUT, stream=True)
        r.raise_for_status()
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return True
    except Exception:
        return False


def do_download(entry: dict, output_dir: str) -> bool:
    """Download using cached/API entry. entry has username, play_url?, images?, create_time?, profile_uid?, content_type?."""
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
        base_name = build_filename(entry, "") or f"{username}_{video_id}"
        for i, item in enumerate(images):
            url = item if isinstance(item, str) else (item.get("url") or item.get("image_url") or "")
            if not url:
                continue
            ext = ".jpg"
            if "." in url.split("?")[0]:
                ext = "." + url.split("?")[0].rsplit(".", 1)[-1].lower()
            if ext not in (".jpg", ".jpeg", ".png", ".webp"):
                ext = ".jpg"
            filepath = os.path.join(folder, f"{base_name}_img_{i + 1}{ext}")
            if os.path.exists(filepath):
                ok += 1
                continue
            if download_to_file(url, filepath):
                ok += 1
        if ok:
            print(f"Downloaded {ok} image(s) -> {folder}")
        return ok > 0

    if not play_url:
        return False
    if play_url.startswith("//"):
        play_url = "https:" + play_url
    fname = build_filename(entry, ".mp4")
    filepath = os.path.join(folder, fname)
    if os.path.exists(filepath):
        print(f"Already exists: {filepath}")
        return True
    h = {**TIKWM_HEADERS, "Referer": "https://www.tiktok.com/", "Origin": "https://www.tiktok.com"}
    if download_to_file(play_url, filepath, h):
        print(f"Downloaded: {filepath}")
        return True
    return False


def process_one_url(tiktok_url: str, cache: dict, output_dir: str) -> bool:
    """Process one URL: use cache if present, else extract then cache and download. Returns True if something succeeded."""
    tiktok_url = tiktok_url.strip()
    if "tiktok.com" not in tiktok_url and "douyin.com" not in tiktok_url:
        print(f"Skipped (not TikTok): {tiktok_url[:60]}...")
        return False

    tiktok_url = resolve_tiktok_redirect(tiktok_url)
    video_id = extract_media_id_from_url(tiktok_url) or "unknown"
    username_from_url = extract_username_from_url(tiktok_url) or "unknown"

    content_type = content_type_from_url(tiktok_url)
    # Use cache if we have a valid entry for this video_id
    if video_id in cache:
        ent = dict(cache[video_id])
        ent.setdefault("video_id", video_id)
        ent.setdefault("username", username_from_url)
        ent.setdefault("content_type", content_type)
        ent.setdefault("create_time", None)
        ent.setdefault("profile_uid", "unknown")
        if ent.get("play_url") or (ent.get("images") and len(ent.get("images", [])) > 0):
            print(f"[Cache] Using cached link for {video_id}")
            return do_download(ent, output_dir)

    # Extract via API
    print(f"Extracting link for {video_id}...")
    result = submit_tikwm_task(tiktok_url)
    if not result:
        if content_type == "photo":
            print(f"TikWM extraction failed for photo/slideshow {video_id}, trying gallery-dl fallback...")
            return gallery_dl_photo_fallback(tiktok_url, output_dir, username_from_url)
        if not result:
            print(f"Extraction failed for {video_id}")
            return False

    content_type = content_type_from_url(tiktok_url)
    # Persist to cache immediately so a crash doesn't lose this link
    cache[video_id] = {
        "username": result.get("username") or username_from_url,
        "play_url": result.get("play_url"),
        "video_id": result.get("video_id") or video_id,
        "images": result.get("images") or [],
        "create_time": result.get("create_time"),
        "profile_uid": result.get("profile_uid") or "unknown",
        "content_type": content_type,
    }
    save_cache(cache)

    return do_download(cache[video_id], output_dir)


def main() -> None:
    if load_sessionid():
        print("Using session ID from sessionid.txt (private videos supported).")
    prompt = "Enter a TikTok video URL or path to a .txt file with URLs: "
    if len(sys.argv) > 1:
        user_input = sys.argv[1].strip()
    else:
        try:
            user_input = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            return
    if not user_input:
        print("No input.")
        return

    output_dir = os.path.join(os.getcwd(), "profiles")
    cache = load_cache()

    if user_input.lower().endswith(".txt"):
        if not os.path.isfile(user_input):
            print(f"File not found: {user_input}")
            return
        with open(user_input, "r", encoding="utf-8", errors="replace") as f:
            lines = [line.strip() for line in f if line.strip()]
        for i, url in enumerate(lines):
            if i > 0:
                time.sleep(BATCH_DELAY_SEC)
            process_one_url(url, cache, output_dir)
    else:
        process_one_url(user_input, cache, output_dir)


if __name__ == "__main__":
    main()
