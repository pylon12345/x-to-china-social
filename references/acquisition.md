# Acquisition and verification

## Fast path and budgets

1. Run the source cache probe before any network or browser tool. A valid hit ends acquisition.
2. On a miss, use one extractor call without media download and import its Markdown with `build_source.py`.
3. Stop as soon as the URL, author, non-empty body, thread order, and media count pass verification.
4. If the extractor fails, use one browser method. Prefer the in-app browser for public content; use logged-in Chrome only when the public view is insufficient.
5. After two machine attempts, request pasted text or screenshots instead of continuing retries.

Acquisition budget per URL: at most one extractor call, one browser fallback, no engagement-metric lookup, no media download, and no unrelated-reply expansion. Do not load extractor Markdown into the model merely to reshape it; the importer is deterministic.

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

Open the status permalink, not the home feed. Identify the primary post by matching the status ID in the current URL or permalink. Read semantic article regions and visible text; exclude navigation, recommendations, promoted posts, and unrelated replies.

For a thread, include consecutive replies authored by the same handle when they form an obvious numbered or contiguous chain. Stop at the first unrelated branch unless the original author resumes with an explicit continuation. Preserve post boundaries.

If the page shows a login wall, consent overlay, rate-limit message, or an empty shell, switch methods. A screenshot can establish visible wording but not hidden text or media URLs.

Do not open a browser to re-verify a successful extractor result unless a required field is missing or internally inconsistent. Do not download the same media during acquisition and again during the media stage.

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
| Anonymous request gets 401/403/429 | Switch to browser/Chrome |
| Extractor returns empty body | Open permalink in browser |
| Replies hidden | Use logged-in Chrome or manual handoff |
| Deleted/private/age-gated content | Stop; request user-provided content |
| Video cannot download | Keep the source permalink and summarize only visible context |

