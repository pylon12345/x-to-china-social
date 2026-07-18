#!/usr/bin/env python3
"""Export final platform Markdown and local images into an Obsidian vault."""

import argparse
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from _common import atomic_json, atomic_text, digest, fail


IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def resolve_image(job_dir, raw_value):
    """Resolve a Markdown image target to a local file inside the job, or None for remote."""
    value = raw_value.strip().strip("<>")
    if re.match(r"^(?:https?://|data:|obsidian:)", value, re.I):
        return None
    source = (job_dir / value).resolve()
    try:
        source.relative_to(job_dir.resolve())
    except ValueError:
        fail(f"image path escapes the job directory: {value}")
    if not source.is_file():
        fail(f"referenced local image is missing: {source}")
    return source


def discover_vault(explicit):
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    elif os.environ.get("OBSIDIAN_VAULT"):
        candidates.append(Path(os.environ["OBSIDIAN_VAULT"]).expanduser())
    else:
        appdata = os.environ.get("APPDATA")
        config = Path(appdata) / "obsidian" / "obsidian.json" if appdata else None
        if config and config.is_file():
            try:
                vaults = json.loads(config.read_text(encoding="utf-8")).get("vaults", {})
            except (OSError, json.JSONDecodeError) as exc:
                fail(f"cannot read Obsidian vault registry: {exc}")
            open_vaults = [Path(v["path"]) for v in vaults.values() if v.get("open") and v.get("path")]
            all_vaults = [Path(v["path"]) for v in vaults.values() if v.get("path")]
            candidates = open_vaults if len(open_vaults) == 1 else all_vaults
    existing = sorted({path.resolve() for path in candidates if path.is_dir()})
    if len(existing) != 1:
        fail("cannot choose one Obsidian vault; set OBSIDIAN_VAULT or pass --vault")
    return existing[0]


def safe_folder(value):
    folder = PurePosixPath(str(value).replace("\\", "/"))
    if folder.is_absolute() or not folder.parts or any(part in {"", ".", ".."} for part in folder.parts):
        fail("--folder must be a safe relative vault path")
    return folder


def strip_frontmatter(text):
    if not text.startswith("---\n"):
        return text.lstrip()
    end = text.find("\n---\n", 4)
    return text[end + 5 :].lstrip() if end >= 0 else text.lstrip()


def title_from_markdown(text, fallback):
    frontmatter = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    if frontmatter:
        match = re.search(r"(?m)^title:\s*[\"']?(.*?)[\"']?\s*$", frontmatter.group(1))
        if match and match.group(1).strip():
            return match.group(1).strip()
    heading = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    return heading.group(1).strip() if heading else fallback


def safe_filename(value, max_length=100):
    cleaned = INVALID_FILENAME.sub("-", value).strip(" .-")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned or "untitled")[:max_length].rstrip(" .")


def load_receipt(path):
    if not path.exists():
        return {"items": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read existing Obsidian receipt: {exc}")


def prior_items(receipt):
    return {item.get("platform"): item for item in receipt.get("items", [])}


def assert_safe_update(destination, previous):
    if not destination.exists():
        return
    if not previous or previous.get("destination") != str(destination):
        fail(f"refusing to overwrite unmanaged Obsidian note: {destination}")
    if digest(destination) != previous.get("note_sha256"):
        fail(f"Obsidian note has manual changes; refusing to overwrite: {destination}")


def copy_images(
    text, source_dir, vault, asset_folder, previous_assets,
    platform, collision_names,
):
    copied = []
    previous_by_destination = {item.get("destination"): item for item in previous_assets or []}

    def replace(match):
        alt, raw = match.groups()
        source = resolve_image(source_dir, raw)
        if source is None:
            return match.group(0)
        name = safe_filename(source.stem, 80) + source.suffix.lower()
        if name.lower() in collision_names:
            name = safe_filename(f"{platform}-{source.stem}", 80) + source.suffix.lower()
        relative = asset_folder / name
        destination = vault.joinpath(*relative.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        previous = previous_by_destination.get(str(destination))
        if destination.exists() and digest(destination) != digest(source):
            if not previous or digest(destination) != previous.get("sha256"):
                fail(f"refusing to overwrite changed Obsidian asset: {destination}")
        if not destination.exists() or digest(destination) != digest(source):
            shutil.copy2(source, destination)
        item = {
            "source": str(source),
            "destination": str(destination),
            "sha256": digest(destination),
        }
        copied.append(item)
        return f"![{alt}]({relative.as_posix()})"

    return IMAGE_RE.sub(replace, text), copied


def managed_path(job_dir, value, label):
    path = (job_dir / value).resolve()
    try:
        path.relative_to(job_dir)
    except ValueError:
        fail(f"{label} path escapes the job directory: {value}")
    if not path.is_file():
        fail(f"referenced {label} is missing: {path}")
    return path


def render_prompt_note(raw, source, item, title, created_at):
    output_path = str(item.get("output_path") or "")
    metadata = [
        "---",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"source: {json.dumps(source['source_url'], ensure_ascii=False)}",
        f"source_author: {json.dumps(source['author']['handle'], ensure_ascii=False)}",
        f"source_status_id: {json.dumps(str(source.get('status_id', '')), ensure_ascii=False)}",
        f"source_media_id: {json.dumps(str(item.get('source_media_id', '')), ensure_ascii=False)}",
        f"adaptation_mode: {json.dumps(str(item.get('mode', '')), ensure_ascii=False)}",
        f"output_path: {json.dumps(output_path, ensure_ascii=False)}",
        f"archived_at: {json.dumps(created_at, ensure_ascii=False)}",
        "tags:",
        "  - X内容库",
        "  - 配图提示词",
        "---",
        "",
        f"<!-- x-to-china-social prompt: {source.get('status_id', '')}:{item.get('prompt_path', '')} -->",
        "",
        "## 完整提示词",
        "",
        "````markdown",
        raw.rstrip(),
        "````",
        "",
    ]
    return "\n".join(metadata)


def copy_prompt_notes(job_dir, source, vault, folder, previous_notes, created_at):
    report_path = job_dir / "illustration-report.json"
    if not report_path.is_file():
        return []
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read illustration report: {exc}")
    previous_by_destination = {
        item.get("destination"): item for item in previous_notes or []
    }
    status_id = str(source.get("status_id") or "unknown")
    handle = str(source.get("author", {}).get("handle", "unknown")).lstrip("@")
    prompt_folder = folder / "_prompts" / f"{handle}-{status_id}"
    saved = []
    for index, item in enumerate(report.get("items", []), start=1):
        relative_source = item.get("prompt_path")
        if not relative_source:
            fail(f"illustration item {index} has no prompt_path")
        source_path = managed_path(job_dir, relative_source, "prompt")
        title = f"配图提示词 {index:02d} - {source_path.stem}"
        filename = safe_filename(title) + ".md"
        relative = prompt_folder / filename
        destination = vault.joinpath(*relative.parts)
        previous = previous_by_destination.get(str(destination))
        assert_safe_update(destination, previous)
        note = render_prompt_note(
            source_path.read_text(encoding="utf-8"), source, item, title, created_at
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        atomic_text(destination, note)
        saved.append({
            "source_media_id": item.get("source_media_id"),
            "mode": item.get("mode"),
            "prompt_path": str(relative_source),
            "output_path": item.get("output_path"),
            "source": str(source_path),
            "destination": str(destination),
            "vault_path": relative.as_posix(),
            "note_sha256": digest(destination),
        })
    return saved


def render_note(body, source, platform, title, created_at):
    metadata = [
        "---",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"source: {json.dumps(source['source_url'], ensure_ascii=False)}",
        f"source_author: {json.dumps(source['author']['handle'], ensure_ascii=False)}",
        f"source_status_id: {json.dumps(str(source.get('status_id', '')), ensure_ascii=False)}",
        f"platform: {json.dumps(platform, ensure_ascii=False)}",
        f"archived_at: {json.dumps(created_at, ensure_ascii=False)}",
        "tags:",
        "  - X内容库",
        f"  - {platform}",
        "---",
        "",
        f"<!-- x-to-china-social managed: {source.get('status_id', '')}:{platform} -->",
        "",
    ]
    return "\n".join(metadata) + body.rstrip() + "\n"


def selected_platforms(job_dir, requested):
    available = {
        "xiaohongshu": job_dir / "xiaohongshu.md",
        "wechat": job_dir / "wechat.md",
    }
    if requested == "auto":
        state_path = job_dir / "workflow-state.json"
        if state_path.is_file():
            targets = json.loads(state_path.read_text(encoding="utf-8")).get("targets", [])
        else:
            targets = [name for name, path in available.items() if path.is_file()]
    elif requested == "both":
        targets = list(available)
    else:
        targets = [requested]
    missing = [name for name in targets if not available[name].is_file()]
    if missing:
        fail("missing final Markdown: " + ", ".join(missing))
    return [(name, available[name]) for name in targets]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_dir", type=Path)
    parser.add_argument("--vault")
    parser.add_argument("--folder", default="X内容库")
    parser.add_argument("--platform", choices=["auto", "both", "xiaohongshu", "wechat"], default="auto")
    args = parser.parse_args()

    job_dir = args.job_dir.resolve()
    source_path = job_dir / "source.json"
    if not source_path.is_file():
        fail(f"missing {source_path}")
    source = json.loads(source_path.read_text(encoding="utf-8"))
    vault = discover_vault(args.vault)
    folder = safe_folder(args.folder)
    receipt_path = job_dir / "obsidian-receipt.json"
    old_receipt = load_receipt(receipt_path)
    previous = prior_items(old_receipt)
    timestamp = datetime.now(timezone.utc).isoformat()
    items = []
    platforms = selected_platforms(job_dir, args.platform)
    prompt_notes = copy_prompt_notes(
        job_dir, source, vault, folder, old_receipt.get("prompt_notes", []), timestamp
    )

    # Validate every local image before writing any note or asset. When two
    # platforms use the same basename for different bytes, namespace only the
    # colliding destinations so one branch cannot partially overwrite another.
    destination_sources = {}
    for platform, article_path in platforms:
        original = article_path.read_text(encoding="utf-8")
        for match in IMAGE_RE.finditer(original):
            image = resolve_image(job_dir, match.group(2))
            if image is None:
                continue
            name = (safe_filename(image.stem, 80) + image.suffix.lower()).lower()
            destination_sources.setdefault(name, set()).add(digest(image))
    collision_names = {
        name for name, hashes in destination_sources.items() if len(hashes) > 1
    }

    for platform, article_path in platforms:
        original = article_path.read_text(encoding="utf-8")
        title = title_from_markdown(original, platform)
        status_id = str(source.get("status_id") or "unknown")
        handle = str(source.get("author", {}).get("handle", "unknown")).lstrip("@")
        subfolder = folder / ("微信公众号" if platform == "wechat" else "小红书")
        filename = safe_filename(f"{title} - @{handle} - {status_id}") + ".md"
        destination = vault.joinpath(*subfolder.parts) / filename
        old_item = previous.get(platform)
        assert_safe_update(destination, old_item)
        asset_folder = folder / "_assets" / f"{handle}-{status_id}"
        body, assets = copy_images(
            strip_frontmatter(original), job_dir, vault, asset_folder,
            (old_item or {}).get("assets", []), platform, collision_names,
        )
        note = render_note(body, source, platform, title, timestamp)
        destination.parent.mkdir(parents=True, exist_ok=True)
        atomic_text(destination, note)
        items.append({
            "platform": platform,
            "source": str(article_path),
            "destination": str(destination),
            "note_sha256": digest(destination),
            "assets": assets,
        })

    receipt = {
        "status": "saved",
        "vault": str(vault),
        "folder": folder.as_posix(),
        "saved_at": timestamp,
        "items": items,
        "prompt_notes": prompt_notes,
    }
    atomic_json(receipt_path, receipt)
    print(receipt_path.resolve())


if __name__ == "__main__":
    main()
