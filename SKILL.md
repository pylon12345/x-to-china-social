---
name: x-to-china-social
description: 将公开 X/Twitter 帖子、线程或长文通过 Codex 内置浏览器提取并改写为自然中文的微信公众号或小红书内容；包含来源归档、去 AI 味、基于原文配图的合规改编、公众号排版验证、Obsidian 归档，以及按需保存公众号草稿。用户提供 X 链接或要求搬运、翻译、改写、配图、排版、同步公众号/小红书时使用。
---

# X to China Social V8.2

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

## V8.2 阶段

1. `preflight`：生成 `capability-report.json`。必需技能缺失就阻断，禁止静默降级。
2. `acquire`：先查缓存，再用 Codex 内置浏览器做 DOM 优先、截图辅助的单次获取并核验原文，生成不可变的 `source.json`、`source.md` 和轻量索引 `source-index.json`。
3. `media`：保存原图、目视检查并在 `media-manifest.json` 给每张图作最终决定。
4. `diagnose`：用 `chinese-social-copywriter` 生成 `content-analysis.md`，只提供编辑建议，不新增事实。
5. `voice`：生成 `voice-brief.md`，明确用户视角、受众、语气及第一人称边界。
6. `rewrite`：先写 `*-draft.md`，强制调用 `humanizer-zh` 生成最终稿和 `humanization-report.json`。
7. `illustrate`：用原文图片做构图/信息层级参考，生成原创改编图或重绘图及 `illustration-report.json`。
8. `package_media`：为每个目标平台生成独立贴图发布包，将图片与逐图提示词配对，禁止把提示词写入文章正文。
9. `layout`：公众号使用 `baoyu-markdown-to-html` 或 `dbs-wechat-html` 生成简洁、杂志、视觉卡片三个候选版本；选择后生成最终 HTML 和 `layout-validation.json`。
10. `sync`：归档 Obsidian，并将每张生成图的提示词分别保存为独立笔记；仅 `full` 模式保存公众号草稿并验证远端排版。
11. `review`：核对来源、事实、署名、图片权利、平台文件和收据。

精确产物、恢复规则和报告格式见 [references/workflow.md](references/workflow.md)。

## 原文获取

先探测已有来源，不要把正文读进上下文：

```powershell
python "{baseDir}/scripts/build_source.py" --check-existing --source-url "<X URL>" --output-dir "<job-dir>"
```

- 返回 `cache=hit`：直接完成 acquire；不得重新抓取或重新读取 `source.json`。
- 返回码 3：缓存未命中，继续下面的内置浏览器获取。

读取 [references/browser-acquisition.md](references/browser-acquisition.md)，使用 `browser:control-in-app-browser` 明确选择 Codex 内置浏览器。优先接管已经打开且 URL 精确匹配的标签页；没有时才新建标签页并打开状态永久链接。

正文采用 DOM 优先策略：先用 `domSnapshot()` 确认主文章存在，再导入 `scripts/browser_source.mjs`，对 `main article` 做有限的结构化投影并直接写入 `<job-dir>/browser-source.json`。不要读取整页 `body.innerText`，不要把完整 DOM 快照或全文输出塞进模型上下文。随后运行：

```powershell
python "{baseDir}/scripts/build_source.py" "<job-dir>/browser-source.json" --source-url "<X URL>" --output-dir "<job-dir>"
```

截图只用于确认页面是否加载完整、识别登录墙/弹窗、检查封面或图表；不要把长文章默认改成滚动截图 OCR。DOM 缺失时可保存一次当前视口 `source-visual.png` 做诊断。若仍无法确认完整正文，请用户在内置浏览器登录或提供正文/截图，并标记 `acquisition=manual`。

不要自动改用逆向 X API。只有用户明确同意逆向接口风险并要求回退时，才可调用 `baoyu-danger-x-to-markdown` 一次；成功后立即停止，不再用浏览器重复核验。不得索取或输出 cookie/token。

每个 URL 默认只进行 1 次内置浏览器机器获取。成功即停；不要采集互动数，不要展开推荐回复。线程只收集原作者连续回复；引用帖只保留理解正文不可缺少的上下文。删除、私密、付费内容不得绕过访问控制。字段规范见 [references/acquisition.md](references/acquisition.md)。手工或浏览器得到结构化 JSON 时运行：

```powershell
python "{baseDir}/scripts/build_source.py" input.json --output-dir "<job-dir>"
```

后续阶段先读 `source-index.json`。`reading_strategy=single_pass` 时只读 `source.md` 一次；`indexed_parts` 时按 `parts` 顺序读取 `source-parts/`，不要再重复读取 `source-raw.md` 或完整 `source.json`。`source.json` 只用于机器校验、媒体保存和最终事实抽查。

## 改写与去 AI 味

读 [references/content-routing.md](references/content-routing.md)、[references/first-person.md](references/first-person.md) 和 [references/adaptation.md](references/adaptation.md)。

- 初稿只能取材于 `source.md`、用户上下文和另行核验的来源。
- `humanizer-zh` 是 V8.2 强制环节。不得用“手工简单润色”冒充该技能已运行。
- 保留数字、命令、链接、引语、限定语和不确定性；不得把原作者经历写成用户经历。
- 使用“我看到 / 我的理解 / 我更关心的是”这类有署名边界的编辑视角。
- 发布正文默认不写“某作者分享/某作者认为”，也不设置单独的援引作者段。使用“原文提出/这套做法”的中性表达；文末仅保留规范化原文链接和“摘要改写/翻译整理”声明。作者身份仍保存在 `source.json` 与 Obsidian 元数据中，不得伪装成用户原创。
- 对照原文、初稿和终稿填 `humanization-report.json`；事实、引语、来源链接三项必须全部通过。

## 配图改编

读 [references/media-workflow.md](references/media-workflow.md)。原图永远保存为不可变证据；发布图单独输出。

- `reuse`：权利明确，可直接使用。
- `transform`：权利允许，对原图作必要处理但不去水印。
- `reference_adapt`：只参考原图的事实、构图关系和信息层级，优先用 `guizang-material-illustration` 规划归藏风解释图；也可用 `baoyu-article-illustrator`/`baoyu-cover-image`，再用 `imagegen` 生成明显原创的新图。
- `recreate`：不依赖原图像素，从文章事实重新设计解释图；流程图、机制图、数据图优先走 `guizang-material-illustration`。
- `omit`：无必要、无权利或含敏感信息。

每项 `reference_adapt`/`recreate` 必须在 `illustration-report.json` 记录原媒体 ID、提示词文件、输出文件和三项 QA：事实一致、原创性、手机可读性；`skills_used` 记录实际调用技能。需要小红书 3:4 卡片或公众号 21:9 + 1:1 封面时，优先调用 `guizang-social-card-skill`，也可用 `baoyu-xhs-images`；最终图片用 `baoyu-compress-image` 优化。

归藏配图必须遵守短中文标签、准确指向、移动端可读和无意外水印规则。文章型内容先生成归藏解释图，再交给社交卡片技能组合；不得用社交卡片技能替代正文改写，也不得用 PPT 技能生成文章配图。

每张生成图必须有独立 `prompt_path`。运行 `build_platform_media_package.py <job-dir>`，生成 `platform-media-package.json`，按目标平台逐张配对图片和提示词。图片与提示词属于独立发布资产，不得把完整提示词或提示词链接写入文章正文。`export_to_obsidian.py` 会把提示词逐张写入 `X内容库/_prompts/<handle>-<status-id>/`；`obsidian-receipt.json.prompt_notes` 必须覆盖 `illustration-report.json` 的全部提示词。

## 贴图发布包

- 每个平台独立列出图片顺序、图片路径、提示词路径和 SHA-256；双平台可共享原始生成结果，但发布顺序必须分别记录。
- 贴图包用于平台上传、人工审查和后续自动化，不代表已经发布。远端上传或正式发布仍需对应平台能力与用户当次明确确认。
- 文章文件只保留面向读者的正文；不得附加生成提示词、内部参数或提示词索引。

## 公众号排版与草稿

读 [references/wechat-layout-profiles.md](references/wechat-layout-profiles.md)、[references/layout-decision-template.md](references/layout-decision-template.md)、[references/delivery.md](references/delivery.md)，完整同步还要读 [references/wechat-draft-api.md](references/wechat-draft-api.md)。

- Markdown 是可编辑内容源，HTML 是交付物；不得用泛化手写 HTML 冒充排版技能。
- 从同一份 `wechat.md` 生成 `clean`、`editorial`、`visual` 三个候选 HTML，展示预览并选择。选择写入 `layout-selection.json`；只有被选版本复制为 `wechat-formatted.html` 和 `wechat-preview.html`。
- 用户没有指定时，根据内容类型推荐默认版本，但仍保留三个候选版本。运行：

```powershell
python "{baseDir}/scripts/select_wechat_layout.py" "<job-dir>" --profile clean --reason "<选择原因>"
python "{baseDir}/scripts/validate_wechat_layout.py" "<job-dir>" --formatter "<实际技能名>"
```

- 验证必须确认最终 HTML 与被选候选版本哈希一致、正文匹配、至少 4 个内联样式、至少 1 个带样式标题和 2 个带样式段落。
- `full` 模式优先用 `baoyu-post-to-wechat`；也可使用官方 API 脚本。保存后必须重新读取远端编辑器内容，验证标题、正文、原文出处、原文链接、改编声明、图片和排版。公开正文不强制显示原作者姓名。
- 官方 API：`publish_wechat_draft.py` 会自动读取远端草稿复验。浏览器/发布技能路径需导出编辑器 HTML 后运行 `verify_wechat_remote.py`。没有远端样式证据时不得生成成功收据。
- 微信素材接口只接受 JPG、PNG 或 GIF。预检会阻止 WebP 上传；先用 `baoyu-compress-image` 转换发布副本。更新草稿前脚本会读取旧草稿 ID，若明确返回 `40007 invalid media_id`，自动安全重建草稿。

## 交付约束

- 只生成所选平台的文件；两平台共用一次来源归档，但独立改写。
- 现有产物优先复用；覆盖用户编辑过的文件前先做时间戳备份。
- 多 URL 各建一个账本；单个 URL 失败不能阻塞其他 URL。
- 交付时说明平台、`fast/full` 模式、来源链接、主题、验收结果、Obsidian 位置；`full` 模式还要给草稿 ID 和远端排版验证结果。
- 不得删除水印、冒充原作者、隐去原文链接或改编声明，或把草稿保存说成正式发布。
