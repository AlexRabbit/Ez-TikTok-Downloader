from __future__ import annotations

import os
import re
import time
from typing import Optional
from urllib.parse import quote

import requests

from .config import AppConfig, load_config

SUBMIT_URL = "https://tikwm.com/api/video/task/submit"
RESULT_BASE = "https://tikwm.com/api/video/task/result?task_id="
QUICK_API = "https://www.tikwm.com/api/"

TIKWM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://tikwm.com",
    "Referer": "https://tikwm.com/",
    "x-requested-with": "XMLHttpRequest",
}


def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip() or "unknown"


def load_sessionid(cfg: Optional[AppConfig] = None) -> Optional[str]:
    cfg = cfg or load_config()
    p = cfg.sessionid_path
    if not os.path.isfile(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            line = f.readline().strip()
    except Exception:
        return None
    if not line or line.startswith("#"):
        return None
    if line.lower().startswith("sessionid="):
        line = line[10:].strip()
    if line.upper().startswith("PASTE_"):
        return None
    return line if line else None


def tikwm_headers_with_session(session_id: Optional[str]) -> dict:
    h = dict(TIKWM_HEADERS)
    if session_id:
        h["Referer"] = f"https://www.tikwm.com/originalDownloader.html?cookie=sessionid={session_id}"
        h["x-proxy-cookie"] = f"sessionid={session_id}"
    return h


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


def extract_media_id_from_url(url: str) -> Optional[str]:
    m = re.search(r"/(?:video|photo)/(\d+)", url)
    return m.group(1) if m else None


def content_type_from_url(url: str) -> str:
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


def resolve_tiktok_redirect(url: str, cfg: Optional[AppConfig] = None) -> str:
    cfg = cfg or load_config()
    u = url.strip()
    if not re.search(r"https?://(vt|vm)\.tiktok\.com/", u, re.IGNORECASE):
        return u
    try:
        r = requests.get(
            u,
            headers={"User-Agent": TIKWM_HEADERS["User-Agent"]},
            timeout=cfg.request_timeout,
            allow_redirects=True,
        )
        if r.url and "tiktok.com" in r.url.lower():
            return r.url
    except requests.RequestException:
        pass
    return u


def _parse_tikwm_entry(j: dict, username_from_url: str, video_id_from_url: Optional[str]) -> Optional[dict]:
    data = j.get("data")
    if not data:
        return None

    if isinstance(data, dict) and (data.get("play") or data.get("hdplay") or data.get("wmplay")):
        author = data.get("author") or {}
        vid = data.get("id") or video_id_from_url or "unknown"
        if isinstance(vid, (int, float)):
            vid = str(int(vid))
        username = author.get("unique_id") or author.get("uniqueId") or author.get("nickname") or username_from_url
        profile_uid = author.get("id")
        return {
            "play_url": data.get("hdplay") or data.get("play") or data.get("wmplay"),
            "images": data.get("images") or [],
            "username": sanitize_filename(username or username_from_url),
            "video_id": str(vid),
            "create_time": data.get("create_time"),
            "profile_uid": str(profile_uid) if profile_uid is not None else "unknown",
        }

    detail = data.get("detail") if isinstance(data, dict) else None
    if detail is None and isinstance(data, dict):
        detail = data
    if not isinstance(detail, dict):
        return None

    play_url = detail.get("play_url") or detail.get("url") or detail.get("play") or detail.get("hdplay")
    images = detail.get("images") or (data.get("images") if isinstance(data, dict) else []) or []
    author = detail.get("author") or (data.get("author") if isinstance(data, dict) else {}) or {}
    username = (author.get("unique_id") or author.get("nickname") or username_from_url or "").strip()
    username = sanitize_filename(username) if username else sanitize_filename(username_from_url)
    vid = detail.get("video_id") or (data.get("video_id") if isinstance(data, dict) else None) or video_id_from_url or "unknown"
    if isinstance(vid, (int, float)):
        vid = str(int(vid))
    create_time = detail.get("create_time") or detail.get("createTime") or (data.get("create_time") if isinstance(data, dict) else None)
    profile_uid = author.get("id") or author.get("uid") or author.get("uniqueId")
    if profile_uid is not None:
        profile_uid = str(profile_uid)
    else:
        profile_uid = "unknown"

    if not play_url and not images:
        return None

    return {
        "play_url": play_url,
        "username": username,
        "video_id": vid,
        "images": images if isinstance(images, list) else [],
        "create_time": create_time,
        "profile_uid": profile_uid,
    }


def submit_tikwm_quick(tiktok_url: str, cfg: Optional[AppConfig] = None) -> Optional[dict]:
    cfg = cfg or load_config()
    session_id = load_sessionid(cfg)
    api_headers = tikwm_headers_with_session(session_id)
    username_from_url = extract_username_from_url(tiktok_url) or "unknown"
    video_id_from_url = extract_media_id_from_url(tiktok_url)

    for candidate in url_candidates(tiktok_url):
        try:
            url = f"{QUICK_API}?url={quote(candidate)}&hd=1"
            r = requests.get(url, headers=api_headers, timeout=cfg.request_timeout)
            if r.status_code != 200:
                continue
            j = r.json()
            if j.get("code") != 0:
                continue
            entry = _parse_tikwm_entry(j, username_from_url, video_id_from_url)
            if entry:
                return entry
        except (requests.RequestException, ValueError):
            continue
    return None


def submit_tikwm_task(tiktok_url: str, cfg: Optional[AppConfig] = None) -> Optional[dict]:
    cfg = cfg or load_config()
    quick = submit_tikwm_quick(tiktok_url, cfg)
    if quick:
        return quick

    candidates = url_candidates(tiktok_url)
    username_from_url = extract_username_from_url(tiktok_url) or "unknown"
    video_id_from_url = extract_media_id_from_url(tiktok_url)
    session_id = load_sessionid(cfg)
    api_headers = tikwm_headers_with_session(session_id)

    for candidate in candidates:
        try:
            body = f"web=1&url={quote(candidate)}"
            r = requests.post(SUBMIT_URL, data=body, headers=api_headers, timeout=cfg.request_timeout)
            r.raise_for_status()
            j = r.json()
        except (requests.RequestException, ValueError):
            continue

        code = j.get("code")
        task_id = (j.get("data") or {}).get("task_id") if isinstance(j.get("data"), dict) else None
        if code != 0 or not task_id:
            continue

        for _ in range(cfg.poll_attempts):
            time.sleep(cfg.poll_interval)
            try:
                poll = requests.get(RESULT_BASE + str(task_id), headers=api_headers, timeout=cfg.request_timeout)
                if poll.status_code != 200:
                    continue
                j2 = poll.json()
                if j2.get("code") != 0 or not isinstance(j2.get("data"), dict):
                    continue
                data = j2["data"]
                status = data.get("status")
                if status == 2:
                    entry = _parse_tikwm_entry(
                        {"data": {**data, "detail": data.get("detail") or data}},
                        username_from_url,
                        video_id_from_url,
                    )
                    if entry:
                        return entry
                if status == 3:
                    break
            except (requests.RequestException, ValueError):
                continue
    return None
