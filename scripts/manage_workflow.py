#!/usr/bin/env python3
"""Validate and advance an x-to-china-social workflow ledger."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def die(message):
    raise SystemExit(f"error: {message}")


def now():
    return datetime.now(timezone.utc).isoformat()


def write_state(path, data):
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def upgrade_v2(path, data):
    stages = data.get("stages") or []
    if any(stage.get("id") == "sync" for stage in stages):
        data["version"] = 3
        data["updated_at"] = now()
        write_state(path, data)
        return data
    review_index = next(
        (index for index, stage in enumerate(stages) if stage.get("id") == "review"),
        None,
    )
    if review_index is None:
        die("cannot migrate v2 ledger without a review stage")
    required = ["obsidian-receipt.json"]
    if "wechat" in data.get("targets", []):
        required.append("wechat-draft-receipt.json")
    sync = {
        "id": "sync",
        "status": "pending",
        "required_artifacts": required,
        "note": None,
        "completed_at": None,
    }
    layout = next((stage for stage in stages if stage.get("id") == "layout"), None)
    if layout and layout.get("status") == "completed":
        review = stages[review_index]
        review.update(status="pending", note=None, completed_at=None)
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
    if targets == ["wechat"]:
        resolved = "wechat"
    elif targets == ["xiaohongshu"]:
        resolved = "xiaohongshu"
    elif set(targets) == {"xiaohongshu", "wechat"}:
        resolved = "both"
    else:
        die("cannot migrate ledger with unsupported targets")
    data["version"] = 4
    data.setdefault("platform_selection", {
        "resolved": resolved,
        "mode": "legacy",
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
    elif data.get("version") != 4:
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
    active = [
        stage["id"] for stage in stages
        if stage.get("status") in {"in_progress", "blocked"}
    ]
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
    return [
        name for name in stage.get("required_artifacts", [])
        if not (job_dir / name).is_file()
    ]


def read_receipt(path, label):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        die(f"invalid {label} receipt: {exc}")


def delivery_errors(job_dir, data, stage):
    if stage.get("id") != "sync":
        return []
    errors = []
    obsidian_path = job_dir / "obsidian-receipt.json"
    if obsidian_path.is_file():
        receipt = read_receipt(obsidian_path, "Obsidian")
        archived = {item.get("platform") for item in receipt.get("items", [])}
        if receipt.get("status") != "saved":
            errors.append("Obsidian receipt status is not saved")
        missing_targets = set(data.get("targets", [])) - archived
        if missing_targets:
            errors.append("Obsidian receipt is missing: " + ", ".join(sorted(missing_targets)))
    if "wechat" in data.get("targets", []):
        wechat_path = job_dir / "wechat-draft-receipt.json"
        if wechat_path.is_file():
            receipt = read_receipt(wechat_path, "WeChat draft")
            if receipt.get("status") != "draft_saved" or not receipt.get("draft_id"):
                errors.append("WeChat receipt needs status=draft_saved and draft_id")
            if receipt.get("mode") not in {"official_api", "authenticated_browser", "publisher_skill"}:
                errors.append("WeChat receipt must come from a live publisher")
            if receipt.get("verified") is not True:
                errors.append("WeChat draft was not read back and verified")
            if receipt.get("unresolved_images"):
                errors.append("WeChat receipt contains unresolved images")
            intended = set(receipt.get("intended_images", []))
            uploaded = {
                item.get("local_path")
                for item in receipt.get("uploaded_images", [])
                if item.get("local_path") and (item.get("media_id") or item.get("remote_url"))
            }
            missing_images = intended - uploaded
            if missing_images:
                errors.append("WeChat images were not uploaded: " + ", ".join(sorted(missing_images)))
    return errors


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
    delivery = delivery_errors(job_dir, data, stage)
    if delivery:
        die("delivery gate failed: " + "; ".join(delivery))
    stage.update(status="completed", note=None, completed_at=now())
    next_stage = next((item for item in data["stages"] if item["status"] == "pending"), None)
    if next_stage:
        next_stage["status"] = "in_progress"
        data["current_stage"] = next_stage["id"]
    else:
        data["current_stage"] = None
        data["overall_status"] = "preview_ready"
    save(path, data)
    print(data.get("current_stage") or data["overall_status"])


def command_block(path, data, stage_id, note):
    stages = stages_by_id(data)
    stage = stages.get(stage_id)
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
            failures.extend(
                f"{stage['id']}: {name}"
                for name in missing_artifacts(job_dir, stage)
            )
            failures.extend(
                f"{stage['id']}: {message}"
                for message in delivery_errors(job_dir, data, stage)
            )
    if failures:
        die("completed stages have missing artifacts: " + ", ".join(failures))
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
            "publication": data["publication"]["status"],
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
