---
name: x-to-china-social
description: 将公开 X/Twitter 帖子、线程或长文改写为自然中文的微信公众号或小红书内容；包含来源归档、去 AI 味、基于原文配图的合规改编、公众号排版验证、Obsidian 归档，以及按需保存公众号草稿。用户提供 X 链接或要求搬运、翻译、改写、配图、排版、同步公众号/小红书时使用。
---

# X to China Social V8.1

![X 转中国社媒](assets/icon.svg)

这是唯一的用户入口。内部调用已安装的下游技能，按文件交接，支持断点续跑。不得声称已抓取、排版或保存草稿，除非相应的机器验收门禁已经通过。

## 默认路由

- 未指定平台：只做微信公众号。
- 明确说小红书：只做小红书；只有明确说“两边都要”才同时生成。
- 未明确说“保存/同步到公众号草稿箱”：使用 `fast`，生成本地成品、预览和 Obsidian 归档。
- 明确要求保存公众号草稿：使用 `full`，在本地验收后同步并读取远端草稿复验。
- 已完成的 `fast` 任务后来收到“发到草稿”时，重新运行 `init_workflow.py`；脚本会把账本升级为 `full` 并只重开 `sync/review`，不重复抓取、改写或生图。
- 保存草稿不是发布。群发或正式发布始终需要用户当次明确确认。

先读 [references/platform-routing.md](references/platform-routing.md)，然后初始化：

```powershell
python "{baseDir}/scripts/init_workflow.py" "<X URL>" --platform auto --delivery auto --request-text "<用户原话>" --root "x-social"
python "{baseDir}/scripts/preflight_capabilities.py" "x-social/<handle>-<status-id>"
python "{baseDir}/scripts/manage_workflow.py" "x-social/<handle>-<status-id>" complete preflight
```

只处理 `workflow-state.json` 的 `current_stage`。每阶段完成后运行 `manage_workflow.py <job-dir> complete <stage>`；门禁失败时修复产物，不要手改账本绕过。

## V8 阶段

1. `preflight`：生成 `capability-report.json`。必需技能缺失就阻断，禁止静默降级。
2. `acquire`：获取并核验原文，生成不可变的 `source.json` 和 `source.md`。
3. `media`：保存原图、目视检查并在 `media-manifest.json` 给每张图作最终决定。
4. `diagnose`：用 `chinese-social-copywriter` 生成 `content-analysis.md`，只提供编辑建议，不新增事实。
5. `voice`：生成 `voice-brief.md`，明确用户视角、受众、语气及第一人称边界。
6. `rewrite`：先写 `*-draft.md`，强制调用 `humanizer-zh` 生成最终稿和 `humanization-report.json`。
7. `illustrate`：用原文图片做构图/信息层级参考，生成原创改编图或重绘图及 `illustration-report.json`。
8. `layout`：公众号使用 `baoyu-markdown-to-html` 或 `dbs-wechat-html`，生成排版 HTML 和 `layout-validation.json`。
9. `sync`：归档 Obsidian，并将每张生成图的提示词分别保存为独立笔记；仅 `full` 模式保存公众号草稿并验证远端排版。
10. `review`：核对来源、事实、署名、图片权利、平台文件和收据。

精确产物、恢复规则和报告格式见 [references/workflow.md](references/workflow.md)。

## 原文获取

依次尝试：

1. 用户接受逆向接口免责声明时使用 `baoyu-danger-x-to-markdown`。
2. 使用应用内浏览器打开规范化 X URL。
3. 使用用户已登录的 Chrome 会话；不得索取或输出 cookie/token。
4. 仍失败时请用户提供正文或截图，并标记 `acquisition=manual`。

线程只收集原作者连续回复；引用帖保留理解正文所需上下文。删除、私密、付费内容不得绕过访问控制。字段规范见 [references/acquisition.md](references/acquisition.md)。结构化数据可运行：

```powershell
python "{baseDir}/scripts/build_source.py" input.json --output-dir "<job-dir>"
```

## 改写与去 AI 味

读 [references/content-routing.md](references/content-routing.md)、[references/first-person.md](references/first-person.md) 和 [references/adaptation.md](references/adaptation.md)。

- 初稿只能取材于 `source.md`、用户上下文和另行核验的来源。
- `humanizer-zh` 是 V8 强制环节。不得用“手工简单润色”冒充该技能已运行。
- 保留数字、命令、链接、引语、限定语和不确定性；不得把原作者经历写成用户经历。
- 使用“我看到 / 我的理解 / 我更关心的是”这类有署名边界的编辑视角。
- 发布正文默认不写“某作者分享/某作者认为”，也不设置单独的援引作者段。使用“原文提出/这套做法”的中性表达；文末仅保留规范化原文链接和“摘要改写/翻译整理”声明。作者身份仍保存在 `source.json` 与 Obsidian 元数据中，不得伪装成用户原创。
- 对照原文、初稿和终稿填 `humanization-report.json`；事实、引语、来源链接三项必须全部通过。

## 配图改编

读 [references/media-workflow.md](references/media-workflow.md)。原图永远保存为不可变证据；发布图单独输出。

- `reuse`：权利明确，可直接使用。
- `transform`：权利允许，对原图作必要处理但不去水印。
- `reference_adapt`：只参考原图的事实、构图关系和信息层级，用 `baoyu-article-illustrator`/`baoyu-cover-image` 规划，再用 `imagegen` 生成明显原创的新图。
- `recreate`：不依赖原图像素，从文章事实重新设计解释图。
- `omit`：无必要、无权利或含敏感信息。

每项 `reference_adapt`/`recreate` 必须在 `illustration-report.json` 记录原媒体 ID、提示词文件、输出文件和三项 QA：事实一致、原创性、手机可读性。需要小红书卡片时再调用 `baoyu-xhs-images`；最终图片用 `baoyu-compress-image` 优化。

每张生成图必须有独立 `prompt_path`。`export_to_obsidian.py` 会把这些提示词逐张写入 `X内容库/_prompts/<handle>-<status-id>/`，并在平台归档笔记末尾加入可点击的 Obsidian 链接；`obsidian-receipt.json.prompt_notes` 必须覆盖 `illustration-report.json` 的全部提示词。

## 公众号排版与草稿

读 [references/layout-decision-template.md](references/layout-decision-template.md)、[references/delivery.md](references/delivery.md)，完整同步还要读 [references/wechat-draft-api.md](references/wechat-draft-api.md)。

- Markdown 是可编辑内容源，HTML 是交付物；不得用泛化手写 HTML 冒充排版技能。
- 生成 `layout-decision.md`、`wechat-formatted.html`、`wechat-preview.html`，然后运行：

```powershell
python "{baseDir}/scripts/validate_wechat_layout.py" "<job-dir>" --formatter "<实际技能名>"
```

- 验证必须确认正文匹配、至少 4 个内联样式、至少 1 个带样式标题和 2 个带样式段落。
- `full` 模式优先用 `baoyu-post-to-wechat`；也可使用官方 API 脚本。保存后必须重新读取远端编辑器内容，验证标题、正文、原文出处、原文链接、改编声明、图片和排版。公开正文不强制显示原作者姓名。
- 官方 API：`publish_wechat_draft.py` 会自动读取远端草稿复验。浏览器/发布技能路径需导出编辑器 HTML 后运行 `verify_wechat_remote.py`。没有远端样式证据时不得生成成功收据。
- 微信素材接口只接受 JPG、PNG 或 GIF。预检会阻止 WebP 上传；先用 `baoyu-compress-image` 转换发布副本。更新草稿前脚本会读取旧草稿 ID，若明确返回 `40007 invalid media_id`，自动安全重建草稿。

## 交付约束

- 只生成所选平台的文件；两平台共用一次来源归档，但独立改写。
- 现有产物优先复用；覆盖用户编辑过的文件前先做时间戳备份。
- 多 URL 各建一个账本；单个 URL 失败不能阻塞其他 URL。
- 交付时说明平台、`fast/full` 模式、来源链接、主题、验收结果、Obsidian 位置；`full` 模式还要给草稿 ID 和远端排版验证结果。
- 不得删除水印、冒充原作者、隐去原文链接或改编声明，或把草稿保存说成正式发布。
