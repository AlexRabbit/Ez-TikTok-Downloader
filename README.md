<div align="center">

# 🎬 Ez-TikTok-Downloader

### *Download TikTok videos without watermark — desktop app + browser userscript, shared cache, GUI, and more.*

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License: Unlicense](https://img.shields.io/badge/License-Unlicense-lightgrey?style=for-the-badge)](./LICENSE)
[![Author](https://img.shields.io/badge/Author-AlexRabbit-FF0050?style=for-the-badge&logo=github&logoColor=white)](https://github.com/AlexRabbit)

**🚫 No watermark · 📺 Original quality · 💾 Shared cache · 🔁 Continuous downloads · 🖥️ GUI · 📋 Clipboard mode · 🐳 Docker**

If this helped you, consider starring the repo ⭐

[📥 Download ZIP](https://github.com/AlexRabbit/Ez-TikTok-Downloader/archive/refs/heads/main.zip) · [🌐 TikTok_Rabbit Userscript](https://github.com/AlexRabbit/Userscripts)

</div>

---

## ✨ What's new in v2

| Feature | How to use |
|---------|------------|
| 🖱️ **Drag & drop** | Drop a URL, `.txt`, or `.url` shortcut onto **`run.bat`** |
| 📋 **Clipboard monitor** | `python tt.py --clipboard` or enable in GUI / `config.json` |
| 🖥️ **GUI** | Double-click **`run_gui.bat`** |
| 👤 **Bulk @username** | `python tt.py @creator` or paste `@creator` in the prompt |
| 🍎 **Mac/Linux** | `./dependencies.sh` then `./run.sh` |
| 🐳 **Docker** | `docker compose run --rm ez-tiktok "URL"` |
| ⚙️ **Settings** | Copy `config.json.example` → `config.json` |

---

## 🎯 What is this?

**Ez-TikTok-Downloader** by [AlexRabbit](https://github.com/AlexRabbit) downloads TikTok content without the watermark overlay.

| Feature | Description |
|--------|-------------|
| 🌐 **Original quality** | TikWM API + quick API fallback |
| 🖼️ **Photo fallback** | gallery-dl when TikWM fails on slideshows |
| 🔐 **Private videos** | `sessionid.txt` for friends-only content |
| 📁 **Organized by creator** | `profiles/username/` folders |
| 💾 **Shared cache** | Same link cache as the browser userscript |
| 🔁 **Continuous mode** | Download one after another — no "Press any key" |
| 👤 **Profile bulk** | Download all public posts from `@username` |


---

## 🖱️ Drag and drop

Drop onto **`run.bat`** (or **`run_drop.bat`**):

- A **TikTok URL** (if Windows passes it as an argument)
- A **`.txt`** file with one URL per line
- A **`.url`** Internet Shortcut file

The download starts immediately, then the continuous prompt loop continues.

---

## 📋 Clipboard monitor

Auto-download when you copy a TikTok link
Also available as a checkbox in the **GUI**.

---

## 🖥️ GUI

Double-click **`run_gui.bat`** (Windows) or run **`./gui.sh`** (Mac/Linux).

- URL field + **Download** button
- **Profile** bulk download field
- Progress bar (extraction + download %)
- Clipboard monitor toggle
- Scrollable log

> Linux: install `python3-tk` if the GUI does not open (`sudo apt install python3-tk`).

---

## 👤 Bulk profile download

Download all public posts from a creator:

```batch
python tt.py @username
python tt.py --profile username
python tt.py "https://www.tiktok.com/@username"
```

Or paste `@username` in the interactive prompt or GUI profile field.

---

## ⚙️ Configuration

Copy **`config.json.example`** → **`config.json`**:

| Key | Default | Description |
|-----|---------|-------------|
| `output_dir` | `profiles` | Download folder |
| `cache_file` | `link_cache.json` | Cache path |
| `batch_delay_sec` | `2` | Delay between batch/profile items |
| `naming_template` | `{date} - {profile_uid} - {username} - {video_id}{ext}` | Filename pattern |
| `clipboard_monitor` | `false` | Auto-download copied links |
| `clipboard_poll_sec` | `1.5` | Clipboard check interval |
| `request_timeout` | `25` | HTTP timeout seconds |

---

## 🍎 Mac / Linux

```bash
chmod +x dependencies.sh run.sh gui.sh
./dependencies.sh    # once
./run.sh             # CLI
./gui.sh             # GUI
```

---

## 🐳 Docker

```bash
cp config.json.example config.json
docker compose build
docker compose run --rm ez-tiktok "https://www.tiktok.com/@user/video/1234567890"
```

Volumes: `./profiles`, `./link_cache.json`, `./config.json`

Clipboard monitor is not available inside Docker.

---

## 📥 Installation (Windows)

1. Download and extract the ZIP
2. Double-click **`dependencies.bat`** (once)
3. Double-click **`run.bat`**

Optional: copy `sessionid.txt.example` → `sessionid.txt` for private videos.

---

## 🔐 Private videos

Copy **`sessionid.txt.example`** → **`sessionid.txt`**, paste your TikTok `sessionid` cookie value.

For photo/slideshow fallback: copy **`cookies.txt.example`** → **`cookies.txt`**.

---


## 🙏 Credits

- **[AlexRabbit](https://github.com/AlexRabbit)** — creator & maintainer
- **[TikTok_Rabbit userscript](https://github.com/AlexRabbit/Userscripts)** — browser companion + shared cache
- **[TikWM](https://www.tikwm.com)** — download link API
- **[gallery-dl](https://github.com/mikf/gallery-dl)** — photo fallback & profile listing

---

<div align="center">

**Made with ❤️ by [AlexRabbit](https://github.com/AlexRabbit)**

<sub>🎬 Ez-TikTok-Downloader · Shared cache · GUI · Clipboard · Docker · Bulk profiles</sub>

</div>
