#!/usr/bin/env python3
"""Build platform-specific image/prompt bundles kept separate from article copy."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from _common import atomic_json, digest, fail


def load_json(path, label):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid {label}: {exc}")


def managed_file(job_dir, value, label):
    path = (job_dir / str(value or "")).resolve()
    try:
        path.relative_to(job_dir)
    except ValueError:
        fail(f"{label} escapes the job directory: {value}")
    if not path.is_file():
        fail(f"missing {label}: {value}")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_dir", type=Path)
    args = parser.parse_args()
    job_dir = args.job_dir.resolve()
    state = load_json(job_dir / "workflow-state.json", "workflow state")
    report = load_json(job_dir / "illustration-report.json", "illustration report")
    if report.get("status") != "passed":
        fail("illustration report has not passed")

    platform_items = {}
    for platform in state.get("targets", []):
        article_path = job_dir / f"{platform}.md"
        article = article_path.read_text(encoding="utf-8-sig") if article_path.is_file() else ""
        items = []
        for order, source in enumerate(report.get("items", []), start=1):
            image_path = managed_file(job_dir, source.get("output_path"), "image")
            prompt_path = managed_file(job_dir, source.get("prompt_path"), "prompt")
            prompt_text = prompt_path.read_text(encoding="utf-8-sig").strip()
            if prompt_text and prompt_text in article:
                fail(f"{platform} article contains the full prompt for media item {order}")
            items.append({
                "order": order,
                "source_media_id": source.get("source_media_id"),
                "mode": source.get("mode"),
                "image_path": image_path.relative_to(job_dir).as_posix(),
                "image_sha256": digest(image_path),
                "prompt_path": prompt_path.relative_to(job_dir).as_posix(),
                "prompt_sha256": digest(prompt_path),
            })
        platform_items[platform] = {
            "article_path": article_path.name,
            "article_contains_prompts": False,
            "items": items,
        }

    output = {
        "status": "ready",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "separation_policy": "Images and prompts are platform publishing assets, not article body content.",
        "platforms": platform_items,
    }
    destination = job_dir / "platform-media-package.json"
    atomic_json(destination, output)
    print(destination)


if __name__ == "__main__":
    main()
