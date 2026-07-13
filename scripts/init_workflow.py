#!/usr/bin/env python3
"""Initialize one resumable X-to-China-social workflow directory."""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


STAGES = [
    ("acquire", ["source.json", "source.md"]),
    ("media", ["media-manifest.json"]),
    ("diagnose", ["content-analysis.md"]),
    ("voice", ["voice-brief.md"]),
    ("rewrite", []),
    ("redraw", []),
    ("layout", []),
    ("review", []),
    ("publish", []),
]


def canonicalize(raw):
    parsed = urlparse(raw.strip())
    match = re.fullmatch(r"/(?:i/web/)?([^/]+)/status/(\d+)(?:/.*)?", parsed.path)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {
        "x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"
    } or not match:
        raise SystemExit("error: expected an X/Twitter status URL")
    handle, status_id = match.groups()
    return f"https://x.com/{handle}/status/{status_id}", handle, status_id


def main():
    parser = argparse.ArgumentParser(description="Initialize the unified X-to-China-social workflow.")
    parser.add_argument("url")
    parser.add_argument("--root", type=Path, default=Path("x-social"))
    parser.add_argument("--platform", choices=["both", "xiaohongshu", "wechat"], default="both")
    args = parser.parse_args()

    source_url, handle, status_id = canonicalize(args.url)
    job_dir = args.root / f"{handle}-{status_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    state_path = job_dir / "workflow-state.json"
    if state_path.exists():
        print(state_path.resolve())
        return

    targets = ["xiaohongshu", "wechat"] if args.platform == "both" else [args.platform]
    acquire_done = all((job_dir / name).exists() for name in ("source.json", "source.md"))
    current_stage = "media" if acquire_done else "acquire"
    stages = []
    for name, artifacts in STAGES:
        status = "pending"
        if name == "acquire" and acquire_done:
            status = "completed"
        elif name == current_stage:
            status = "in_progress"
        stages.append({"id": name, "status": status, "artifacts": artifacts, "note": None})

    state = {
        "workflow": "x-to-china-social",
        "version": 1,
        "source_url": source_url,
        "targets": targets,
        "defaults": {
            "voice": "attributed-first-person",
            "media": "archive-inspect-contextual-redraw",
            "wechat_layout": "dbs-wechat-html-required",
            "publishing": "preview-only-until-confirmed"
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "current_stage": current_stage,
        "stages": stages
    }
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(state_path.resolve())


if __name__ == "__main__":
    main()
