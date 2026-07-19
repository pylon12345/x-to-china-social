#!/usr/bin/env python3
"""Normalize acquired X evidence without sending the full source through the model."""

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from _common import fail, parse_status_url


SINGLE_PASS_CHARS = 12000
PART_CHARS = 8000


def normalize_handle(value):
    handle = str(value or "").strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", handle):
        fail("author.handle must be a valid X handle")
    return handle


def canonicalize(url, author_handle):
    parsed = parse_status_url(url)
    if not parsed:
        fail("source_url must contain /<handle>/status/<id> on x.com or twitter.com")
    url_handle, status_id = parsed
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


def split_frontmatter(content):
    """Read the JSON-compatible frontmatter emitted by x-to-markdown."""
    normalized = content.lstrip("\ufeff")
    if not normalized.startswith("---\n"):
        fail("extractor markdown must start with YAML frontmatter")
    end = normalized.find("\n---", 4)
    if end < 0:
        fail("extractor markdown has no closing frontmatter delimiter")
    metadata = {}
    for raw_line in normalized[4:end].splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", raw_line)
        if not match:
            fail(f"unsupported extractor frontmatter line: {raw_line}")
        key, raw_value = match.groups()
        try:
            metadata[key] = json.loads(raw_value)
        except json.JSONDecodeError:
            metadata[key] = raw_value.strip().strip("'\"")
    body_start = end + len("\n---")
    return metadata, normalized[body_start:].strip()


def extractor_author(metadata, source_url):
    parsed = parse_status_url(source_url)
    if not parsed:
        fail("extractor markdown must resolve to an X status URL")
    url_handle, _ = parsed
    handle = str(metadata.get("authorUsername") or url_handle).strip().lstrip("@")
    name = str(metadata.get("authorName") or "").strip()
    if not name:
        combined = str(metadata.get("author") or "").strip()
        match = re.match(r"^(.*?)\s*\(@[A-Za-z0-9_]+\)\s*$", combined)
        if match:
            name = match.group(1).strip()
    return {"name": name or None, "handle": f"@{handle}"}


IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\((https?://[^)\s]+)(?:\s+[^)]*)?\)")


def extractor_media(metadata, body):
    items = []
    seen = set()

    def add(url, alt_text=""):
        target = str(url or "").strip()
        if not target or target in seen:
            return
        seen.add(target)
        items.append({"url": target, "alt_text": str(alt_text or "").strip() or None})

    add(metadata.get("coverImage"), "Cover image")
    for match in IMAGE_PATTERN.finditer(body):
        add(match.group(2), match.group(1))
    return items


def compact_extractor_body(body):
    """Keep image position/alt text while moving remote URLs into structured media."""
    def replace(match):
        alt = match.group(1).strip()
        return f"[Image: {alt}]" if alt else "[Image]"

    return IMAGE_PATTERN.sub(replace, body).strip()


def from_extractor_markdown(content, source_url=None):
    metadata, body = split_frontmatter(content)
    resolved_url = str(source_url or metadata.get("requestedUrl") or metadata.get("url") or "").strip()
    if not body and not metadata.get("coverImage"):
        fail("extractor markdown contains no body or media")
    return {
        "source_url": resolved_url,
        "author": extractor_author(metadata, resolved_url),
        "posts": [{
            "text": compact_extractor_body(body),
            "media": extractor_media(metadata, body),
            "timestamp": None,
        }],
        "quoted_posts": [],
        "acquisition": "extractor",
        "extractor": {
            "title": metadata.get("title"),
            "tweet_count": metadata.get("tweetCount"),
            "requested_url": metadata.get("requestedUrl"),
        },
    }


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


def source_parts(data):
    """Create deterministic, heading-aware chunks only for long sources."""
    combined = []
    for index, post in enumerate(data["posts"], 1):
        combined.append(f"# Post {index}\n\n{str(post.get('text') or '').strip()}")
    text = "\n\n".join(combined).strip()
    if len(text) <= SINGLE_PASS_CHARS:
        return []
    blocks = re.split(r"(?=^#{1,6}\s)|\n{2,}", text, flags=re.MULTILINE)
    parts, current = [], ""
    for block in (item.strip() for item in blocks if item.strip()):
        candidate = f"{current}\n\n{block}".strip() if current else block
        if current and len(candidate) > PART_CHARS:
            parts.append(current)
            current = block
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def build_index(data, json_payload, markdown_payload, part_paths):
    char_count = sum(len(str(post.get("text") or "")) for post in data["posts"])
    media_count = sum(len(post.get("media", [])) for post in data["posts"])
    return {
        "status": "ready",
        "source_url": data["source_url"],
        "status_id": data["status_id"],
        "post_count": len(data["posts"]),
        "quoted_post_count": len(data["quoted_posts"]),
        "media_count": media_count,
        "content_chars": char_count,
        "estimated_tokens": (char_count + 3) // 4,
        "reading_strategy": "single_pass" if not part_paths else "indexed_parts",
        "parts": part_paths,
        "source_json_sha256": hashlib.sha256(json_payload.encode("utf-8")).hexdigest(),
        "source_markdown_sha256": hashlib.sha256(markdown_payload.encode("utf-8")).hexdigest(),
    }


def backup(path):
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target = path.with_name(f"{path.stem}-backup-{timestamp}{path.suffix}")
    shutil.copy2(path, target)
    return target


def write_evidence(path, content, replace):
    payload = content.encode("utf-8") if isinstance(content, str) else content
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() == payload:
            return
        if not replace:
            fail(f"refusing to overwrite changed evidence: {path}; use --replace to back up and replace")
        backup(path)
    temp = path.with_name(path.name + ".tmp")
    temp.write_bytes(payload)
    temp.replace(path)


def canonical_status(raw):
    parsed = parse_status_url(raw)
    if not parsed:
        fail("expected an X/Twitter status URL")
    handle, status_id = parsed
    return f"https://x.com/{handle}/status/{status_id}", status_id


def check_existing(output_dir, expected_url):
    source_path = output_dir / "source.json"
    markdown_path = output_dir / "source.md"
    index_path = output_dir / "source-index.json"
    if not all(path.is_file() for path in (source_path, markdown_path, index_path)):
        print("cache miss: source artifacts are incomplete", file=sys.stderr)
        raise SystemExit(3)
    try:
        data = json.loads(source_path.read_text(encoding="utf-8-sig"))
        index = json.loads(index_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cache miss: invalid source artifacts: {exc}", file=sys.stderr)
        raise SystemExit(3)
    _, expected_status = canonical_status(expected_url)
    if str(data.get("status_id")) != expected_status:
        print("cache miss: source status ID differs", file=sys.stderr)
        raise SystemExit(3)
    json_digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    markdown_digest = hashlib.sha256(markdown_path.read_bytes()).hexdigest()
    if (index.get("status") != "ready" or
            index.get("source_json_sha256") != json_digest or
            index.get("source_markdown_sha256") != markdown_digest):
        print("cache miss: source hashes changed", file=sys.stderr)
        raise SystemExit(3)
    print(json.dumps({
        "cache": "hit",
        "source_url": data.get("source_url"),
        "content_chars": index.get("content_chars"),
        "estimated_tokens": index.get("estimated_tokens"),
        "reading_strategy": index.get("reading_strategy"),
    }, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, nargs="?", help="Acquired JSON or extractor Markdown")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-url", help="Original status URL; overrides extractor frontmatter")
    parser.add_argument("--check-existing", action="store_true", help="Exit 0 only for a valid cache hit")
    parser.add_argument("--replace", action="store_true", help="Back up changed evidence before replacement")
    args = parser.parse_args()
    if args.check_existing:
        if not args.source_url:
            fail("--check-existing requires --source-url")
        check_existing(args.output_dir, args.source_url)
        return
    if not args.input:
        fail("input is required unless --check-existing is used")
    try:
        content = args.input.read_text(encoding="utf-8-sig")
    except OSError as exc:
        fail(f"cannot read input: {exc}")
    if args.input.suffix.lower() in {".md", ".markdown"} or content.lstrip().startswith("---"):
        raw = from_extractor_markdown(content, args.source_url)
    else:
        try:
            raw = json.loads(content)
        except json.JSONDecodeError as exc:
            fail(f"cannot read input JSON: {exc}")
        if args.source_url:
            raw["source_url"] = args.source_url
    data = validate(raw)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    markdown_payload = markdown(data)
    if not markdown_payload.endswith("\n"):
        markdown_payload += "\n"
    parts = source_parts(data)
    part_paths = []
    for index, part in enumerate(parts, 1):
        relative = f"source-parts/part-{index:03d}.md"
        part_paths.append(relative)
        payload = part if part.endswith("\n") else part + "\n"
        write_evidence(args.output_dir / relative, payload, args.replace)
    index_payload = json.dumps(
        build_index(data, json_payload, markdown_payload, part_paths),
        ensure_ascii=False, indent=2,
    ) + "\n"
    write_evidence(args.output_dir / "source.json", json_payload, args.replace)
    write_evidence(args.output_dir / "source.md", markdown_payload, args.replace)
    write_evidence(args.output_dir / "source-index.json", index_payload, args.replace)
    print(args.output_dir.resolve())


if __name__ == "__main__":
    main()
