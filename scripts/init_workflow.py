#!/usr/bin/env python3
"""Initialize one target-aware, resumable X-to-China-social workflow."""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


def canonicalize(raw):
    parsed = urlparse(raw.strip())
    host = parsed.netloc.lower().split(":", 1)[0]
    allowed = {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}
    match = re.fullmatch(r"/([^/]+)/status/(\d+)(?:/.*)?", parsed.path.rstrip("/"))
    if parsed.scheme not in {"http", "https"} or host not in allowed or not match:
        raise SystemExit("error: expected an X/Twitter status URL containing /<handle>/status/<id>")
    handle, status_id = match.groups()
    if handle.lower() in {"i", "home", "explore", "search"}:
        raise SystemExit("error: status URL must include the author's handle")
    return f"https://x.com/{handle}/status/{status_id}", handle, status_id


def stage_definitions(targets):
    rewrite = []
    layout = []
    sync = ["obsidian-receipt.json"]
    if "xiaohongshu" in targets:
        rewrite.extend(["xiaohongshu-draft.md", "xiaohongshu.md"])
    if "wechat" in targets:
        rewrite.extend(["wechat-draft.md", "wechat.md"])
        layout.extend(["layout-decision.md", "wechat-formatted.html", "wechat-preview.html"])
        sync.append("wechat-draft-receipt.json")
    return [
        ("acquire", ["source.json", "source.md"]),
        ("media", ["media-manifest.json"]),
        ("diagnose", ["content-analysis.md"]),
        ("voice", ["voice-brief.md"]),
        ("rewrite", rewrite),
        ("layout", layout),
        ("sync", sync),
        ("review", []),
    ]


WECHAT_TERMS = ("公众号", "微信公众号", "微信文章", "wechat", "weixin", "mp.weixin")
XHS_TERMS = ("小红书", "红书", "xhs", "rednote", "redbook")
BOTH_TERMS = (
    "双平台", "两个平台", "两边都", "都要", "公众号+小红书", "小红书+公众号",
    "公众号和小红书", "小红书和公众号", "wechat+xhs", "xhs+wechat", "both",
)
WECHAT_ONLY_TERMS = (
    "只做公众号", "只要公众号", "仅做公众号", "不要小红书", "不做小红书",
    "跳过小红书", "小红书以后再说", "wechatonly", "onlywechat",
)
XHS_ONLY_TERMS = (
    "只做小红书", "只要小红书", "仅做小红书", "不要公众号", "不做公众号",
    "跳过公众号", "公众号以后再说", "xhsonly", "onlyxhs", "rednoteonly",
)
NO_SIMULTANEOUS_TERMS = ("不要同时", "别同时", "不同时写", "不同时做")


def resolve_platform(platform, request_text):
    """Resolve an explicit CLI choice or a natural-language request to one target."""
    if platform != "auto":
        return platform, "explicit"

    text = (request_text or "").strip().lower().replace(" ", "")
    if not text:
        return "wechat", "default"

    if any(term in text for term in WECHAT_ONLY_TERMS):
        return "wechat", "trigger"
    if any(term in text for term in XHS_ONLY_TERMS):
        return "xiaohongshu", "trigger"
    if any(term in text for term in NO_SIMULTANEOUS_TERMS):
        return "wechat", "default"

    has_wechat = any(term in text for term in WECHAT_TERMS)
    has_xhs = any(term in text for term in XHS_TERMS)
    if any(term in text for term in BOTH_TERMS) or (has_wechat and has_xhs):
        return "both", "trigger"
    if has_xhs:
        return "xiaohongshu", "trigger"
    if has_wechat:
        return "wechat", "trigger"
    return "wechat", "default"


def main():
    parser = argparse.ArgumentParser(description="Initialize the X-to-China-social workflow.")
    parser.add_argument("url")
    parser.add_argument("--root", type=Path, default=Path("x-social"))
    parser.add_argument(
        "--platform", choices=["auto", "both", "xiaohongshu", "wechat"], default="auto",
        help="Target platform. auto resolves --request-text and otherwise defaults to WeChat.",
    )
    parser.add_argument(
        "--request-text", default="",
        help="Natural-language request used only when --platform=auto.",
    )
    args = parser.parse_args()

    source_url, handle, status_id = canonicalize(args.url)
    job_dir = args.root / f"{handle}-{status_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    state_path = job_dir / "workflow-state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("source_url") != source_url:
            raise SystemExit("error: existing workflow has a different source URL")
        print(state_path.resolve())
        return

    resolved_platform, selection_mode = resolve_platform(args.platform, args.request_text)
    targets = ["xiaohongshu", "wechat"] if resolved_platform == "both" else [resolved_platform]
    timestamp = datetime.now(timezone.utc).isoformat()
    stages = []
    for index, (name, artifacts) in enumerate(stage_definitions(targets)):
        stages.append({
            "id": name,
            "status": "in_progress" if index == 0 else "pending",
            "required_artifacts": artifacts,
            "note": None,
            "completed_at": None,
        })

    state = {
        "workflow": "x-to-china-social",
        "version": 4,
        "source_url": source_url,
        "status_id": status_id,
        "source_handle": f"@{handle}",
        "targets": targets,
        "platform_selection": {
            "resolved": resolved_platform,
            "mode": selection_mode,
            "request_text": args.request_text or None,
        },
        "overall_status": "in_progress",
        "current_stage": "acquire",
        "publication": {
            "status": "not_requested",
            "requires_explicit_confirmation": True,
            "confirmed_at": None,
        },
        "created_at": timestamp,
        "updated_at": timestamp,
        "stages": stages,
    }
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(state_path.resolve())


if __name__ == "__main__":
    main()
