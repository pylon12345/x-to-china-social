# Platform trigger routing

Resolve the target once, before drafting or image generation. Record the result in `workflow-state.json.targets`. Never infer `both` from the Skill's capabilities.

## Precedence

1. Follow an explicit structured target (`--platform`) when supplied.
2. Follow explicit exclusion or “only” wording in the user's latest request.
3. Select `both` only when the latest request positively names both platforms or uses a dual-platform trigger.
4. Select the one positively named platform.
5. If no platform is named, select `wechat`.
6. If the latest wording is contradictory and cannot be resolved semantically, ask one short question before initializing.

The latest user instruction overrides older defaults. A source URL by itself is an unspecified-platform request and therefore routes to WeChat.

## Trigger archive

| Outcome | Chinese triggers and examples | English or shorthand triggers |
| --- | --- | --- |
| `wechat` | `公众号`、`微信公众号`、`微信文章`、`公众号草稿`、`保存到公众号草稿箱`、`只做公众号` | `WeChat`、`Weixin`、`mp.weixin`、`WeChat draft` |
| `xiaohongshu` | `小红书`、`红书`、`小红书笔记`、`小红书图文`、`只做小红书` | `XHS`、`RedNote`、`Redbook` |
| `both` | `公众号和小红书`、`小红书和公众号`、`公众号+小红书`、`双平台`、`两个平台`、`两边都要`、`都做` | `both`、`WeChat + XHS`、`XHS + WeChat` |
| default `wechat` | 只发 X 链接、`改写这篇`、`帮我处理`，且没有任何平台词 | no platform term |

Treat close natural-language equivalents semantically; this table is representative, not a brittle exact-match whitelist.

## Exclusions and corrections

- `不要小红书，只做公众号` -> `wechat`
- `不要公众号，只做小红书` -> `xiaohongshu`
- `先做公众号，小红书以后再说` -> `wechat`
- `这次改成小红书` -> `xiaohongshu`, even if an older message mentioned WeChat
- `不要同时写公众号和小红书` without another positive target -> `wechat` by the default rule

Do not treat a platform mentioned only inside a negated phrase as a positive trigger. Do not carry an earlier job's dual-platform target into a new URL.

## Output consequences

### WeChat only

Create `wechat-draft.md`, `wechat.md`, layout files, the selected WeChat media, an Obsidian receipt for `wechat`, and a verified WeChat draft receipt. Do not create Xiaohongshu copy or cards.

### Xiaohongshu only

Create `xiaohongshu-draft.md`, `xiaohongshu.md`, selected Xiaohongshu media/cards, and an Obsidian receipt for `xiaohongshu`. Skip WeChat layout, credential preflight, image upload, and draft-box sync.

### Both

Create both branches independently from the canonical source. Export both to Obsidian and sync only the WeChat branch to the公众号草稿箱.

## Initialization examples

```powershell
python "{baseDir}/scripts/init_workflow.py" "<X URL>" --platform wechat --root "x-social"
python "{baseDir}/scripts/init_workflow.py" "<X URL>" --platform xiaohongshu --root "x-social"
python "{baseDir}/scripts/init_workflow.py" "<X URL>" --platform both --root "x-social"
python "{baseDir}/scripts/init_workflow.py" "<X URL>" --request-text "只做小红书" --root "x-social"
```

Use `--platform` in production after semantic routing. Use `--request-text` for deterministic automation and tests. If neither option resolves a trigger, the script records `wechat` with selection mode `default`.
