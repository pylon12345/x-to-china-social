# Media archival and adaptation

Treat every source image as an evidence asset, not automatically as reusable publishing material.

## Archive

After `source.json` passes verification, run:

```powershell
python "{baseDir}/scripts/save_media.py" "x-social/<id>/source.json" --output-dir "x-social/<id>"
```

This creates immutable files under `media/original/` and `media-manifest.json`. A failed download remains in the manifest with its remote URL and error. Never report it as saved. Do not bypass login, access control, hotlink protection, or a private/deleted post.

Recommended asset tree:

```text
media/
├── original/       # byte-for-byte downloaded source assets; never edit
├── adapted/        # crops, resized copies, or newly recreated explanatory visuals
├── platform/
│   ├── xhs/        # final Xiaohongshu assets
│   └── wechat/     # final WeChat assets
└── prompts/        # reproducible prompts for generated/recreated images
```

Also create `media/redraw-brief.md` whenever any asset is marked `recreate`. It is the handoff contract between editorial rewriting and image generation.

## Inspect and classify

Visually inspect every saved asset and update its manifest entry before drafting:

- `evidence`: screenshot, photo, quotation card, or result that supports a claim.
- `chart`: chart, table, diagram, timeline, or workflow.
- `ui`: product or interface screenshot.
- `decorative`: cover, illustration, meme, or atmosphere image.
- `identity`: portrait, logo, trademark, branded character, or protected visual identity.

Record `rights_review`, visible watermark status, relevant private information, factual role, and one decision: `reuse`, `transform`, `recreate`, or `omit`.

## Decision rules

- `reuse`: only when permission/licence is clear or quotation is justified; keep attribution and do not imply the publisher created it.
- `transform`: crop, resize, compress, or convert format only. Never remove or cover a watermark, signature, logo, credit, or copyright notice.
- `recreate`: preferred when the source image communicates a useful idea but reuse rights are unclear. Build a genuinely new explanatory visual from verified text/data; do not closely copy composition, style, characters, or branding.
- `omit`: choose this when the image is irrelevant, sensitive, misleading, inaccessible, or cannot be used responsibly.

Evidence screenshots and charts must not be decoratively altered in ways that change meaning. UI screenshots must retain product identity and have private data redacted when necessary. For charts, verify labels and numbers against `source.md` or a separately cited data source before reconstruction.

## Generate and adapt

For every `recreate` decision, build `media/redraw-brief.md` from all of the following context:

- `source.md`: verified facts, terminology, numbers, and the original image's factual role.
- `media-manifest.json` plus visual inspection: what the source image communicates, what must be preserved, and what must not be copied.
- `content-analysis.md`: audience value, information hierarchy, and recommended content form.
- `voice-brief.md` and the accepted platform draft: the user's editorial perspective, tone, and call to action.
- platform constraints: Xiaohongshu card sequence/aspect ratio or WeChat article placement/theme.

The brief must state the image objective, verified data, prohibited invention, desired type, placement, aspect ratio, on-image language, accessibility description, attribution, and originality boundary.

Use `$baoyu-article-illustrator` with this brief to decide placement, type, density, style, and palette for new explanatory images. Respect its confirmation gate, save every prompt under `media/prompts/`, then use `$imagegen` for image creation or editing. Preserve unsuccessful candidates and regenerate to fix text; never paint over text programmatically. Use `$baoyu-compress-image` only for non-semantic size/format optimization.

Unless the user owns the image or supplies explicit permission, default to text-derived recreation instead of editing the source bitmap. The new image may express the same verified facts, but it must not pose as the original author's work.

Recreation is contextual, not cosmetic: preserve the idea or verified information that helps the adapted article, but create a new hierarchy, composition, palette, and editorial framing suitable for the chosen platform. Do not mimic a living artist's style or reproduce distinctive copyrighted characters, logos, or layouts.

## Platform mapping

- Xiaohongshu: pass accepted copy and eligible local assets to `$baoyu-xhs-images`. Put final cards in `media/platform/xhs/`; source images may be references only when rights allow.
- WeChat: map intended local images into `wechat.md` before invoking `$dbs-wechat-html`. Put final variants in `media/platform/wechat/` and verify that every intended image survives HTML conversion.
- Update `media-manifest.json` so every derivative records `path`, `kind`, `platform`, `source_asset`, `adaptation_notes`, and `attribution`.

The published source note must cover both the text and any reused source media. Newly generated visuals should be labelled as editorial illustrations when that distinction matters.
