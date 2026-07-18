#!/usr/bin/env python3
"""Verify a browser- or skill-saved WeChat draft from exported remote editor HTML."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from publish_wechat_draft import atomic_json, inspect_html, remote_verification


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_dir", type=Path)
    parser.add_argument("--remote-html", type=Path, required=True)
    parser.add_argument("--draft-id", required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--mode", choices=["authenticated_browser", "publisher_skill"], required=True)
    args = parser.parse_args()

    job_dir = args.job_dir.resolve()
    local_path = job_dir / "wechat-formatted.html"
    if not local_path.is_file() or not args.remote_html.is_file():
        raise SystemExit("error: local or remote HTML is missing")
    local_html, _, images, unresolved, _ = inspect_html(local_path)
    remote_html = args.remote_html.read_text(encoding="utf-8-sig")
    state = json.loads((job_dir / "workflow-state.json").read_text(encoding="utf-8-sig"))
    source_url = state.get("source_url", "")
    item = {"title": args.title, "content": remote_html, "content_source_url": source_url}
    checks, remote_layout, local_layout = remote_verification(
        job_dir, local_html, item, args.title, source_url
    )
    intended = [str(path.relative_to(job_dir)).replace("\\", "/") for _, path in images]
    # The editor export cannot prove per-image uploads; verify that the remote
    # draft renders at least as many images as the local HTML intends.
    checks["images_present"] = remote_layout["image_count"] >= len(intended)
    failed = [name for name, passed in checks.items() if not passed]
    receipt = {
        "status": "draft_saved" if not failed else "failed",
        "mode": args.mode,
        "draft_id": args.draft_id,
        "account": args.account,
        "html": "wechat-formatted.html",
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "title": args.title,
        "intended_images": intended,
        "uploaded_images": [],
        "unresolved_images": unresolved,
        "verified": not failed and not unresolved,
        "verification": checks,
        "local_layout": local_layout,
        "remote_layout": remote_layout,
        "failed_checks": failed,
    }
    path = job_dir / "wechat-draft-receipt.json"
    atomic_json(path, receipt)
    print(path)
    raise SystemExit(0 if receipt["verified"] else 2)


if __name__ == "__main__":
    main()
