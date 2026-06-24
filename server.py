#!/usr/bin/env python3
"""
Photo Cleaner — local web app that strips AI/provenance metadata
(C2PA / JUMBF / IPTC digitalSourceType / XMP / EXIF) from images so
Instagram does not apply the "AI Info" label.

Lossless: JPEG pixels are never re-encoded; PNG/WebP are re-encoded
losslessly (pixels identical) to drop C2PA chunks.

Run:  python3 server.py   (opens the UI in your browser automatically)
"""
import base64
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "out")
os.makedirs(OUT_DIR, exist_ok=True)

EXIFTOOL = shutil.which("exiftool") or "/opt/homebrew/bin/exiftool"
MAGICK = shutil.which("magick") or "/opt/homebrew/bin/magick"

# Tags that indicate AI generation / provenance — used for the before/after report.
SIGNAL_RE = re.compile(
    r"C2PA|JUMBF|jumbf|DigitalSourceType|trainedAlgorithmicMedia|compositeWithTrained|"
    r"Firefly|OpenAI|DALL|gpt-image|GPT|Generative|Stable.?Diffusion|Midjourney|SynthID",
    re.I,
)
# Broader set (includes generic authorship tags) for the "before" display only.
DISPLAY_RE = re.compile(SIGNAL_RE.pattern + r"|Software|Creator|Artist|ProcessingSoftware", re.I)

MIME = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "webp": "image/webp", "tif": "image/tiff", "tiff": "image/tiff",
    "heic": "image/heic", "gif": "image/gif",
}


def _exif_lines(path, rx):
    try:
        r = subprocess.run([EXIFTOOL, "-a", "-G1", path],
                           capture_output=True, text=True, timeout=60)
    except Exception:
        return []
    out = []
    for line in r.stdout.splitlines():
        if rx.search(line):
            out.append(re.sub(r"\s{2,}", "  ", line.strip()))
    return out


def has_ai_signal(path):
    return bool(_exif_lines(path, SIGNAL_RE))


def process(name, data):
    """Clean one image. Returns (cleaned_bytes, before_list, after_list, ext)."""
    work = tempfile.mkdtemp(prefix="igclean_")
    try:
        safe = os.path.basename(name) or "image"
        src = os.path.join(work, safe)
        with open(src, "wb") as f:
            f.write(data)

        before = _exif_lines(src, DISPLAY_RE)
        ext = safe.rsplit(".", 1)[-1].lower() if "." in safe else ""
        dst = os.path.join(work, "clean_" + safe)

        if ext in ("png", "webp", "tif", "tiff", "gif"):
            # Lossless formats: re-encode (drops C2PA chunks + all metadata containers).
            subprocess.run([MAGICK, src, "-auto-orient", "-strip", dst],
                           check=True, capture_output=True)
            subprocess.run([EXIFTOOL, "-all=", "-overwrite_original", "-P", dst],
                           capture_output=True)
        elif ext in ("jpg", "jpeg", "heic"):
            # Lossy: strip metadata losslessly, pixels untouched. Bake orientation first.
            shutil.copy(src, dst)
            subprocess.run([EXIFTOOL, "-all=", "-tagsfromfile", "@", "-Orientation",
                            "-overwrite_original", "-P", dst], capture_output=True)
            if has_ai_signal(dst):  # stubborn manifest survived -> re-encode fallback
                subprocess.run([MAGICK, src, "-auto-orient", "-strip", "-quality", "96", dst],
                               check=True, capture_output=True)
                subprocess.run([EXIFTOOL, "-all=", "-overwrite_original", "-P", dst],
                               capture_output=True)
        else:
            shutil.copy(src, dst)
            subprocess.run([EXIFTOOL, "-all=", "-overwrite_original", "-P", dst],
                           capture_output=True)

        after = _exif_lines(dst, DISPLAY_RE)
        with open(dst, "rb") as f:
            cleaned = f.read()

        # Persist a copy in the out/ folder (avoid clobbering on name collisions).
        target = os.path.join(OUT_DIR, safe)
        if os.path.exists(target):
            stem, dot, e = safe.rpartition(".")
            n = 2
            while os.path.exists(target):
                target = os.path.join(OUT_DIR, f"{stem or safe}-{n}{dot}{e}")
                n += 1
        with open(target, "wb") as f:
            f.write(cleaned)

        return cleaned, before, after, ext
    finally:
        shutil.rmtree(work, ignore_errors=True)


INDEX = os.path.join(BASE_DIR, "index.html")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html"):
            with open(INDEX, "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        elif path == "/health":
            self._send(200, b'{"ok":true}')
        else:
            self._send(404, b'{"ok":false,"error":"not found"}')

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/clean":
            length = int(self.headers.get("Content-Length", "0"))
            data = self.rfile.read(length)
            name = urllib.parse.unquote(self.headers.get("X-Filename", "image"))
            try:
                cleaned, before, after, ext = process(name, data)
                mime = MIME.get(ext, "application/octet-stream")
                payload = {
                    "ok": True,
                    "filename": os.path.basename(name),
                    "before": before,
                    "after": after,
                    "removed": len(before),
                    "dataurl": "data:%s;base64,%s" % (mime, base64.b64encode(cleaned).decode()),
                }
            except Exception as e:  # noqa
                payload = {"ok": False, "error": str(e), "filename": os.path.basename(name)}
            self._send(200, json.dumps(payload).encode())
        elif path == "/open-out":
            try:
                subprocess.run(["open", OUT_DIR], check=False)
                self._send(200, b'{"ok":true}')
            except Exception as e:  # noqa
                self._send(200, json.dumps({"ok": False, "error": str(e)}).encode())
        else:
            self._send(404, b'{"ok":false}')

    def log_message(self, *a):  # keep the terminal quiet
        pass


def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    port = free_port()
    url = f"http://127.0.0.1:{port}/"
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("\n  Photo Cleaner is running.")
    print(f"  If your browser didn't open, go to:  {url}")
    print("  (Keep this window open while using the app. Close it when done.)\n")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
