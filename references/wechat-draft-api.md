# WeChat draft connector

Use the official API when the account exposes material-management and draft permissions. Use authenticated browser automation only as a fallback.

## One-time setup

1. Enable the material and draft interfaces in the Official Account backend.
2. Obtain AppID and AppSecret from basic configuration.
3. Add the publisher machine's fixed outbound public IP to the account IP whitelist.
4. Inject credentials outside the skill and job directory:

```powershell
$env:WECHAT_APP_ID="wx..."
$env:WECHAT_APP_SECRET="..."
$env:WECHAT_ACCOUNT_NAME="公众号显示名"
```

Never paste AppSecret into a prompt or command argument. Never write it to a receipt, repository, or log. `WECHAT_ACCESS_TOKEN` may replace AppSecret for a short-lived run. `WECHAT_TOKEN_CACHE` may override the default per-user cache location.

## HTML and image contract

The official API receives an HTML body fragment, not a browser copy/paste session. Require publisher-compatible HTML with inline `style` attributes. HTML relying only on a document-level `<style>` block is acceptable for manual browser paste but must fail official-API preflight.

Every intended body image must appear as a local `img` element in `wechat-formatted.html`, and each path must resolve relative to that file. Pass the image count recorded in `layout-decision.md` through `--expected-images`; a mismatch blocks delivery. The connector uploads these files and replaces their paths with WeChat-hosted URLs. Supply a cover with `--cover`; otherwise the first local inline image becomes the cover source.

## Commands

Run the no-network preflight first:

```powershell
python "{baseDir}/scripts/publish_wechat_draft.py" "<job-dir>" --preflight --cover "<cover.png>" --expected-images <layout image count>
```

Exercise local receipt handling without a remote write:

```powershell
python "{baseDir}/scripts/publish_wechat_draft.py" "<job-dir>" --dry-run --cover "<cover.png>"
```

Create or update the remote draft:

```powershell
python "{baseDir}/scripts/publish_wechat_draft.py" "<job-dir>" --cover "<cover.png>"
```

The connector updates the prior `draft_id` when a live receipt exists for the same account. Use `--force-create` only after intentionally choosing to make a second draft. A dry-run receipt has `status=simulated` and cannot pass the sync gate.

## Deterministic API sequence

1. Acquire and cache `access_token` outside the job directory.
2. Upload each local body image and replace it with the returned hosted URL.
3. Upload the cover as permanent image material and use its `media_id` as `thumb_media_id`.
4. Call `draft/add`, or `draft/update` when a prior receipt identifies the draft.
5. Read the draft back and verify its title.
6. Write `wechat-draft-receipt.json` without credentials or tokens.

This connector never calls free-publish, mass-send, preview-send, or publish endpoints.

## Receipt requirements

A valid live receipt uses `status=draft_saved`, `mode=official_api`, a non-empty `draft_id`, `verified=true`, no unresolved images, and one hosted URL for every intended inline image. Preserve the receipt so later runs update instead of duplicating the draft.
