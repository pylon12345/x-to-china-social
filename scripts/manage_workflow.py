#!/usr/bin/env python3
"""Validate and advance an x-to-china-social V8.2 workflow ledger."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from _common import (
    ILLUSTRATION_SKILLS, MIN_INLINE_STYLES, MIN_STYLED_HEADINGS,
    MIN_STYLED_PARAGRAPHS, atomic_json as write_state, fail as die,
)


def now():
    return datetime.now(timezone.utc).isoformat()


def upgrade_v2(path, data):
    stages = data.get("stages") or []
    if not any(stage.get("id") == "sync" for stage in stages):
        review_index = next((i for i, stage in enumerate(stages) if stage.get("id") == "review"), None)
        if review_index is None:
            die("cannot migrate v2 ledger without a review stage")
        required = ["obsidian-receipt.json"]
        if "wechat" in data.get("targets", []):
            required.append("wechat-draft-receipt.json")
        sync = {"id": "sync", "status": "pending", "required_artifacts": required,
                "note": None, "completed_at": None}
        layout = next((stage for stage in stages if stage.get("id") == "layout"), None)
        if layout and layout.get("status") == "completed":
            stages[review_index].update(status="pending", note=None, completed_at=None)
            sync["status"] = "in_progress"
            data["current_stage"] = "sync"
            data["overall_status"] = "in_progress"
        stages.insert(review_index, sync)
    data["version"] = 3
    data["updated_at"] = now()
    write_state(path, data)
    return data


def upgrade_to_v4(path, data):
    targets = data.get("targets") or []
    mapping = {("wechat",): "wechat", ("xiaohongshu",): "xiaohongshu"}
    resolved = mapping.get(tuple(targets), "both" if set(targets) == {"wechat", "xiaohongshu"} else None)
    if not resolved:
        die("cannot migrate ledger with unsupported targets")
    data["version"] = 4
    data.setdefault("platform_selection", {"resolved": resolved, "mode": "legacy", "request_text": None})
    data["updated_at"] = now()
    write_state(path, data)
    return data


def upgrade_to_v8(path, data):
    """Preserve legacy stage lists while recording their original full-delivery behavior."""
    sync = next((stage for stage in data.get("stages", []) if stage.get("id") == "sync"), {})
    full = "wechat-draft-receipt.json" in sync.get("required_artifacts", [])
    data["version"] = 8
    data.setdefault("delivery", {
        "mode": "full" if full else "fast",
        "selection": "legacy",
        "request_text": None,
    })
    data["updated_at"] = now()
    write_state(path, data)
    return data


def load(job_dir):
    path = job_dir / "workflow-state.json"
    if not path.exists():
        die(f"missing {path}")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if data.get("version") == 2:
        data = upgrade_v2(path, data)
    if data.get("version") == 3:
        data = upgrade_to_v4(path, data)
    if data.get("version") == 4:
        data = upgrade_to_v8(path, data)
    if data.get("version") != 8:
        die("unsupported workflow-state version")
    return path, data


def save(path, data):
    data["updated_at"] = now()
    write_state(path, data)


def stages_by_id(data):
    stages = data.get("stages") or []
    result = {stage.get("id"): stage for stage in stages}
    if len(result) != len(stages):
        die("duplicate or missing stage id")
    return result


def validate_invariants(data):
    stages = data.get("stages") or []
    active = [stage["id"] for stage in stages if stage.get("status") in {"in_progress", "blocked"}]
    if len(active) > 1:
        die(f"multiple stages are active: {', '.join(active)}")
    if data.get("current_stage") != (active[0] if active else None):
        die("current_stage does not match the active stage")
    seen_open = False
    for stage in stages:
        status = stage.get("status")
        if status not in {"pending", "in_progress", "completed", "blocked"}:
            die(f"invalid status for {stage.get('id')}: {status}")
        if status in {"pending", "in_progress", "blocked"}:
            seen_open = True
        elif seen_open:
            die("completed stages must form a contiguous prefix")


def missing_artifacts(job_dir, stage):
    return [name for name in stage.get("required_artifacts", []) if not (job_dir / name).is_file()]


def read_json(path, label):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        die(f"invalid {label}: {exc}")


def all_true(value, names):
    return all(value.get(name) is True for name in names)


def report_errors(job_dir, data, stage):
    stage_id = stage.get("id")
    errors = []
    targets = data.get("targets", [])
    if stage_id == "preflight":
        report = read_json(job_dir / "capability-report.json", "capability report")
        if report.get("status") != "ready" or report.get("required_missing"):
            errors.append("required V8.2 skills are missing")
        if report.get("workflow_version") != 8:
            errors.append("capability report schema is not version 8")
        if report.get("release_version") != "8.2":
            errors.append("capability report is not for release V8.2")
    elif stage_id == "media":
        manifest = read_json(job_dir / "media-manifest.json", "media manifest")
        allowed = {"reuse", "transform", "reference_adapt", "recreate", "omit"}
        for item in manifest.get("items", manifest.get("media", [])):
            if item.get("decision") not in allowed:
                errors.append(f"media {item.get('id', '?')} has no final rights decision")
    elif stage_id == "rewrite":
        report = read_json(job_dir / "humanization-report.json", "humanization report")
        if report.get("status") != "passed" or report.get("skill") != "humanizer-zh":
            errors.append("humanizer-zh did not pass")
        covered = {item.get("target") for item in report.get("targets", []) if item.get("status") == "passed"}
        missing = set(targets) - covered
        if missing:
            errors.append("humanization report is missing: " + ", ".join(sorted(missing)))
        checks = report.get("fidelity_checks", {})
        if not all_true(checks, ["facts_preserved", "quotes_preserved", "source_links_preserved"]):
            errors.append("humanization fidelity checks did not pass")
    elif stage_id == "illustrate":
        report = read_json(job_dir / "illustration-report.json", "illustration report")
        if report.get("status") != "passed":
            errors.append("illustration report did not pass")
        used_skills = set(report.get("skills_used", []))
        if not used_skills or not used_skills.issubset(ILLUSTRATION_SKILLS):
            errors.append("illustration report must record supported skills_used")
        qa = report.get("qa", {})
        if not all_true(qa, ["facts_preserved", "originality", "mobile_readability"]):
            errors.append("illustration QA did not pass")
        manifest_path = job_dir / "media-manifest.json"
        if manifest_path.is_file():
            manifest = read_json(manifest_path, "media manifest")
            expected = {
                item.get("id") for item in manifest.get("items", manifest.get("media", []))
                if item.get("decision") in {"reference_adapt", "recreate"}
            }
            outputs = {item.get("source_media_id"): item for item in report.get("items", [])}
            for media_id in expected:
                item = outputs.get(media_id, {})
                for key in ("output_path", "prompt_path"):
                    relative = item.get(key)
                    if not relative or not (job_dir / relative).is_file():
                        errors.append(f"illustration {media_id} lacks {key}")
    elif stage_id == "package_media":
        package = read_json(job_dir / "platform-media-package.json", "platform media package")
        if package.get("status") != "ready":
            errors.append("platform media package is not ready")
        packaged_targets = set(package.get("platforms", {}))
        missing_targets = set(targets) - packaged_targets
        if missing_targets:
            errors.append("platform media package is missing: " + ", ".join(sorted(missing_targets)))
        for platform, payload in package.get("platforms", {}).items():
            if payload.get("article_contains_prompts") is not False:
                errors.append(f"{platform} article must not contain image prompts")
            for index, item in enumerate(payload.get("items", []), start=1):
                for key in ("image_path", "prompt_path"):
                    relative = item.get(key)
                    if not relative or not (job_dir / relative).is_file():
                        errors.append(f"{platform} media item {index} lacks {key}")
    elif stage_id == "layout" and "wechat" in targets:
        report = read_json(job_dir / "layout-validation.json", "layout validation")
        selection = read_json(job_dir / "layout-selection.json", "layout selection")
        if selection.get("status") != "selected":
            errors.append("WeChat layout version has not been selected")
        if selection.get("selected_profile") not in {"clean", "editorial", "visual"}:
            errors.append("WeChat layout selection uses an unsupported profile")
        if report.get("selected_profile") != selection.get("selected_profile"):
            errors.append("layout validation does not match the selected profile")
        if report.get("valid") is not True or report.get("source_match") is not True:
            errors.append("layout validation did not pass")
        if not report.get("formatter"):
            errors.append("layout formatter is not recorded")
        if report.get("inline_style_count", 0) < MIN_INLINE_STYLES:
            errors.append("WeChat HTML has too few inline styles")
    return errors


def delivery_errors(job_dir, data, stage):
    if stage.get("id") != "sync":
        return []
    errors = []
    obsidian_path = job_dir / "obsidian-receipt.json"
    if obsidian_path.is_file():
        receipt = read_json(obsidian_path, "Obsidian receipt")
        archived = {item.get("platform") for item in receipt.get("items", [])}
        if receipt.get("status") != "saved":
            errors.append("Obsidian receipt status is not saved")
        missing_targets = set(data.get("targets", [])) - archived
        if missing_targets:
            errors.append("Obsidian receipt is missing: " + ", ".join(sorted(missing_targets)))
        illustration_path = job_dir / "illustration-report.json"
        if illustration_path.is_file():
            illustration = read_json(illustration_path, "illustration report")
            expected_prompts = {
                item.get("prompt_path") for item in illustration.get("items", [])
                if item.get("prompt_path")
            }
            prompt_notes = receipt.get("prompt_notes", [])
            archived_prompts = {item.get("prompt_path") for item in prompt_notes}
            missing_prompts = expected_prompts - archived_prompts
            if missing_prompts:
                errors.append(
                    "Obsidian receipt is missing image prompts: " +
                    ", ".join(sorted(missing_prompts))
                )
            for item in prompt_notes:
                destination = Path(str(item.get("destination") or ""))
                if not destination.is_file():
                    errors.append(f"Obsidian prompt note is missing: {destination}")
                    continue
                actual = hashlib.sha256(destination.read_bytes()).hexdigest()
                if actual != item.get("note_sha256"):
                    errors.append(f"Obsidian prompt note hash changed: {destination}")
    full_wechat = data.get("delivery", {}).get("mode") == "full" and "wechat" in data.get("targets", [])
    if full_wechat:
        path = job_dir / "wechat-draft-receipt.json"
        if path.is_file():
            receipt = read_json(path, "WeChat draft receipt")
            if receipt.get("status") != "draft_saved" or not receipt.get("draft_id"):
                errors.append("WeChat receipt needs status=draft_saved and draft_id")
            if receipt.get("mode") not in {"official_api", "authenticated_browser", "publisher_skill"}:
                errors.append("WeChat receipt must come from a live publisher")
            if receipt.get("verified") is not True or receipt.get("unresolved_images"):
                errors.append("WeChat draft was not fully read back and verified")
            verification = receipt.get("verification", {})
            required = ["title", "body_nonempty", "source_url",
                        "adaptation_disclosure", "layout_preserved"]
            if not all_true(verification, required):
                errors.append("WeChat remote content verification did not pass")
            layout = receipt.get("remote_layout", {})
            if (layout.get("inline_style_count", 0) < MIN_INLINE_STYLES or
                    layout.get("styled_heading_count", 0) < MIN_STYLED_HEADINGS or
                    layout.get("styled_paragraph_count", 0) < MIN_STYLED_PARAGRAPHS):
                errors.append("WeChat remote draft lost its layout")
            if receipt.get("mode") == "official_api":
                intended = set(receipt.get("intended_images", []))
                uploaded = {item.get("local_path") for item in receipt.get("uploaded_images", [])
                            if item.get("local_path") and (item.get("media_id") or item.get("remote_url"))}
                missing_images = intended - uploaded
                if missing_images:
                    errors.append("WeChat images were not uploaded: " + ", ".join(sorted(missing_images)))
            elif verification.get("images_present") is not True:
                errors.append("remote draft does not show all intended images")
    return errors


def stage_errors(job_dir, data, stage):
    return report_errors(job_dir, data, stage) + delivery_errors(job_dir, data, stage)


def command_complete(job_dir, path, data, stage_id):
    stages = stages_by_id(data)
    if stage_id not in stages:
        die(f"unknown stage: {stage_id}")
    stage = stages[stage_id]
    if stage.get("status") == "completed":
        print(f"already completed: {stage_id}")
        return
    if data.get("current_stage") != stage_id or stage.get("status") != "in_progress":
        die(f"only the current in_progress stage can be completed ({data.get('current_stage')})")
    missing = missing_artifacts(job_dir, stage)
    if missing:
        die("missing required artifacts: " + ", ".join(missing))
    errors = stage_errors(job_dir, data, stage)
    if errors:
        die(f"{stage_id} gate failed: " + "; ".join(errors))
    stage.update(status="completed", note=None, completed_at=now())
    next_stage = next((item for item in data["stages"] if item["status"] == "pending"), None)
    if next_stage:
        next_stage["status"] = "in_progress"
        data["current_stage"] = next_stage["id"]
    else:
        data["current_stage"] = None
        data["overall_status"] = (
            "draft_ready" if data.get("delivery", {}).get("mode") == "full" and
            "wechat" in data.get("targets", []) else "preview_ready"
        )
    save(path, data)
    print(data.get("current_stage") or data["overall_status"])


def command_block(path, data, stage_id, note):
    stage = stages_by_id(data).get(stage_id)
    if not stage or data.get("current_stage") != stage_id or stage.get("status") != "in_progress":
        die("only the current in_progress stage can be blocked")
    if not note.strip():
        die("a blocking note is required")
    stage.update(status="blocked", note=note.strip())
    data["overall_status"] = "blocked"
    save(path, data)
    print(f"blocked: {stage_id}")


def command_resume(path, data):
    stage_id = data.get("current_stage")
    stage = stages_by_id(data).get(stage_id)
    if not stage or stage.get("status") != "blocked":
        die("current stage is not blocked")
    stage.update(status="in_progress", note=None)
    data["overall_status"] = "in_progress"
    save(path, data)
    print(f"resumed: {stage_id}")


def command_validate(job_dir, data):
    validate_invariants(data)
    failures = []
    for stage in data["stages"]:
        if stage["status"] == "completed":
            failures.extend(f"{stage['id']}: {name}" for name in missing_artifacts(job_dir, stage))
            failures.extend(f"{stage['id']}: {message}" for message in stage_errors(job_dir, data, stage))
    if failures:
        die("completed stages failed validation: " + ", ".join(failures))
    print("workflow ledger valid")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_dir", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    complete = sub.add_parser("complete")
    complete.add_argument("stage")
    block = sub.add_parser("block")
    block.add_argument("stage")
    block.add_argument("--note", required=True)
    sub.add_parser("resume")
    sub.add_parser("validate")
    sub.add_parser("status")
    args = parser.parse_args()

    path, data = load(args.job_dir)
    if args.command == "complete":
        command_complete(args.job_dir, path, data, args.stage)
    elif args.command == "block":
        command_block(path, data, args.stage, args.note)
    elif args.command == "resume":
        command_resume(path, data)
    elif args.command == "validate":
        command_validate(args.job_dir, data)
    else:
        validate_invariants(data)
        print(json.dumps({
            "overall_status": data["overall_status"],
            "current_stage": data["current_stage"],
            "targets": data["targets"],
            "delivery_mode": data.get("delivery", {}).get("mode", "full"),
            "publication": data["publication"]["status"],
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
