#!/usr/bin/env python3
"""Write a deterministic V8 capability report before source acquisition."""

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


def skill_name(path):
    try:
        head = path.read_text(encoding="utf-8-sig")[:4000]
    except OSError:
        return None
    match = re.search(r"(?m)^name:\s*[\"']?([^\"'\r\n]+)", head)
    return match.group(1).strip() if match else None


def discover():
    home = Path.home()
    codex_home = Path(os.environ.get("CODEX_HOME", home / ".codex"))
    roots = [codex_home / "skills", home / ".agents" / "skills"]
    result = {}
    for root in roots:
        if not root.is_dir():
            continue
        for skill in root.rglob("SKILL.md"):
            name = skill_name(skill)
            if name and name not in result:
                result[name] = str(skill.parent.resolve())
    return result


def choose(installed, alternatives):
    return next((name for name in alternatives if name in installed), None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_dir", type=Path)
    args = parser.parse_args()
    state_path = args.job_dir / "workflow-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    targets = state.get("targets", [])
    delivery = (state.get("delivery") or {}).get("mode", "fast")
    installed = discover()

    groups = {
        "diagnosis": ["dbs-content", "chinese-social-copywriter"],
        "humanizer": ["humanizer-zh"],
        "illustration_planner": ["baoyu-article-illustrator"],
        "cover_planner": ["baoyu-cover-image"],
        "image_renderer": ["imagegen"],
        "image_optimizer": ["baoyu-compress-image"],
    }
    if "wechat" in targets:
        groups["wechat_formatter"] = ["baoyu-markdown-to-html", "dbs-wechat-html"]
    if "xiaohongshu" in targets:
        groups["xiaohongshu_cards"] = ["baoyu-xhs-images"]
    if delivery == "full" and "wechat" in targets:
        groups["wechat_publisher"] = ["baoyu-post-to-wechat"]

    selections = {key: choose(installed, options) for key, options in groups.items()}
    missing = [key for key, value in selections.items() if value is None]
    optional = {
        "x_extractor": choose(installed, ["baoyu-danger-x-to-markdown"]),
        "markdown_formatter": choose(installed, ["baoyu-format-markdown"]),
    }
    report = {
        "status": "ready" if not missing else "blocked",
        "workflow_version": 8,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "targets": targets,
        "delivery_mode": delivery,
        "selections": selections,
        "required_missing": missing,
        "optional": optional,
        "resolved_paths": {name: installed[name] for name in set(selections.values()) if name},
    }
    target = args.job_dir / "capability-report.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(target.resolve())
    raise SystemExit(0 if report["status"] == "ready" else 2)


if __name__ == "__main__":
    main()
