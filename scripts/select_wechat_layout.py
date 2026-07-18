#!/usr/bin/env python3
"""Select one generated WeChat layout candidate as the delivery version."""

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path

from _common import atomic_json, atomic_text, digest


PROFILES = {
    "clean": "wechat-layout-clean.html",
    "editorial": "wechat-layout-editorial.html",
    "visual": "wechat-layout-visual.html",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_dir", type=Path)
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    job_dir = args.job_dir.resolve()

    candidates = {}
    for profile, filename in PROFILES.items():
        path = job_dir / filename
        if not path.is_file():
            raise SystemExit(f"error: missing layout candidate: {filename}")
        candidates[profile] = {"file": filename, "sha256": digest(path)}

    selected_file = PROFILES[args.profile]
    selected = job_dir / selected_file
    formatted = job_dir / "wechat-formatted.html"
    preview = job_dir / "wechat-preview.html"
    shutil.copyfile(selected, formatted)
    shutil.copyfile(selected, preview)
    timestamp = datetime.now(timezone.utc).isoformat()
    selection = {
        "status": "selected",
        "selected_profile": args.profile,
        "selected_file": selected_file,
        "reason": args.reason,
        "selected_at": timestamp,
        "candidates": candidates,
        "formatted_sha256": digest(formatted),
    }
    atomic_json(job_dir / "layout-selection.json", selection)
    decision = (
        "# 公众号排版决策\n\n"
        f"- 已选版本：`{args.profile}`\n"
        f"- 选择原因：{args.reason}\n"
        f"- 最终文件：`{selected_file}`\n"
        "- 候选版本：`clean`、`editorial`、`visual`\n"
        "- 状态：已选择，等待内容与移动端排版验证\n"
    )
    atomic_text(job_dir / "layout-decision.md", decision)
    print(job_dir / "layout-selection.json")


if __name__ == "__main__":
    main()
