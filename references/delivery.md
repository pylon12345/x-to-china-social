# Automatic delivery

Run delivery after every selected platform's final Markdown exists. Require the layout gate only when WeChat is selected. Delivery creates external drafts and knowledge-base notes; it never sends or publishes an article.

## Obsidian archive

Run:

```powershell
python "{baseDir}/scripts/export_to_obsidian.py" "<job-dir>"
```

Vault selection order:

1. `--vault "<path>"`
2. `OBSIDIAN_VAULT`
3. The single open/existing vault in Obsidian's local registry

If more than one vault remains, block `sync` and ask the user to choose once. Use `--folder` to override the default `X内容库` folder.

The script writes one note per target under `X内容库/微信公众号/` or `X内容库/小红书/`, adds source metadata and tags, copies referenced local images into `X内容库/_assets/<handle>-<status-id>/`, and writes `obsidian-receipt.json`.

It may update a note only when the previous receipt proves the note is still byte-for-byte unchanged. If the user edited the Obsidian note, stop and preserve their changes.

## WeChat draft box

For a WeChat target, create a draft after `wechat-formatted.html` passes validation.

Read [wechat-draft-api.md](wechat-draft-api.md). Run scripts/publish_wechat_draft.py --preflight before any network call. Prefer the official API when permissions and a fixed whitelisted IP are available; otherwise use an authenticated browser publisher and produce the same receipt contract.

1. Resolve the intended account and verify draft-creation support. Prefer scripts/publish_wechat_draft.py for the official API. Otherwise use a callable publisher skill or authenticated browser publisher.
2. Read every local image referenced by the final HTML/Markdown. Use only manifest items whose decision permits the selected use. Pass the image count from layout-decision.md as --expected-images and block on any mismatch.
3. Upload each intended image to the WeChat account's material/media service. Preserve the returned `media_id` or hosted URL.
4. Replace local image references in the draft payload with the returned WeChat references. Do not use `file://`, localhost, or temporary local paths.
5. Create or update a **draft**. Never call a publish/send endpoint in this stage.
6. Read the draft back when the capability permits. Verify title, body, cover, inline image count, source note, and disclosure.
7. Write `wechat-draft-receipt.json`.

Minimum receipt:

```json
{
  "status": "draft_saved",
  "mode": "official_api",
  "draft_id": "remote draft id",
  "account": "account name or id",
  "html": "wechat-formatted.html",
  "saved_at": "ISO-8601",
  "intended_images": ["media/platform/wechat/01.png"],
  "uploaded_images": [
    {
      "local_path": "media/platform/wechat/01.png",
      "media_id": "remote media id",
      "remote_url": "optional hosted URL"
    }
  ],
  "unresolved_images": [],
  "verified": true
}
```

The sync gate fails when the receipt is not from a live publisher, draft_id is missing, read-back verification is false, any intended image lacks a remote reference, or unresolved_images is non-empty. Simulated receipts never pass. A source with no intended images may use empty image arrays.

## Idempotency and updates

- Search the existing receipt first. Update the same remote draft when the publisher supports it; otherwise create a new draft and record that replacement explicitly.
- Never create duplicate drafts silently after an ambiguous timeout. Query by the prior `draft_id` or a stable source marker before retrying.
- Preserve user edits in Obsidian and remote drafts. If remote content changed after the last receipt and the capability can detect it, stop and ask before replacement.
- Keep Obsidian failure and WeChat failure independent in batch mode, but do not complete `sync` until all required target receipts pass.
