# File-based workflow

## Workspace

Create one stable directory per X status:

```text
x-social/<handle>-<status-id>/
├── workflow-state.json
├── source.json
├── source.md
├── media-manifest.json
├── media/
│   ├── original/
│   ├── adapted/
│   ├── platform/xhs/
│   ├── platform/wechat/
│   ├── prompts/
│   └── redraw-brief.md         # required when any asset is recreated
├── content-analysis.md
├── voice-brief.md
├── xiaohongshu-draft.md
├── xiaohongshu.md
├── xhs-images/                 # optional output from baoyu-xhs-images
├── wechat-draft.md
├── wechat.md
├── layout-decision.md
├── wechat-formatted.html
└── wechat-preview.html
```

Use the canonical status ID as identity. Reuse the directory when the same URL is processed again.

## Orchestration rule

Treat this entire document as one workflow, not a menu of independent skills. The root `$x-to-china-social` skill owns sequencing and calls extractors, `$dbs-content`, `$humanizer-zh`, `$baoyu-article-illustrator`, `$imagegen`, `$baoyu-xhs-images`, and `$gzh-design` internally when their stage applies.

Create `workflow-state.json` with `scripts/init_workflow.py`. Set exactly one stage to `in_progress`; mark it `completed` only after its gate passes, then advance `current_stage`. Use `blocked` only for an inaccessible source or a required user confirmation. Record the blocking reason in `note` and resume from that stage without repeating earlier work.

## Stage 1: Acquire

Input: X URL.

Output: `source.json`, `source.md`, and optional `media/`.

Gate: Verify URL, author, non-empty content, thread order, and media inventory. Do not proceed from a link preview or incomplete thread without labeling the limitation.

`source.md` is an evidence artifact. Preserve source wording and post boundaries. Add no hooks, commentary, hashtags, or platform-specific framing.

## Stage 2: Archive and route media

Input: verified `source.json`.

Run `scripts/save_media.py`, inspect every available image, and follow `references/media-workflow.md`. Preserve originals and record `reuse`, `transform`, `recreate`, or `omit` before using an image in a draft. If useful new illustrations are needed, create `media/redraw-brief.md` from the source, diagnosis, voice, accepted copy, and platform layout; use `$baoyu-article-illustrator` for the plan and `$imagegen` for rendering after its required confirmation. Compress only with `$baoyu-compress-image`.

Gate: `media-manifest.json` accounts for every source media URL. Every saved file has a hash, every derivative points to its source asset, and no watermark or attribution has been removed.

## Stage 3: Recognize and diagnose

Input: `source.md`, with `source.json` only for metadata.

Use `$dbs-content` to identify the content type, core claim, reader value, information density, best platform/form, title or hook risks, expression problems, and useful information gap. Save the concise result as `content-analysis.md` using `references/content-routing.md`.

Gate: The diagnosis must distinguish source facts from editorial recommendations. It must not invent audience data, performance claims, product intent, or personal experience.

## Stage 4: Establish first-person voice

Inputs: `source.md`, `content-analysis.md`, and any user-provided background or experience.

Create `voice-brief.md` using `references/first-person.md`. Separate what the source author did from what the user thinks, learned, recommends, or genuinely tested.

Gate: Do not assign the source author's actions, results, credentials, screenshots, metrics, or media to the user. If the user has not supplied a personal test, use attributed commentary mode.

## Stage 5: Adapt and humanize

Inputs: `source.md`, `content-analysis.md`, and `voice-brief.md`. Use `source.json` for metadata and media paths.

Initial outputs:

- `xiaohongshu-draft.md` for Xiaohongshu
- `wechat-draft.md` for WeChat

Create each independently using `references/adaptation.md`. Include the canonical source URL in both. Do not mutate `source.md`.

Pass each initial draft through `$humanizer-zh` and save the result as `xiaohongshu.md` or `wechat.md`. Keep the initial draft for audit and rollback.

Gate: Check attribution, factual fidelity, disclosure of translation/summary, separation of source claims from editor commentary, command/number integrity, and absence of fabricated first-person experience. Reject style edits that reduce accuracy.

## Stage 6: Layout (required for WeChat)

For Xiaohongshu cards, pass the accepted `xiaohongshu.md` and eligible mapped assets to `$baoyu-xhs-images`; store final assets in `media/platform/xhs/` or record its actual output location.

For WeChat, map eligible local images into `wechat.md`, store platform variants in `media/platform/wechat/`, then pass the Markdown to `$gzh-design`. A WeChat job is not complete at Markdown.

1. Read `$gzh-design`'s `theme-index.md`.
2. Select a registered theme automatically by content type unless the user named one.
3. Save `layout-decision.md` with theme, article type, component recipe, title, image count, and selection reason.
4. Read the selected theme library and `common-components.md` completely.
5. Assemble the clean `<section>…</section>` fragment as `wechat-formatted.html`; use only registered components and inline styles.
6. Run `validate_gzh_html.py`; fix every ERROR and punctuation WARNING to zero.
7. Run `wrap_preview.py` to create `wechat-preview.html`.

Required completion files: `wechat.md`, `layout-decision.md`, `wechat-formatted.html`, and `wechat-preview.html`.

Gate: Compare headings, paragraphs, images, source note, and disclosure against the Markdown. Formatting must not change claims.

## Stage 7: Review and publish

Show the user the Markdown draft and relevant preview. Report source URL, target platform, title, media count, theme, and validation result.

Do not publish based on an earlier general request to “搬运”. Require explicit confirmation after the final preview. On confirmation, pass `wechat.md` or the format expected by `$baoyu-post-to-wechat`; do not improvise a second HTML conversion.

## Resume rules

- `source.md` exists but source media is present and `media-manifest.json` does not exist: resume at media archival.
- `media-manifest.json` exists but contains `pending` decisions: resume at media inspection and routing.
- Any media item is `recreate` but `media/redraw-brief.md` is missing: resume at contextual redraw briefing.
- Media is absent or routed but `content-analysis.md` does not exist: resume at recognition.
- `content-analysis.md` exists but `voice-brief.md` does not: resume at first-person positioning.
- `voice-brief.md` exists but no platform initial draft exists: resume at adaptation.
- Initial draft exists but final platform Markdown does not: resume at humanization.
- `wechat.md` exists but any required layout file is missing or validation is not clean: resume at layout, preserving manual edits.
- Validated preview exists: resume at review.
- Source URL changed: create a new status directory.
- The user requests a refresh: reacquire into temporary data, compare it with the current source, and ask before replacing changed evidence.
- Before overwriting any editable or generated artifact, rename the old file to `<stem>-backup-YYYYMMDD-HHMMSS.<ext>`.

## Batch mode

For multiple URLs, create one directory per status and complete acquisition for each first. Then adapt/layout independently so one inaccessible post does not block the others. Produce a compact completion table with each URL and its last successful stage.
