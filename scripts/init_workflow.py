#!/usr/bin/env python3
"""Initialize one target-aware, delivery-aware V8.2 workflow."""

import argparse
from datetime import datetime, timezone
from pathlib import Path

from _common import atomic_json, parse_status_url
from manage_workflow import load as load_ledger


def canonicalize(raw):
    parsed = parse_status_url(raw)
    if not parsed:
        raise SystemExit("error: expected an X/Twitter status URL containing /<handle>/status/<id>")
    handle, status_id = parsed
    if handle.lower() in {"i", "home", "explore", "search"}:
        raise SystemExit("error: status URL must include the author's handle")
    return f"https://x.com/{handle}/status/{status_id}", handle, status_id


def stage_definitions(targets, delivery_mode="fast"):
    rewrite, layout = [], []
    sync = ["obsidian-receipt.json"]
    if "xiaohongshu" in targets:
        rewrite.extend(["xiaohongshu-draft.md", "xiaohongshu.md"])
    if "wechat" in targets:
        rewrite.extend(["wechat-draft.md", "wechat.md"])
        layout.extend([
            "wechat-layout-clean.html", "wechat-layout-editorial.html",
            "wechat-layout-visual.html", "layout-selection.json",
            "layout-decision.md", "layout-validation.json",
            "wechat-formatted.html", "wechat-preview.html",
        ])
        if delivery_mode == "full":
            sync.append("wechat-draft-receipt.json")
    rewrite.append("humanization-report.json")
    return [
        ("preflight", ["capability-report.json"]),
        ("acquire", ["source.json", "source.md"]),
        ("media", ["media-manifest.json"]),
        ("diagnose", ["content-analysis.md"]),
        ("voice", ["voice-brief.md"]),
        ("rewrite", rewrite),
        ("illustrate", ["illustration-report.json"]),
        ("package_media", ["platform-media-package.json"]),
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
NO_SIMULTANEOUS_TERMS = ("不要同时", "别同时", "不同时间写", "不同时间做")
FULL_DELIVERY_TERMS = (
    "保存到公众号草稿箱", "公众号草稿箱", "保存草稿", "同步公众号", "同步到公众号",
    "全流程", "完整同步", "wechatdraft", "fullsync", "fulldelivery",
)
FAST_DELIVERY_TERMS = (
    "快速模式", "只做本地", "本地预览", "不要同步", "不进草稿箱", "不保存草稿",
    "跳过草稿箱", "fast", "localonly",
)


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


def resolve_delivery(delivery, request_text):
    """Resolve fast local delivery or full remote draft sync."""
    if delivery != "auto":
        return delivery, "explicit"
    text = (request_text or "").strip().lower().replace(" ", "")
    if any(term in text for term in FAST_DELIVERY_TERMS):
        return "fast", "trigger"
    if any(term in text for term in FULL_DELIVERY_TERMS):
        return "full", "trigger"
    return "fast", "default"


def upgrade_delivery(state_path, state, requested_mode, selection_mode, request_text):
    """Upgrade an existing fast ledger to full without recreating completed artifacts."""
    current_mode = state.get("delivery", {}).get("mode", "fast")
    if current_mode == "full" or requested_mode != "full":
        return False
    if "wechat" not in state.get("targets", []):
        raise SystemExit("error: full delivery requires a WeChat target")
    state["delivery"] = {
        "mode": "full", "selection": selection_mode,
        "request_text": request_text or None,
    }
    sync = next(stage for stage in state["stages"] if stage.get("id") == "sync")
    if "wechat-draft-receipt.json" not in sync.get("required_artifacts", []):
        sync.setdefault("required_artifacts", []).append("wechat-draft-receipt.json")
    if sync.get("status") == "completed":
        sync.update(
            status="in_progress", completed_at=None,
            note="Reopened after explicit upgrade from fast to full delivery.",
        )
        review = next(stage for stage in state["stages"] if stage.get("id") == "review")
        review.update(status="pending", completed_at=None, note=None)
        state["current_stage"] = "sync"
        state["overall_status"] = "in_progress"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    atomic_json(state_path, state)
    return True


def main():
    parser = argparse.ArgumentParser(description="Initialize the X-to-China-social workflow.")
    parser.add_argument("url")
    parser.add_argument("--root", type=Path, default=Path("x-social"))
    parser.add_argument(
        "--platform", choices=["auto", "both", "xiaohongshu", "wechat"], default="auto",
        help="Target platform. auto resolves --request-text and otherwise defaults to WeChat.",
    )
    parser.add_argument("--request-text", default="", help="Natural-language routing request.")
    parser.add_argument(
        "--delivery", choices=["auto", "fast", "full"], default="auto",
        help="fast stops at local outputs plus Obsidian; full also saves a verified WeChat draft.",
    )
    args = parser.parse_args()

    source_url, handle, status_id = canonicalize(args.url)
    job_dir = args.root / f"{handle}-{status_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    state_path = job_dir / "workflow-state.json"
    if state_path.exists():
        _, state = load_ledger(job_dir)
        if state.get("source_url") != source_url:
            raise SystemExit("error: existing workflow has a different source URL")
        requested_mode, selection_mode = resolve_delivery(args.delivery, args.request_text)
        upgrade_delivery(
            state_path, state, requested_mode, selection_mode, args.request_text
        )
        print(state_path.resolve())
        return

    resolved_platform, selection_mode = resolve_platform(args.platform, args.request_text)
    delivery_mode, delivery_selection_mode = resolve_delivery(args.delivery, args.request_text)
    targets = ["xiaohongshu", "wechat"] if resolved_platform == "both" else [resolved_platform]
    timestamp = datetime.now(timezone.utc).isoformat()
    stages = [
        {
            "id": name,
            "status": "in_progress" if index == 0 else "pending",
            "required_artifacts": artifacts,
            "note": None,
            "completed_at": None,
        }
        for index, (name, artifacts) in enumerate(stage_definitions(targets, delivery_mode))
    ]
    state = {
        "workflow": "x-to-china-social", "version": 8, "release_version": "8.2",
        "source_url": source_url, "status_id": status_id, "source_handle": f"@{handle}",
        "targets": targets,
        "platform_selection": {
            "resolved": resolved_platform, "mode": selection_mode,
            "request_text": args.request_text or None,
        },
        "delivery": {
            "mode": delivery_mode, "selection": delivery_selection_mode,
            "request_text": args.request_text or None,
        },
        "overall_status": "in_progress", "current_stage": "preflight",
        "publication": {
            "status": "not_requested", "requires_explicit_confirmation": True,
            "confirmed_at": None,
        },
        "created_at": timestamp, "updated_at": timestamp, "stages": stages,
    }
    atomic_json(state_path, state)
    print(state_path.resolve())


if __name__ == "__main__":
    main()
