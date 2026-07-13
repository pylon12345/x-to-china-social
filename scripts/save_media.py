#!/usr/bin/env python3
"""Download public media from an X source bundle without modifying originals."""

import argparse
import hashlib
import json
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


def iter_media(data):
    for collection in ("posts", "quoted_posts"):
        for post_index, post in enumerate(data.get(collection, []), 1):
            for media_index, item in enumerate(post.get("media", []), 1):
                if isinstance(item, str):
                    item = {"url": item}
                if isinstance(item, dict) and item.get("url"):
                    yield collection, post_index, media_index, item


def extension(url, content_type=None):
    query_format = parse_qs(urlparse(url).query).get("format", [""])[0]
    candidate = query_format or Path(urlparse(url).path).suffix.lstrip(".")
    candidate = re.sub(r"[^a-zA-Z0-9]", "", candidate).lower()
    if candidate in {"jpeg", "jpg", "png", "webp", "gif", "mp4", "mov"}:
        return ".jpg" if candidate == "jpeg" else f".{candidate}"
    guessed = mimetypes.guess_extension((content_type or "").split(";", 1)[0].strip())
    return ".jpg" if guessed == ".jpe" else (guessed or ".bin")


def main():
    parser = argparse.ArgumentParser(description="Archive public media listed in source.json.")
    parser.add_argument("source_json", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="Article directory; media/original and media-manifest.json are created here")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    data = json.loads(args.source_json.read_text(encoding="utf-8"))
    original_dir = args.output_dir / "media" / "original"
    original_dir.mkdir(parents=True, exist_ok=True)
    records = []

    for index, (collection, post_index, media_index, item) in enumerate(iter_media(data), 1):
        url = str(item["url"])
        record = {
            "id": f"media-{index:02d}", "source_url": url, "collection": collection,
            "post_index": post_index, "media_index": media_index,
            "media_type": item.get("type", "unknown"), "alt_text": item.get("alt_text"),
            "download_status": "pending", "local_original": None,
            "sha256": None, "mime_type": None, "bytes": None,
            "rights_review": "pending", "watermark": "unknown",
            "decision": "pending", "derivatives": []
        }
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0 (media archival workflow)"})
            with urlopen(request, timeout=args.timeout) as response:
                payload = response.read()
                mime_type = response.headers.get_content_type()
            suffix = extension(url, mime_type)
            target = original_dir / f"{index:02d}-original{suffix}"
            if target.exists():
                existing = target.read_bytes()
                if hashlib.sha256(existing).digest() != hashlib.sha256(payload).digest():
                    raise RuntimeError(f"refusing to overwrite changed original: {target.name}")
            else:
                target.write_bytes(payload)
            record.update({
                "download_status": "saved",
                "local_original": target.relative_to(args.output_dir).as_posix(),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "mime_type": mime_type,
                "bytes": len(payload)
            })
        except Exception as exc:
            record["download_status"] = "failed"
            record["error"] = str(exc)
        records.append(record)

    manifest = {
        "source_url": data.get("source_url"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "policy": "Originals are immutable. Republishing or adapting requires a separate rights review.",
        "items": records
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "media-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    saved = sum(item["download_status"] == "saved" for item in records)
    print(f"saved {saved}/{len(records)} media files; manifest: {manifest_path.resolve()}")


if __name__ == "__main__":
    main()
