#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


def fail(message):
    raise SystemExit(f"error: {message}")


def validate(data):
    url = str(data.get("source_url", "")).strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {
        "x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"
    }:
        fail("source_url must be an x.com or twitter.com URL")
    author = data.get("author") or {}
    if not str(author.get("handle", "")).strip():
        fail("author.handle is required")
    posts = data.get("posts")
    if not isinstance(posts, list) or not posts:
        fail("posts must be a non-empty list")
    for index, post in enumerate(posts, 1):
        if not isinstance(post, dict):
            fail(f"posts[{index}] must be an object")
        if not str(post.get("text", "")).strip() and not post.get("media"):
            fail(f"posts[{index}] needs text or media")
        post.setdefault("timestamp", None)
        post.setdefault("media", [])
    data.setdefault("acquisition", "manual")
    data.setdefault("quoted_posts", [])
    data.setdefault("fetched_at", datetime.now(timezone.utc).isoformat())
    return data


def markdown(data):
    author = data["author"]
    name = str(author.get("name", "")).strip()
    handle = str(author["handle"]).strip()
    title = f"{name} ({handle})" if name else handle
    lines = ["---", f'source_url: {json.dumps(data["source_url"], ensure_ascii=False)}',
             f'acquisition: {json.dumps(data["acquisition"], ensure_ascii=False)}',
             f'author: {json.dumps(title, ensure_ascii=False)}',
             f'fetched_at: {json.dumps(data["fetched_at"], ensure_ascii=False)}', "---", "", f"# {title}", ""]
    for index, post in enumerate(data["posts"], 1):
        if len(data["posts"]) > 1:
            lines.extend([f"## Post {index}", ""])
        text = str(post.get("text", "")).strip()
        if text:
            lines.extend([text, ""])
        for item in post.get("media", []):
            if isinstance(item, str):
                lines.append(f"- Media: {item}")
            elif isinstance(item, dict):
                target = item.get("local_path") or item.get("url") or "unknown"
                alt = item.get("alt_text") or item.get("type") or "Media"
                lines.append(f"- {alt}: {target}")
        if post.get("media"):
            lines.append("")
    lines.extend(["---", "", f"Source: {data['source_url']}", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Validate an X source bundle and render canonical files.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    data = validate(json.loads(args.input.read_text(encoding="utf-8")))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "source.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "source.md").write_text(markdown(data), encoding="utf-8")
    print(args.output_dir.resolve())


if __name__ == "__main__":
    main()
