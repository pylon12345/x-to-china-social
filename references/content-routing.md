# Content recognition and rewrite brief

## Diagnosis output

Save `content-analysis.md` with this structure:

```markdown
# Content analysis

## Source identity
- Type: short post / thread / X Article
- Topic: ...
- Source language: ...
- Evidence completeness: complete / limited, with reason

## Editorial diagnosis
- Content form: opinion / tutorial / case study / list / news / personal story / mixed
- Core claim: one sentence
- Reader value: one sentence
- Information density: low / medium / high
- Strongest material: 2-5 concrete items from the source
- Weak or removable material: X-specific debris, repetition, or context that does not travel

## Routing
- Xiaohongshu fit: high / medium / low, with reason
- Recommended Xiaohongshu form: text note / image cards / short video script / skip
- WeChat fit: high / medium / low, with reason
- Recommended WeChat form: short article / tutorial / deep article / skip

## Rewrite brief
- Target audience: inferred and labeled as inference
- Hook direction: ...
- Structure: ...
- Tone: ...
- Must preserve: facts, numbers, links, commands, qualifications
- Must disclose: translation / summary / editorial additions
- Avoid: fabricated experience, impersonation, hype, unsupported claims
- First-person mode: attributed commentary / verified experience / neutral summary
```

## Skill roles

Use `$dbs-content` to produce editorial judgment: format fit, expression efficiency, title/hook risk, information gap, and content problems. Its rule that it does not write content remains in force.

Use the general adaptation rules to write each initial platform draft. Do not ask `$dbs-content` to violate its no-ghostwriting role.

Use `$humanizer-zh` only after the draft exists. Ask it to remove AI-like filler, formulaic contrasts, repetitive headings, excessive bolding, vague attribution, promotional language, and mechanical rhythm while preserving the requested platform style.

## Fidelity check after humanization

Compare initial and final drafts. Fail the gate when the final version:

- changes a number, date, command, path, product name, or URL;
- turns an inference into a source claim;
- adds first-person use or results not present in the source;
- removes the original author or source link;
- changes uncertainty into certainty;
- adds a recommendation that could be mistaken for the original author's view.

Read `references/first-person.md` before using “我”.
