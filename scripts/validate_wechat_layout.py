#!/usr/bin/env python3
"""Compare WeChat Markdown and formatted HTML, then write layout-validation.json."""

import argparse
import hashlib
import json
import re
from difflib import SequenceMatcher
from html import unescape
from pathlib import Path

from publish_wechat_draft import layout_proof, visible_text


def markdown_text(value):
    value = re.sub(r"\A---\s*.*?\s*---\s*", "", value, flags=re.S)
    value = re.sub(r"!\[[^]]*]\([^)]*\)", "", value)
    value = re.sub(r"\[([^]]+)]\([^)]*\)", r"\1", value)
    value = re.sub(r"(?m)^#{1,6}\s*", "", value)
    value = re.sub(r"[*_>`~|-]", "", value)
    return " ".join(value.split())


def compact(value):
    return re.sub(r"\s+", "", value).lower()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_dir", type=Path)
    parser.add_argument("--formatter", required=True)
    parser.add_argument("--markdown", default="wechat.md")
    parser.add_argument("--html", default="wechat-formatted.html")
    args = parser.parse_args()
    job_dir = args.job_dir.resolve()
    md_path, html_path = job_dir / args.markdown, job_dir / args.html
    if not md_path.is_file() or not html_path.is_file():
        raise SystemExit("error: WeChat Markdown or formatted HTML is missing")
    md = markdown_text(md_path.read_text(encoding="utf-8-sig"))
    html = html_path.read_text(encoding="utf-8-sig")
    selection_path = job_dir / "layout-selection.json"
    if not selection_path.is_file():
        raise SystemExit("error: select a WeChat layout version before validation")
    selection = json.loads(selection_path.read_text(encoding="utf-8-sig"))
    selected_profile = selection.get("selected_profile")
    if selection.get("status") != "selected" or selected_profile not in {"clean", "editorial", "visual"}:
        raise SystemExit("error: invalid WeChat layout selection")
    selected_path = job_dir / str(selection.get("selected_file") or "")
    if not selected_path.is_file():
        raise SystemExit("error: selected WeChat layout file is missing")
    selected_hash = hashlib.sha256(selected_path.read_bytes()).hexdigest()
    final_hash = hashlib.sha256(html_path.read_bytes()).hexdigest()
    if selected_hash != final_hash:
        raise SystemExit("error: formatted HTML does not match the selected layout version")
    rendered = visible_text(html)
    similarity = SequenceMatcher(None, compact(md), compact(rendered)).ratio()
    proof = layout_proof(html)
    source_match = similarity >= 0.82
    valid = (
        source_match and proof["inline_style_count"] >= 4 and
        proof["styled_heading_count"] >= 1 and proof["styled_paragraph_count"] >= 2
    )
    report = {
        "valid": valid,
        "source_match": source_match,
        "text_similarity": round(similarity, 4),
        "formatter": args.formatter,
        "selected_profile": selected_profile,
        "selected_file": selection.get("selected_file"),
        **proof,
        "markdown": args.markdown,
        "html": args.html,
    }
    target = job_dir / "layout-validation.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(target)
    raise SystemExit(0 if valid else 2)


if __name__ == "__main__":
    main()
