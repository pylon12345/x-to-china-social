#!/usr/bin/env python3
"""Create or update a WeChat Official Account draft with uploaded images.

Secrets are read only from environment variables and are never written to receipts.
"""

import argparse
import hashlib
import json
import mimetypes
import os
import re
import time
import uuid
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


API = "https://api.weixin.qq.com"


class PublishError(RuntimeError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def request_json(method, url, body=None, headers=None, timeout=30):
    if isinstance(body, (dict, list)):
        body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8", **(headers or {})}
    request = Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise PublishError(f"HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise PublishError(f"network request failed: {exc}") from exc
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise PublishError("WeChat returned a non-JSON response") from exc
    if payload.get("errcode") not in (None, 0):
        raise PublishError(
            f"WeChat errcode={payload.get('errcode')} errmsg={payload.get('errmsg', '')}"
        )
    return payload


def multipart(path):
    boundary = "----xToChinaSocial" + uuid.uuid4().hex
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="{path.name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8")
    body = head + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("ascii")
    return body, {"Content-Type": f"multipart/form-data; boundary={boundary}"}


def token_cache_path():
    configured = os.environ.get("WECHAT_TOKEN_CACHE")
    if configured:
        return Path(configured).expanduser()
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME")
    return Path(base or Path.home() / ".cache") / "x-to-china-social" / "wechat-token.json"


def access_token(app_id, app_secret):
    if os.environ.get("WECHAT_ACCESS_TOKEN"):
        return os.environ["WECHAT_ACCESS_TOKEN"], "environment"
    cache = token_cache_path()
    try:
        value = json.loads(cache.read_text(encoding="utf-8-sig"))
        if value.get("app_id") == app_id and value.get("expires_at", 0) > time.time() + 180:
            return value["access_token"], "cache"
    except (OSError, KeyError, json.JSONDecodeError):
        pass
    query = urlencode({"grant_type": "client_credential", "appid": app_id, "secret": app_secret})
    payload = request_json("GET", f"{API}/cgi-bin/token?{query}")
    token = payload.get("access_token")
    if not token:
        raise PublishError("token response did not contain access_token")
    cache.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(cache, {
        "app_id": app_id,
        "access_token": token,
        "expires_at": time.time() + int(payload.get("expires_in", 7200)),
    })
    return token, "api"


class Facts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images = []
        self.title = ""
        self.h1 = ""
        self.description = ""
        self.first_p = ""
        self.capture = None
        self.buffer = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "img" and values.get("src"):
            self.images.append(values["src"])
        if tag == "meta" and values.get("name", "").lower() == "description":
            self.description = values.get("content", "")
        if tag in {"title", "h1", "p"} and self.capture is None:
            self.capture, self.buffer = tag, []

    def handle_endtag(self, tag):
        if tag != self.capture:
            return
        value = " ".join("".join(self.buffer).split())
        if tag == "title" and not self.title:
            self.title = value
        elif tag == "h1" and not self.h1:
            self.h1 = value
        elif tag == "p" and not self.first_p:
            self.first_p = value
        self.capture = None

    def handle_data(self, data):
        if self.capture:
            self.buffer.append(data)


def body_fragment(html):
    match = re.search(r"<body\b[^>]*>(.*)</body\s*>", html, flags=re.I | re.S)
    return match.group(1).strip() if match else html.strip()


def local_path(src, html_path):
    parsed = urlparse(unescape(src))
    if parsed.scheme.lower() not in {"", "file"}:
        return None
    raw = parsed.path
    if parsed.scheme == "file" and re.match(r"^/[A-Za-z]:", raw):
        raw = raw[1:]
    path = Path(raw.replace("/", os.sep))
    return (path if path.is_absolute() else html_path.parent / path).resolve()


def inspect_html(html_path):
    html = html_path.read_text(encoding="utf-8-sig")
    facts = Facts()
    facts.feed(html)
    images, unresolved = [], []
    for src in dict.fromkeys(facts.images):
        path = local_path(src, html_path)
        if path is None:
            continue
        if path.is_file():
            images.append((src, path))
        else:
            unresolved.append({"src": src, "reason": "local file not found"})
    style_block = bool(re.search(r"<style\b", html, flags=re.I))
    inline_styles = len(re.findall(r"\sstyle\s*=", body_fragment(html), flags=re.I))
    compatibility = {
        "has_style_block": style_block,
        "inline_style_count": inline_styles,
        "api_ready": not style_block or inline_styles > 0,
    }
    return html, facts, images, unresolved, compatibility


def upload(token, path, endpoint):
    body, headers = multipart(path)
    separator = "&" if "?" in endpoint else "?"
    return request_json("POST", f"{API}{endpoint}{separator}access_token={token}", body, headers)


def preflight(args, html_path, images, unresolved, compatibility):
    cover = Path(args.cover).expanduser().resolve() if args.cover else None
    checks = {
        "app_id": bool(os.environ.get("WECHAT_APP_ID")),
        "app_secret_or_token": bool(os.environ.get("WECHAT_APP_SECRET") or os.environ.get("WECHAT_ACCESS_TOKEN")),
        "account_name": bool(args.account or os.environ.get("WECHAT_ACCOUNT_NAME")),
        "html": html_path.is_file(),
        "html_api_compatible": compatibility["api_ready"],
        "cover": bool(cover and cover.is_file()) or bool(images),
        "local_images_resolved": not unresolved,
        "expected_image_count": args.expected_images is None or len(images) == args.expected_images,
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "status": "blocked" if failed else "ready",
        "mode": "official_api",
        "checks": checks,
        "failed_checks": failed,
        "html_compatibility": compatibility,
        "local_image_count": len(images),
        "expected_image_count": args.expected_images,
        "unresolved_images": unresolved,
        "notes": [
            "No network call was made.",
            "The fixed outbound IP must be in the Official Account IP whitelist.",
            "AppSecret is read only from the environment and is never stored in the job.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_dir", type=Path)
    parser.add_argument("--html", default="wechat-formatted.html")
    parser.add_argument("--cover")
    parser.add_argument("--account")
    parser.add_argument("--author", default=os.environ.get("WECHAT_ARTICLE_AUTHOR", ""))
    parser.add_argument("--digest", default="")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--expected-images", type=int, help="Fail unless HTML contains this many local body images")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-create", action="store_true")
    args = parser.parse_args()

    job_dir = args.job_dir.resolve()
    html_path = (job_dir / args.html).resolve()
    if not html_path.is_file():
        raise SystemExit(f"error: missing {html_path}")
    html, facts, images, unresolved, compatibility = inspect_html(html_path)
    report = preflight(args, html_path, images, unresolved, compatibility)
    if args.preflight:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        raise SystemExit(0 if report["status"] == "ready" else 2)

    account = args.account or os.environ.get("WECHAT_ACCOUNT_NAME", "")
    title = (facts.h1 or facts.title).strip()
    cover = Path(args.cover).expanduser().resolve() if args.cover else (images[0][1] if images else None)
    errors = []
    if not title:
        errors.append("HTML needs a non-empty <h1> or <title>")
    if not account:
        errors.append("set --account or WECHAT_ACCOUNT_NAME")
    if not cover or not cover.is_file():
        errors.append("provide --cover or include a local inline image")
    if unresolved:
        errors.append("resolve all local image paths")
    if not compatibility["api_ready"]:
        errors.append("generate API-compatible HTML with inline styles")
    if errors:
        raise SystemExit("error: " + "; ".join(errors))

    receipt_path = job_dir / "wechat-draft-receipt.json"
    intended = [str(path.relative_to(job_dir)).replace("\\", "/") for _, path in images]
    fingerprint = hashlib.sha256(html.encode("utf-8")).hexdigest()
    if args.dry_run:
        atomic_json(receipt_path, {
            "status": "simulated", "mode": "dry_run", "draft_id": None,
            "account": account, "html": args.html, "saved_at": now(),
            "content_sha256": fingerprint, "intended_images": intended,
            "uploaded_images": [], "unresolved_images": [], "verified": False,
            "note": "No network call was made; this receipt cannot pass the sync gate.",
        })
        print(receipt_path)
        return

    app_id = os.environ.get("WECHAT_APP_ID", "")
    secret = os.environ.get("WECHAT_APP_SECRET", "")
    if not app_id or (not secret and not os.environ.get("WECHAT_ACCESS_TOKEN")):
        raise SystemExit("error: set WECHAT_APP_ID and WECHAT_APP_SECRET (or WECHAT_ACCESS_TOKEN)")
    prior_id = None
    if receipt_path.is_file() and not args.force_create:
        prior = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
        if prior.get("account") != account:
            raise SystemExit("error: prior receipt belongs to another account; use --force-create intentionally")
        if prior.get("status") == "draft_saved":
            prior_id = prior.get("draft_id")

    try:
        token, token_source = access_token(app_id, secret)
        replacements, uploaded = {}, []
        for original, path in images:
            result = upload(token, path, "/cgi-bin/media/uploadimg")
            if not result.get("url"):
                raise PublishError(f"inline upload returned no URL for {path.name}")
            local = str(path.relative_to(job_dir)).replace("\\", "/")
            replacements[original] = result["url"]
            uploaded.append({"local_path": local, "media_id": None, "remote_url": result["url"]})
        cover_result = upload(token, cover, "/cgi-bin/material/add_material?type=image")
        if not cover_result.get("media_id"):
            raise PublishError("cover upload returned no media_id")
        remote_html = html
        for original, remote in replacements.items():
            remote_html = remote_html.replace(original, remote)
        state_path = job_dir / "workflow-state.json"
        source_url = args.source_url
        if not source_url and state_path.is_file():
            source_url = json.loads(state_path.read_text(encoding="utf-8-sig")).get("source_url", "")
        article = {
            "title": title[:64], "author": args.author[:16],
            "digest": (args.digest or facts.description or facts.first_p).strip()[:120],
            "content": body_fragment(remote_html), "content_source_url": source_url,
            "thumb_media_id": cover_result["media_id"],
            "need_open_comment": 0, "only_fans_can_comment": 0,
        }
        if prior_id:
            request_json("POST", f"{API}/cgi-bin/draft/update?access_token={token}", {
                "media_id": prior_id, "index": 0, "articles": article,
            })
            draft_id, operation = prior_id, "updated"
        else:
            created = request_json("POST", f"{API}/cgi-bin/draft/add?access_token={token}", {"articles": [article]})
            draft_id, operation = created.get("media_id"), "created"
            if not draft_id:
                raise PublishError("draft creation returned no media_id")
        verified = request_json("POST", f"{API}/cgi-bin/draft/get?access_token={token}", {"media_id": draft_id})
        items = verified.get("news_item") or []
        if not items or items[0].get("title") != article["title"]:
            raise PublishError("draft read-back title mismatch")
        atomic_json(receipt_path, {
            "status": "draft_saved", "mode": "official_api", "operation": operation,
            "draft_id": draft_id, "account": account, "app_id_suffix": app_id[-6:],
            "html": args.html, "saved_at": now(), "content_sha256": fingerprint,
            "title": article["title"], "cover": {
                "local_path": str(cover), "media_id": cover_result["media_id"],
                "remote_url": cover_result.get("url"),
            },
            "intended_images": intended, "uploaded_images": uploaded,
            "unresolved_images": [], "verified": True,
            "verified_item_count": len(items), "token_source": token_source,
        })
        print(receipt_path)
    except PublishError as exc:
        atomic_json(receipt_path, {
            "status": "failed", "mode": "official_api", "draft_id": draft_id,
            "account": account, "html": args.html, "failed_at": now(),
            "content_sha256": fingerprint, "intended_images": intended,
            "uploaded_images": [], "unresolved_images": intended,
            "verified": False, "error": str(exc),
            "retry_safety": "Inspect the account before force-creating after an ambiguous timeout.",
        })
        raise SystemExit(f"error: {exc}")


if __name__ == "__main__":
    main()
