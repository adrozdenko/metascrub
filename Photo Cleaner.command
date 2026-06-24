#!/usr/bin/env bash
# Double-click to launch the Photo Cleaner app. It opens in your browser.
# Keep this window open while using the app; close it when you're done.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
cd "$(dirname "$0")" || exit 1
clear
echo "Starting Photo Cleaner…"
python3 server.py
