#!/usr/bin/env python3
"""Shared helpers for x-to-china-social scripts."""

import hashlib
import json
import re
from urllib.parse import urlparse

# WeChat layout acceptance thresholds, shared by local validation, the sync
# gate, and remote draft read-back so they cannot drift apart.
MIN_INLINE_STYLES = 4
MIN_STYLED_HEADINGS = 1
MIN_STYLED_PARAGRAPHS = 2

STATUS_HOSTS = {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}


def fail(message):
    raise SystemExit(f"error: {message}")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_text(path, text):
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def atomic_json(path, value):
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def parse_status_url(raw):
    """Return (handle, status_id) for a canonical X status URL, or None."""
    parsed = urlparse(str(raw or "").strip())
    host = parsed.netloc.lower().split(":", 1)[0]
    match = re.fullmatch(r"/([^/]+)/status/(\d+)(?:/.*)?", parsed.path.rstrip("/"))
    if parsed.scheme not in {"http", "https"} or host not in STATUS_HOSTS or not match:
        return None
    return match.groups()
