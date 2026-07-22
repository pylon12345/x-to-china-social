# Acquisition and verification

## Fast path and budgets

1. Run the source cache probe before any browser tool. A valid hit ends acquisition.
2. On a miss, use the Codex in-app browser once. Claim an already-open exact URL when possible; otherwise open the status permalink.
3. Read semantic article DOM and write structured JSON with `scripts/browser_source.mjs`; import it with `build_source.py`.
4. Stop as soon as the URL, author, non-empty body, thread order, and media count pass verification.
5. Use one viewport screenshot only when page state or visual content needs diagnosis. Do not OCR a long article by default.
6. If the browser cannot expose complete content, request login in the in-app browser or user-provided text/screenshots. Do not silently switch to another browser or API.

Acquisition budget per URL: one in-app-browser DOM attempt, at most one diagnostic screenshot, no engagement-metric lookup, no media download, and no unrelated-reply expansion. A reverse-engineered extractor is an explicit-consent fallback only, never the default path.

## Fields to capture

- Canonical source URL and status ID
- Display name and `@handle`
- Full visible text for each post in the thread, in chronological order
- Timestamp when visible
- Image/video URLs or downloaded local paths, including alt text when visible
- Quoted-post author, URL, and text when it materially affects meaning
- Acquisition method: `extractor`, `browser`, `chrome`, or `manual`

Engagement metrics are omitted by default because they are volatile and add requests. Record them only when the user explicitly needs them and label the observation time.

## Browser extraction

Open the status permalink, not the home feed. Follow [browser-acquisition.md](browser-acquisition.md). Identify the primary post by matching the status ID in the current URL or permalink. Read semantic `main article` regions and visible text; exclude navigation, recommendations, promoted posts, unrelated replies, and engagement metrics.

For X Articles, start at the article `h1` and preserve heading, paragraph, and list order. For ordinary posts, read `tweetText`. Extract only content media, filtering avatars and recommendation cards. Return summary counts to the model while writing the full structured result directly to disk.

For a thread, include consecutive replies authored by the same handle when they form an obvious numbered or contiguous chain. Stop at the first unrelated branch unless the original author resumes with an explicit continuation. Preserve post boundaries.

If the page shows a login wall, consent overlay, rate-limit message, or an empty shell, take one viewport screenshot for diagnosis when useful, then ask the user to sign in or provide content. A screenshot can establish visible wording but not hidden text or media URLs.

Do not reopen or reread the browser after `build_source.py` succeeds. Do not download the same media during acquisition and again during the media stage.

## Verification gate

Proceed only when all are true:

- URL contains the expected status ID, or the user explicitly supplied pasted content.
- Author handle is present, or marked unknown for manual content.
- At least one source post has non-empty text or accessible media.
- Thread order is known; otherwise label it uncertain and ask for missing parts.

Never infer missing sentences from previews, search snippets, translations, or replies.

After verification, downstream agents read `source-index.json` first. Read `source.md` once for short sources; for long sources read the listed `source-parts/` files. Treat `source-raw.md` as audit evidence, not prompt context.

## Common failures

| Symptom | Next action |
|---|---|
| Page has no primary `main article` | Verify permalink and page load; save one diagnostic screenshot |
| Login wall or empty shell | Ask the user to sign in in the Codex in-app browser |
| Replies hidden | Ask the user to expand them or provide the missing text |
| Deleted/private/age-gated content | Stop; request user-provided content |
| DOM contains only a visual chart | Save one screenshot for visual inspection; do not invent hidden labels |
| Reverse API requested as fallback | Obtain consent, call it once, and stop after successful import |

