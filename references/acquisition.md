# Acquisition and verification

## Fields to capture

- Canonical source URL and status ID
- Display name and `@handle`
- Full visible text for each post in the thread, in chronological order
- Timestamp when visible
- Image/video URLs or downloaded local paths, including alt text when visible
- Quoted-post author, URL, and text when it materially affects meaning
- Acquisition method: `extractor`, `browser`, `chrome`, or `manual`

Engagement metrics are optional and volatile. Record them only when the user needs them and label the observation time.

## Browser extraction

Open the status permalink, not the home feed. Identify the primary post by matching the status ID in the current URL or permalink. Read semantic article regions and visible text; exclude navigation, recommendations, promoted posts, and unrelated replies.

For a thread, include consecutive replies authored by the same handle when they form an obvious numbered or contiguous chain. Stop at the first unrelated branch unless the original author resumes with an explicit continuation. Preserve post boundaries.

If the page shows a login wall, consent overlay, rate-limit message, or an empty shell, switch methods. A screenshot can establish visible wording but not hidden text or media URLs.

## Verification gate

Proceed only when all are true:

- URL contains the expected status ID, or the user explicitly supplied pasted content.
- Author handle is present, or marked unknown for manual content.
- At least one source post has non-empty text or accessible media.
- Thread order is known; otherwise label it uncertain and ask for missing parts.

Never infer missing sentences from previews, search snippets, translations, or replies.

## Common failures

| Symptom | Next action |
|---|---|
| Anonymous request gets 401/403/429 | Switch to browser/Chrome |
| Extractor returns empty body | Open permalink in browser |
| Replies hidden | Use logged-in Chrome or manual handoff |
| Deleted/private/age-gated content | Stop; request user-provided content |
| Video cannot download | Keep the source permalink and summarize only visible context |

