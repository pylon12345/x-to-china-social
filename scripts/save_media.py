#!/usr/bin/env python3
"""Archive public media without losing prior inspection and rights decisions."""

import argparse
import hashlib
import ipaddress
import json
import mimetypes
import re
import socket
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from _common import atomic_json, fail


PRESERVED_FIELDS = {
    "rights_review", "watermark", "decision", "derivatives", "classification",
    "contains_private_data", "private_information", "factual_role", "inspection_notes",
    "decision_reason", "reference_use", "adaptation_constraints",
}


def iter_media(data):
    for collection in ("posts", "quoted_posts"):
        for post_index, post in enumerate(data.get(collection, []), 1):
            for media_index, item in enumerate(post.get("media", []), 1):
                if isinstance(item, str):
                    item = {"url": item}
                if isinstance(item, dict) and item.get("url"):
                    yield collection, post_index, media_index, item


def safe_url(value):
    """Reject URLs whose host (literal or resolved) is not publicly routable.

    ponytail: addresses are validated at check time, not pinned for the actual
    request, so a DNS-rebinding server could still flip records between the two
    lookups. Pin the connection address if this ever archives hostile sources.
    """
    url = str(value).strip()
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        raise RuntimeError(f"unsupported media URL: {url}")
    try:
        addresses = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None)
        except OSError as exc:
            raise RuntimeError(f"cannot resolve media host {host}: {exc}")
        addresses = {ipaddress.ip_address(info[4][0]) for info in infos}
    if not addresses or not all(address.is_global for address in addresses):
        raise RuntimeError(f"refusing non-public media URL: {url}")
    return url


class SafeRedirects(HTTPRedirectHandler):
    """Re-validate every redirect target before following it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = build_opener(SafeRedirects)


def extension(url, content_type=None):
    query_format = parse_qs(urlparse(url).query).get("format", [""])[0]
    candidate = query_format or Path(urlparse(url).path).suffix.lstrip(".")
    candidate = re.sub(r"[^a-zA-Z0-9]", "", candidate).lower()
    if candidate in {"jpeg", "jpg", "png", "webp", "gif", "mp4", "mov"}:
        return ".jpg" if candidate == "jpeg" else f".{candidate}"
    guessed = mimetypes.guess_extension((content_type or "").split(";", 1)[0].strip())
    return ".jpg" if guessed == ".jpe" else (guessed or ".bin")


def read_limited(response, max_bytes):
    length = response.headers.get("Content-Length")
    if length and int(length) > max_bytes:
        raise RuntimeError(f"media exceeds --max-bytes ({length} > {max_bytes})")
    chunks = []
    total = 0
    while True:
        chunk = response.read(min(1024 * 1024, max_bytes - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise RuntimeError(f"media exceeds --max-bytes ({max_bytes})")
        chunks.append(chunk)
    return b"".join(chunks)


def load_existing(path, source_url):
    if not path.exists():
        return None, {}
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("source_url") != source_url:
        fail("existing media manifest belongs to a different source URL")
    records = {}
    for item in manifest.get("items", []):
        key = (item.get("collection"), item.get("post_index"), item.get("media_index"))
        records[key] = item
    return manifest, records


def existing_download(job_dir, previous):
    if not previous or previous.get("download_status") != "saved" or not previous.get("local_original"):
        return None
    path = job_dir / previous["local_original"]
    if not path.is_file():
        return None
    payload_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if payload_hash != previous.get("sha256"):
        fail(f"archived original changed on disk: {path}")
    return {
        "download_status": "saved",
        "local_original": previous["local_original"],
        "sha256": payload_hash,
        "mime_type": previous.get("mime_type"),
        "bytes": path.stat().st_size,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_json", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--max-bytes", type=int, default=100 * 1024 * 1024)
    args = parser.parse_args()

    data = json.loads(args.source_json.read_text(encoding="utf-8"))
    source_url = data.get("source_url")
    if not source_url:
        fail("source.json is missing source_url")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    original_dir = args.output_dir / "media" / "original"
    original_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "media-manifest.json"
    old_manifest, previous_records = load_existing(manifest_path, source_url)
    records = []

    for index, (collection, post_index, media_index, item) in enumerate(iter_media(data), 1):
        url = str(item["url"]).strip()
        key = (collection, post_index, media_index)
        previous = previous_records.get(key)
        if previous and previous.get("source_url") != url:
            previous = None
        record = {
            "id": f"media-{index:02d}", "source_url": url, "collection": collection,
            "post_index": post_index, "media_index": media_index,
            "media_type": item.get("type", "unknown"), "alt_text": item.get("alt_text"),
            "download_status": "pending", "local_original": None,
            "sha256": None, "mime_type": None, "bytes": None,
            "rights_review": "pending", "watermark": "unknown",
            "decision": "pending", "derivatives": [],
        }
        if previous:
            for field in PRESERVED_FIELDS:
                if field in previous:
                    record[field] = previous[field]
        cached = existing_download(args.output_dir, previous)
        if cached:
            record.update(cached)
            records.append(record)
            continue
        try:
            safe_url(url)
            request = Request(url, headers={"User-Agent": "Mozilla/5.0 (media archival workflow)"})
            with OPENER.open(request, timeout=args.timeout) as response:
                mime_type = response.headers.get_content_type()
                if not (mime_type.startswith("image/") or mime_type.startswith("video/") or mime_type == "application/octet-stream"):
                    raise RuntimeError(f"unexpected media content type: {mime_type}")
                payload = read_limited(response, args.max_bytes)
            suffix = extension(url, mime_type)
            target = original_dir / f"{index:02d}-original{suffix}"
            digest = hashlib.sha256(payload).hexdigest()
            if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise RuntimeError(f"refusing to overwrite changed original: {target.name}")
            if not target.exists():
                target.write_bytes(payload)
            record.update({
                "download_status": "saved",
                "local_original": target.relative_to(args.output_dir).as_posix(),
                "sha256": digest,
                "mime_type": mime_type,
                "bytes": len(payload),
            })
        except Exception as exc:
            record["download_status"] = "failed"
            record["error"] = str(exc)
        records.append(record)

    timestamp = datetime.now(timezone.utc).isoformat()
    manifest = {
        "source_url": source_url,
        "created_at": (old_manifest or {}).get("created_at", timestamp),
        "updated_at": timestamp,
        "policy": "Originals are immutable. Republishing or adapting requires a separate rights review.",
        "items": records,
    }
    atomic_json(manifest_path, manifest)
    saved = sum(item["download_status"] == "saved" for item in records)
    print(f"saved {saved}/{len(records)} media files; manifest: {manifest_path.resolve()}")


if __name__ == "__main__":
    main()
