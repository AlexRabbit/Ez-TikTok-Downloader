#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "============================================"
echo " Ez-TikTok-Downloader - Setup (Mac/Linux)"
echo " by AlexRabbit"
echo "============================================"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 not found. Install Python 3.8+ and try again."
  exit 1
fi

python3 --version
echo
echo "Installing Python packages..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo
echo "Optional (GUI on Linux): sudo apt install python3-tk"
echo
echo "Setup complete. Run: ./run.sh  or  ./gui.sh"
echo "============================================"
