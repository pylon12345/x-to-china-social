#!/usr/bin/env python3
"""Validate an acquired X source bundle and write immutable evidence files."""

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


ALLOWED_HOSTS = {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}


def fail(message):
    raise SystemExit(f"error: {message}")


def normalize_handle(value):
    handle = str(value or "").strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", handle):
        fail("author.handle must be a valid X handle")
    return handle


def canonicalize(url, author_handle):
    parsed = urlparse(str(url or "").strip())
    host = parsed.netloc.lower().split(":", 1)[0]
    match = re.fullmatch(r"/([^/]+)/status/(\d+)(?:/.*)?", parsed.path.rstrip("/"))
    if parsed.scheme not in {"http", "https"} or host not in ALLOWED_HOSTS or not match:
        fail("source_url must contain /<handle>/status/<id> on x.com or twitter.com")
    url_handle, status_id = match.groups()
    if url_handle.lower() != author_handle.lower():
        fail(f"source URL handle @{url_handle} does not match author.handle @{author_handle}")
    return f"https://x.com/{url_handle}/status/{status_id}", status_id


def validate_posts(posts, field, require_nonempty):
    if not isinstance(posts, list) or (require_nonempty and not posts):
        qualifier = "non-empty " if require_nonempty else ""
        fail(f"{field} must be a {qualifier}list")
    for index, post in enumerate(posts, 1):
        if not isinstance(post, dict):
            fail(f"{field}[{index}] must be an object")
        if not str(post.get("text", "")).strip() and not post.get("media"):
            fail(f"{field}[{index}] needs text or media")
        media = post.setdefault("media", [])
        if not isinstance(media, list):
            fail(f"{field}[{index}].media must be a list")
        post.setdefault("timestamp", None)


def validate(data):
    if not isinstance(data, dict):
        fail("input JSON must be an object")
    author = data.get("author")
    if not isinstance(author, dict):
        fail("author must be an object")
    handle = normalize_handle(author.get("handle"))
    author["handle"] = f"@{handle}"
    data["source_url"], data["status_id"] = canonicalize(data.get("source_url"), handle)
    validate_posts(data.get("posts"), "posts", True)
    data.setdefault("quoted_posts", [])
    validate_posts(data["quoted_posts"], "quoted_posts", False)
    acquisition = str(data.setdefault("acquisition", "manual")).strip().lower()
    if acquisition not in {"extractor", "browser", "chrome", "manual"}:
        fail("acquisition must be extractor, browser, chrome, or manual")
    data["acquisition"] = acquisition
    data.setdefault("fetched_at", datetime.now(timezone.utc).isoformat())
    return data


def media_lines(post):
    result = []
    for item in post.get("media", []):
        if isinstance(item, str):
            result.append(f"- Media: {item}")
        elif isinstance(item, dict):
            target = item.get("local_path") or item.get("url") or "unknown"
            alt = item.get("alt_text") or item.get("type") or "Media"
            result.append(f"- {alt}: {target}")
    return result


def render_posts(lines, posts, heading):
    for index, post in enumerate(posts, 1):
        lines.extend([f"## {heading} {index}", ""])
        text = str(post.get("text", "")).strip()
        if text:
            lines.extend([text, ""])
        media = media_lines(post)
        if media:
            lines.extend(media + [""])


def markdown(data):
    author = data["author"]
    name = str(author.get("name", "")).strip()
    handle = author["handle"]
    title = f"{name} ({handle})" if name else handle
    lines = [
        "---",
        f'source_url: {json.dumps(data["source_url"], ensure_ascii=False)}',
        f'status_id: {json.dumps(data["status_id"])}',
        f'acquisition: {json.dumps(data["acquisition"], ensure_ascii=False)}',
        f'author: {json.dumps(title, ensure_ascii=False)}',
        f'fetched_at: {json.dumps(data["fetched_at"], ensure_ascii=False)}',
        "---", "", f"# {title}", "",
    ]
    render_posts(lines, data["posts"], "Post")
    if data["quoted_posts"]:
        lines.extend(["# Quoted context", ""])
        render_posts(lines, data["quoted_posts"], "Quoted post")
    lines.extend(["---", "", f"Source: {data['source_url']}", ""])
    return "\n".join(lines)


def backup(path):
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target = path.with_name(f"{path.stem}-backup-{timestamp}{path.suffix}")
    shutil.copy2(path, target)
    return target


def write_evidence(path, content, replace):
    payload = content.encode("utf-8") if isinstance(content, str) else content
    if path.exists():
        if path.read_bytes() == payload:
            return
        if not replace:
            fail(f"refusing to overwrite changed evidence: {path}; use --replace to back up and replace")
        backup(path)
    temp = path.with_name(path.name + ".tmp")
    temp.write_bytes(payload)
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--replace", action="store_true", help="Back up changed evidence before replacement")
    args = parser.parse_args()
    try:
        raw = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read input JSON: {exc}")
    data = validate(raw)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    write_evidence(args.output_dir / "source.json", json_payload, args.replace)
    write_evidence(args.output_dir / "source.md", markdown(data), args.replace)
    print(args.output_dir.resolve())


if __name__ == "__main__":
    main()
