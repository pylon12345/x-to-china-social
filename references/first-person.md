# First-person voice and ownership

## Purpose

Rewrite the material into the user's voice without disguising the source or transferring another person's experience to the user. “原创化” means new structure, selection, explanation, examples, and editorial judgment. It does not mean removing attribution or claiming someone else's work.

## Choose one mode

### Mode A: Attributed commentary (default)

Use when the user has not provided personal test evidence.

Allowed first-person language:

- “我最近看到一个做法……”
- “我把这套流程拆了一遍……”
- “我的理解是……”
- “如果是我，我会先……”
- “我准备按这个顺序试……”

Keep clear attribution:

- “原作者 AFei Liang 的做法是……”
- “阿哲 Phil 在原文中给出的命令是……”

Do not write “我做了 / 我测试了 / 我花了 1.5 小时 / 我的项目” unless the user supplied those facts.

### Mode B: Verified experience

Use only when the user supplies concrete notes, screenshots, files, results, or an explicit account of what they personally did.

Create a `My verified experience` section in `voice-brief.md` containing only those facts. First-person claims must trace to that section. Keep source-derived ideas attributed even when the user reproduced them.

### Mode C: Neutral summary

Use when first person would feel forced, such as news, policy, or pure reference material. The publisher may still add a short “我的观察” section.

## Write `voice-brief.md`

```markdown
# Voice brief

- Mode: attributed commentary / verified experience / neutral summary
- Publisher identity: {{作者名}} or user-provided name
- Intended reader: ...
- Personal position: what “I” think, infer, or plan
- Source-owned facts: actions, results, media, metrics, quotes belonging to the original author
- My verified experience: user-provided facts only, or “none supplied”
- Allowed first-person claims: ...
- Forbidden first-person claims: ...
- Attribution line: ...
```

## Rewrite rules

- Change the angle and structure, not just pronouns.
- Add the user's genuine analysis, decisions, comparisons, or intended application when available.
- Preserve the original link and label the output as commentary, summary, translation, or secondary creation.
- Use short quotations only when necessary. Paraphrase long source passages.
- Do not remove watermarks, author names, or provenance from source media.
- Before publishing, scan every sentence containing “我 / 我的 / 我们” and verify who actually performed the action.
