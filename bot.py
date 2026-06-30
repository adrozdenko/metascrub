#!/usr/bin/env python3
"""
MetaScrub Telegram bot.

Run:
  export METASCRUB_TELEGRAM_TOKEN="123:abc"
  python3 bot.py

The bot uses Telegram long polling and Python's standard library only.
It reuses server.process(), so the cleaning behavior stays identical to
the web app and CLI.
"""
import json
import mimetypes
import os
import posixpath
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from server import EXIFTOOL, MAGICK, process

TOKEN_ENV = ("METASCRUB_TELEGRAM_TOKEN", "TELEGRAM_BOT_TOKEN", "BOT_TOKEN")
API_TIMEOUT = 65
POLL_TIMEOUT = 50
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff", ".gif"}
SUPPORTED_MIME = {
    "image/jpeg", "image/png", "image/webp", "image/heic", "image/heif",
    "image/tiff", "image/gif",
}
MIME_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "image/tiff": ".tiff",
    "image/gif": ".gif",
}


class TelegramError(RuntimeError):
    pass


def log(event, **fields):
    parts = [time.strftime("%Y-%m-%d %H:%M:%S"), event]
    for key, value in fields.items():
        if value is None:
            continue
        parts.append(f"{key}={value}")
    print(" ".join(parts), flush=True)


def fmt_bytes(size):
    if size is None:
        return None
    try:
        size = int(size)
    except (TypeError, ValueError):
        return size
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f}{unit}" if unit != "B" else f"{size}B"
        size /= 1024
    return f"{size:.1f}GB"


def token_from_env():
    for name in TOKEN_ENV:
        token = os.environ.get(name)
        if token:
            return token
    names = ", ".join(TOKEN_ENV)
    raise SystemExit(f"Missing bot token. Set one of: {names}")


TOKEN = None
API = None
FILE_API = None


def configure_token():
    global TOKEN, API, FILE_API
    if API and FILE_API:
        return
    TOKEN = token_from_env()
    API = f"https://api.telegram.org/bot{TOKEN}"
    FILE_API = f"https://api.telegram.org/file/bot{TOKEN}"


def request_json(method, payload=None):
    configure_token()
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{API}/{method}", data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as res:
            body = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise TelegramError(f"{method} failed: HTTP {e.code} {detail}") from e
    except urllib.error.URLError as e:
        raise TelegramError(f"{method} failed: {e.reason}") from e
    if not body.get("ok"):
        raise TelegramError(f"{method} failed: {body}")
    return body["result"]


def form_header_value(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\r", "").replace("\n", "")


def request_multipart(method, fields, files):
    configure_token()
    boundary = "----metascrub-" + uuid.uuid4().hex
    chunks = []
    for name, value in fields.items():
        field_name = form_header_value(name)
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{field_name}"\r\n\r\n'.encode(),
            str(value).encode("utf-8"),
            b"\r\n",
        ])
    for name, file_info in files.items():
        filename, content_type, data = file_info
        field_name = form_header_value(name)
        safe_filename = form_header_value(filename)
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{safe_filename}"\r\n'
            ).encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            data,
            b"\r\n",
        ])
    chunks.append(f"--{boundary}--\r\n".encode())
    body = b"".join(chunks)
    req = urllib.request.Request(
        f"{API}/{method}",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as res:
            payload = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise TelegramError(f"{method} failed: HTTP {e.code} {detail}") from e
    except urllib.error.URLError as e:
        raise TelegramError(f"{method} failed: {e.reason}") from e
    if not payload.get("ok"):
        raise TelegramError(f"{method} failed: {payload}")
    return payload["result"]


def send_message(chat_id, text, reply_to=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if reply_to:
        payload["reply_parameters"] = {"message_id": reply_to}
    return request_json("sendMessage", payload)


def send_action(chat_id, action):
    return request_json("sendChatAction", {"chat_id": chat_id, "action": action})


def send_document(chat_id, filename, data, caption, reply_to=None):
    fields = {"chat_id": chat_id, "caption": caption}
    if reply_to:
        fields["reply_parameters"] = json.dumps({"message_id": reply_to})
    ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return request_multipart(
        "sendDocument",
        fields,
        {"document": (filename, ctype, data)},
    )


def get_file(file_id):
    return request_json("getFile", {"file_id": file_id})


def download_file(file_path):
    configure_token()
    safe_path = posixpath.normpath(file_path).lstrip("/")
    if safe_path.startswith("../"):
        raise TelegramError("Telegram returned an unsafe file path")
    url = f"{FILE_API}/{urllib.parse.quote(safe_path)}"
    with urllib.request.urlopen(url, timeout=API_TIMEOUT) as res:
        return res.read()


def is_supported_document(document):
    name = document.get("file_name", "")
    ext = os.path.splitext(name)[1].lower()
    mime = document.get("mime_type", "")
    return ext in SUPPORTED_EXT or mime in SUPPORTED_MIME


def photo_payload(message):
    photos = message.get("photo") or []
    if not photos:
        return None
    photo = max(photos, key=lambda item: item.get("file_size") or 0)
    return {
        "file_id": photo["file_id"],
        "file_size": photo.get("file_size"),
        "filename": "telegram-photo.jpg",
        "source": "photo",
        "note": "Telegram photos may be compressed. Send as File/Document for original bytes.",
    }


def document_payload(message):
    document = message.get("document")
    if not document or not is_supported_document(document):
        return None
    filename = os.path.basename(document.get("file_name") or "image")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_EXT:
        filename += MIME_EXT.get(document.get("mime_type", ""), "")
    return {
        "file_id": document["file_id"],
        "file_size": document.get("file_size"),
        "filename": filename,
        "source": "document",
        "note": "",
    }


def extract_image(message):
    return document_payload(message) or photo_payload(message)


def clean_caption(before, after, extra_note=""):
    if before:
        text = f"Cleaned. Removed {len(before)} metadata line"
        if len(before) != 1:
            text += "s"
        text += "."
    else:
        text = "Cleaned. No matching metadata was found, but the image was scrubbed anyway."
    if after:
        text += f"\nWarning: {len(after)} matching metadata line"
        if len(after) != 1:
            text += "s"
        text += " still present."
    if extra_note:
        text += f"\n{extra_note}"
    return text


def handle_image(message, image):
    chat_id = message["chat"]["id"]
    message_id = message.get("message_id")
    started = time.monotonic()
    log(
        "image_received",
        chat=chat_id,
        message=message_id,
        source=image.get("source"),
        file=image.get("filename"),
        size=fmt_bytes(image.get("file_size")),
    )
    send_action(chat_id, "upload_document")

    if image.get("file_size") and image["file_size"] > MAX_DOWNLOAD_BYTES:
        size_mb = image["file_size"] / 1024 / 1024
        raise TelegramError(f"file is {size_mb:.1f} MB; Telegram bot downloads are limited to 20 MB")

    info = get_file(image["file_id"])
    original = download_file(info["file_path"])
    cleaned, before, after, ext = process(image["filename"], original)

    filename = image["filename"]
    if not os.path.splitext(filename)[1] and ext:
        filename = f"{filename}.{ext}"
    out_name = f"clean_{filename}"
    caption = clean_caption(before, after, image.get("note", ""))
    send_document(chat_id, out_name, cleaned, caption, message_id)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    log(
        "image_cleaned",
        chat=chat_id,
        message=message_id,
        file=filename,
        input=fmt_bytes(len(original)),
        output=fmt_bytes(len(cleaned)),
        removed=len(before),
        remaining=len(after),
        elapsed_ms=elapsed_ms,
    )


def handle_message(message):
    chat_id = message["chat"]["id"]
    message_id = message.get("message_id")
    text = (message.get("text") or "").strip()

    if text in ("/start", "/help"):
        log("command", chat=chat_id, message=message_id, text=text)
        send_message(
            chat_id,
            "Send me an image as a File/Document and I will return a cleaned copy.\n\n"
            "JPG, PNG, WebP, HEIC, TIFF, and GIF are supported. For best results, "
            "send photos as files instead of compressed Telegram photos.",
            message_id,
        )
        return

    image = extract_image(message)
    if not image:
        log("unsupported_message", chat=chat_id, message=message_id)
        send_message(
            chat_id,
            "Please send a supported image file: JPG, PNG, WebP, HEIC, TIFF, or GIF.",
            message_id,
        )
        return

    try:
        handle_image(message, image)
    except Exception as e:  # noqa
        log("image_error", chat=chat_id, message=message_id, error=str(e))
        send_message(chat_id, f"Could not clean that image: {e}", message_id)


def check_tools():
    missing = []
    if shutil.which(EXIFTOOL) is None:
        try:
            subprocess.run([EXIFTOOL, "-ver"], capture_output=True, check=True, timeout=10)
        except Exception:
            missing.append("exiftool")
    if shutil.which(MAGICK) is None:
        try:
            subprocess.run([MAGICK, "-version"], capture_output=True, check=True, timeout=10)
        except Exception:
            missing.append("magick")
    if missing:
        names = ", ".join(missing)
        raise SystemExit(f"Missing required tool(s): {names}")


def poll():
    check_tools()
    log("bot_started")
    print("MetaScrub Telegram bot is running. Press Ctrl+C to stop.")
    offset = None
    while True:
        payload = {"timeout": POLL_TIMEOUT, "allowed_updates": ["message"]}
        if offset is not None:
            payload["offset"] = offset
        try:
            updates = request_json("getUpdates", payload)
            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message")
                if message:
                    handle_message(message)
        except KeyboardInterrupt:
            print("\nStopped.")
            return
        except Exception as e:  # noqa
            log("polling_error", error=str(e))
            time.sleep(3)


if __name__ == "__main__":
    poll()
