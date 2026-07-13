---
name: x-to-china-social
description: Runs one resumable end-to-end workflow that fetches public X/Twitter posts, threads, and X Articles; archives and contextually redraws images; diagnoses, rewrites, and humanizes Chinese copy in an attributed first-person voice; creates Xiaohongshu assets; and produces validated GZH-themed WeChat HTML previews. Use when a user provides X URLs or asks to 搬运、翻译、改写、配图、重新制图、排版或发布到小红书/微信公众号.
---

# X to China Social

Turn X content into attributed, platform-ready Chinese deliverables through one file-based, resumable workflow. This skill is the only user-facing entry point; invoke downstream skills internally. Never claim content was fetched unless its URL, author, and body were verified.

## Single-entry contract

Accept one or more X URLs and an optional target platform. Do not require the user to invoke any downstream skill separately.

Default missing choices as follows:

- Target: both Xiaohongshu and WeChat.
- Voice: attributed first-person commentary using “我看到 / 我的理解 / 我建议”; never transfer the source author's experiences or achievements to the user.
- Media: archive originals, inspect them, and contextually recreate useful visuals when reuse rights are unclear.
- WeChat: complete `$dbs-wechat-html` layout and preview; Markdown alone is incomplete.
- Publishing: stop at reviewable local outputs until the user explicitly confirms publication.

Initialize each URL once:

```powershell
python "{baseDir}/scripts/init_workflow.py" "<X URL>" --platform both --root "x-social"
```

Use `workflow-state.json` as the orchestration ledger. Update a stage only after its gate passes, record failures and resumable notes, and preserve completed artifacts. Continue automatically through safe stages. Pause only for inaccessible source content, a downstream image skill's required generation confirmation, or final publishing approval.

## End-to-end workflow

1. Parse every supplied X URL. Accept `x.com`, `twitter.com`, and `mobile.twitter.com`; normalize to `https://x.com/<user>/status/<id>` when possible.
2. Acquire the source using the fallback ladder below. For threads, collect the author's contiguous replies in chronological order. For quoted posts, capture enough quoted context to make the source understandable.
3. Save a canonical source bundle before rewriting. Use `scripts/build_source.py` when structured fields are available. Treat `source.md` as immutable evidence; never rewrite it into platform copy in place.
4. Verify the bundle: URL/status ID, author handle, non-empty body, thread order, and media count. Mark unavailable metrics or timestamps as unknown; never invent them.
5. Archive accessible source media with `scripts/save_media.py`, then visually inspect and route each asset using [references/media-workflow.md](references/media-workflow.md). Keep originals immutable; save adaptations separately and record every relationship in `media-manifest.json`. For `recreate`, build `media/redraw-brief.md` from the verified source, content diagnosis, voice brief, accepted copy, and target-platform layout before invoking the illustration skills.
6. Diagnose `source.md` before writing. Use `$dbs-content` for content type, recommended form/platform, hook/title risks, expression efficiency, and information gap. Save the actionable diagnosis as `content-analysis.md`; do not ask it to write the draft.
7. Ask for the target only if it is not inferable: Xiaohongshu, WeChat, or both. Default to a draft, not live publishing.
8. Build `voice-brief.md` before drafting. Convert the source into the user's editorial perspective using [references/first-person.md](references/first-person.md). Default to attributed commentary such as “我看到 / 我的理解 / 我准备尝试”; never convert the source author's actions into the user's actions without user-provided evidence.
9. Adapt rather than merely translate. Read [references/adaptation.md](references/adaptation.md) and use `content-analysis.md` plus `voice-brief.md` as the brief. Write platform initial drafts.
10. Use `$humanizer-zh` on each initial draft. Preserve facts, attribution, links, commands, numbers, uncertainty, platform purpose, and the approved first-person boundary. Save the humanized result as the final platform Markdown.
11. Write outputs under `x-social/<author>-<status-id>/`: `workflow-state.json`, `source.json`, `source.md`, `media-manifest.json`, `media/original/`, `media/adapted/`, `content-analysis.md`, `voice-brief.md`, `xiaohongshu-draft.md`, `xiaohongshu.md`, `wechat-draft.md`, `wechat.md`, `wechat-formatted.html`, and `wechat-preview.html`. Follow [references/workflow.md](references/workflow.md) for stage gates and resume behavior.
12. For every WeChat output, invoke `$dbs-wechat-html`; Markdown alone is not a completed WeChat deliverable. Select a suitable built-in style such as `minimal`, `stripe`, `github`, `ft`, or `course`, generate the WeChat-ready HTML, and save `layout-decision.md`, `wechat-formatted.html`, and `wechat-preview.html`.
13. When `$dbs-wechat-html` provides multiple preview styles, choose the best fit for the article and record the style id and reason in `layout-decision.md`. Do not mark the WeChat branch complete before the HTML and preview files exist.
14. Show the draft, source link, selected theme, validation result, and formatted preview. Publish only after explicit confirmation in the current conversation.

## Acquisition fallback ladder

Attempt each viable method until one produces verifiable content. Do not stop after a blocked anonymous HTTP request.

1. **Existing extractor**: Use `$baoyu-danger-x-to-markdown` if callable and the user accepts its reverse-engineered API disclaimer. Treat authentication/rate-limit/empty-body failures as a signal to continue.
2. **In-app browser**: Use `$browser:control-in-app-browser` to open the canonical URL. If X requests login or hides replies, continue with Chrome.
3. **Logged-in Chrome**: Use `$chrome:control-chrome` with the user's existing session. Never request, print, or copy cookies/tokens. Wait for the post to render, then extract visible semantic content from the page.
4. **Manual handoff**: If automation still fails, ask the user to open the URL in their logged-in browser and paste the post/thread text or provide screenshots. Continue from that content and label acquisition as `manual`.

For exact extraction fields, thread rules, and failure diagnosis, read [references/acquisition.md](references/acquisition.md). When a page or screenshot is used, ignore replies from unrelated accounts unless necessary context.

## Canonical source bundle

Create JSON matching this minimum shape:

```json
{
  "source_url": "https://x.com/user/status/123",
  "acquisition": "browser",
  "author": {"name": "Name", "handle": "@user"},
  "posts": [{"text": "...", "timestamp": null, "media": []}],
  "quoted_posts": [],
  "fetched_at": "ISO-8601"
}
```

Run:

```powershell
python "{baseDir}/scripts/build_source.py" input.json --output-dir "x-social/123"
```

The script validates required fields and writes both `source.json` and `source.md` without changing the source wording.

## File-based orchestration

Use files, not conversational memory, to pass content between skills:

```text
X URL
  -> init_workflow.py -> workflow-state.json
  -> source.json + source.md
  -> save_media.py -> immutable originals + media-manifest.json
  -> visual inspection -> reuse / transform / recreate / omit
  -> $dbs-content -> content-analysis.md
  -> first-person positioning -> voice-brief.md
  -> platform draft -> $humanizer-zh -> final platform Markdown
  -> recreate decisions -> contextual redraw-brief.md -> $baoyu-article-illustrator -> $imagegen
  -> xiaohongshu.md + eligible assets -> $baoyu-xhs-images (optional)
  -> wechat.md + mapped local assets -> $dbs-wechat-html -> layout-decision.md + WeChat HTML preview (required)
  -> $baoyu-post-to-wechat (only after confirmation)
```

If `source.md` already exists and passes the verification gate, skip acquisition unless the user asks to refresh it. If a platform draft exists, preserve user edits and update only the requested stage. Never overwrite an existing draft or formatted HTML silently; create a timestamped backup first.

For multiple URLs, create one workflow ledger per status. Run acquisition and media archival for all reachable URLs first, then finish each platform branch independently. A failed URL must not block the other jobs.

## Recognition and rewrite contract

- Use `$dbs-content` as an editorial diagnosis, not as a ghostwriter. Convert its findings into `content-analysis.md` using [references/content-routing.md](references/content-routing.md).
- Treat the diagnosis as advice, not new evidence. Claims may come only from `source.md`, explicit user context, or separately verified sources.
- Write `*-draft.md` from `source.md` plus the diagnosis. Then use `$humanizer-zh` to produce the final filename without `-draft`.
- Reject humanizer edits that introduce personal experience, unsupported opinion, false certainty, missing attribution, changed commands, or changed numbers.
- Compare the final copy against both `source.md` and the initial draft before layout.
- Use first person only within the modes in [references/first-person.md](references/first-person.md). “Rewrite as me” authorizes voice adaptation, not false ownership of another person's work or experience.

## Platform routing

- **Xiaohongshu text note**: Write `xiaohongshu.md` with 3 title options, a strong opening, scannable short paragraphs, a practical takeaway, 5-10 relevant hashtags, and a final attribution line containing the X URL. Use first-person only when clearly framed as commentary; never impersonate the original author.
- **Xiaohongshu cards**: After the text draft is accepted, use `$baoyu-xhs-images`. Preserve local downloaded media as references when licensing/permission allows; otherwise create original explanatory visuals.
- **WeChat article**: Write `wechat.md` with frontmatter (`title`, `description`, `author`, `sourceUrl`), a contextual introduction, faithful structured body, editor commentary clearly separated from source claims, and a source note. Then use `$dbs-wechat-html` for layout. Let it recommend a built-in style unless the user named one. Use `$baoyu-post-to-wechat` only after confirmation.
- **Both**: Create the canonical source once, then make two independently adapted drafts. Do not reuse the Xiaohongshu copy as the WeChat body.

## Safety and fidelity

- Preserve links and attribution. State clearly when content is translated, summarized, or edited.
- Do not bypass authentication, CAPTCHAs, access controls, deleted/private posts, or account restrictions.
- Do not reproduce a paywalled or copyrighted long-form X Article verbatim. Summarize it with short attributed excerpts.
- Download media only when publicly accessible and needed. Preserve the byte-for-byte original, hash it, and track derivatives; do not remove watermarks or imply ownership.
- Saving an image locally does not grant republication or adaptation rights. Prefer a new text-derived explanatory visual when rights are unclear.
- Before live publishing, show destination, account if known, title, media count, and whether the action creates a draft or publishes immediately.

## Layout contract

Treat Markdown as the editable content source and generated HTML as a delivery artifact.

- Do not hand-write WeChat component HTML when `$dbs-wechat-html` is available. Follow `$dbs-wechat-html` and its built-in style library.
- Preserve the X attribution and editorial-disclosure section during layout. Do not let a generated signature imply the original X author wrote or endorsed the Chinese article.
- Keep the original author's identity in the source note. Use the user's/publication's name only in the publisher signature area.
- Ensure every source paragraph and intended image survives the Markdown-to-HTML conversion.
- Treat `wechat.md` as incomplete until `$dbs-wechat-html` produces HTML and preview output.
- In automatic workflow runs, select the theme by content type without pausing: tutorials/checklists → 摸鱼绿; case studies → 橄榄手记; analysis/opinion → 红白色系 or 石墨极简风. Record the choice and reason in `layout-decision.md`.
- Read the selected theme's complete component library and `common-components.md`; never simulate its look with generic hand-written HTML.
- Deliver `wechat.md`, `layout-decision.md`, the clean formatted HTML, and the preview HTML. Report the selected theme and validation result.
