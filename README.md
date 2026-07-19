<div align="center">
  <img src="assets/icon.svg" alt="X to China Social icon" width="112" />
  <h1>X to China Social</h1>
  <p><strong>把公开 X 内容可靠地改写为微信公众号或小红书成品。</strong></p>
  <p><strong>Turn public X content into production-ready Chinese social posts.</strong></p>
  <p><a href="#中文">中文</a> · <a href="#english">English</a></p>
</div>

---

## 中文

### 项目简介

`x-to-china-social` 是一个面向 Codex/AI Agent 的标准 Skill 与可恢复工作流。它接收公开的 X（Twitter）帖子、线程或长文链接，经过来源归档、中文改写、去 AI 味、配图改编、公众号排版、Obsidian 归档等步骤，生成可审查、可追溯的微信公众号或小红书内容。

它不是一个“一键搬运”脚本：原文、媒体、改写稿、配图提示词和发布收据都会分开保存，并由阶段门禁验证。只有用户明确要求时，工作流才会把内容保存到微信公众号草稿箱。

### 核心能力

- **智能平台路由**：默认生成微信公众号内容；明确指定小红书或双平台时才切换。
- **自然中文改写**：先分析内容，再通过 `humanizer-zh` 去除生硬翻译腔和常见 AI 表达。
- **来源可追溯**：保存规范化原文链接、作者元数据、正文、线程顺序和媒体清单。
- **低成本获取**：先查本地哈希缓存；未命中时只抓一次，原始 Markdown 由脚本直接规范化，长文按索引分块，避免模型重复吞全文。
- **原创配图改编**：参考原图的事实、构图关系和信息层级，重新生成适合中文读者的新图。
- **提示词独立归档**：每张生成图的完整提示词分别保存为 Obsidian 笔记，并反向链接到文章。
- **公众号排版验收**：验证正文、标题、段落、内联样式和图片，不把“生成了 HTML”当作排版完成。
- **草稿远端复验**：保存公众号草稿后重新读取，核对标题、正文、来源、图片和排版。
- **断点续跑**：`workflow-state.json` 记录唯一状态，已有且哈希一致的产物可以复用。
- **安全交付**：正文默认不设置援引作者段落，但保留原文 URL、内部来源元数据和改编声明。

### 工作流

| 阶段 | 作用 | 主要产物 |
|---|---|---|
| `preflight` | 检查必需技能与运行能力 | `capability-report.json` |
| `acquire` | 缓存优先，单次获取并核验原文 | `source.json`、`source.md`、`source-index.json` |
| `media` | 保存原图并决定复用、改编或省略 | `media-manifest.json` |
| `diagnose` | 分析受众、主张、结构和风险 | `content-analysis.md` |
| `voice` | 确定视角、语气和第一人称边界 | `voice-brief.md` |
| `rewrite` | 生成平台稿并去 AI 味 | `wechat.md` / `xiaohongshu.md`、`humanization-report.json` |
| `illustrate` | 生成原创改编图并进行 QA | `illustration-report.json`、图片与提示词 |
| `package_media` | 生成各平台独立贴图包 | `platform-media-package.json` |
| `layout` | 生成简洁、杂志、视觉卡片三个公众号版本并选择 | 三个候选 HTML、选择记录、最终预览与验证报告 |
| `sync` | 归档 Obsidian，按需保存公众号草稿 | Obsidian 与草稿收据 |
| `review` | 重新验证全部已完成阶段 | 最终交付检查 |

详细门禁和恢复规则见 [`references/workflow.md`](references/workflow.md)。

### 安装

需要 Python 3.9+、Git，以及支持本地 Skills 的 Codex/Agent 环境。

Windows PowerShell：

```powershell
git clone https://github.com/pylon12345/x-to-china-social.git "$env:USERPROFILE\.codex\skills\x-to-china-social"
```

macOS / Linux：

```bash
git clone https://github.com/pylon12345/x-to-china-social.git "$HOME/.codex/skills/x-to-china-social"
```

重启或刷新 Agent 的技能列表后，确认 `$x-to-china-social` 可用。该 Skill 会编排若干下游技能；运行前置检查后，会明确列出当前环境缺少的能力。典型依赖包括：

- `chinese-social-copywriter`、`humanizer-zh`
- `guizang-material-illustration`、`guizang-social-card-skill`（优先）
- `baoyu-article-illustrator`、`baoyu-cover-image`、`imagegen`
- `baoyu-markdown-to-html` 或 `dbs-wechat-html`
- `baoyu-compress-image`
- `baoyu-post-to-wechat`（仅完整公众号草稿流程需要）

### 快速开始

在 Codex 中直接提出需求：

```text
使用 $x-to-china-social，把这个 X 链接改写成微信公众号文章：<X URL>
```

保存到公众号草稿箱：

```text
使用 $x-to-china-social 处理 <X URL>，排版后发到微信公众号草稿。
```

也可以手动初始化账本：

```powershell
python scripts/init_workflow.py "<X URL>" `
  --platform auto `
  --delivery auto `
  --request-text "改写成公众号文章" `
  --root x-social

python scripts/preflight_capabilities.py "x-social/<handle>-<status-id>"
python scripts/manage_workflow.py "x-social/<handle>-<status-id>" complete preflight
```

`auto` 的默认行为：

- 未指定平台：微信公众号。
- 明确说“小红书”：只生成小红书。
- 明确说“两边都要”：同时生成两个平台。
- 未明确要求草稿：使用 `fast`，只生成本地成品、预览和 Obsidian 归档。
- 明确要求“发到草稿”：使用 `full`，增加公众号远端保存与复验。

### 配置

Obsidian 可自动发现唯一打开的 Vault，也可以显式配置：

```powershell
$env:OBSIDIAN_VAULT = "D:\Notes\My Vault"
```

公众号官方 API 模式从环境变量读取凭据：

```powershell
$env:WECHAT_APP_ID = "..."
$env:WECHAT_APP_SECRET = "..."
$env:WECHAT_ACCOUNT_NAME = "..."
```

也可以提供短期 `WECHAT_ACCESS_TOKEN`。凭据只从环境读取，不会写入任务目录、日志或收据。上传图片必须是 JPG、PNG 或 GIF；WebP 会在预检阶段被阻止。

### 典型产物

```text
x-social/<handle>-<status-id>/
├── workflow-state.json
├── capability-report.json
├── source.json
├── source.md
├── source-index.json
├── source-parts/                 # 仅长文
├── media-manifest.json
├── content-analysis.md
├── voice-brief.md
├── wechat.md / xiaohongshu.md
├── humanization-report.json
├── illustration-report.json
├── platform-media-package.json
├── wechat-layout-clean.html / editorial.html / visual.html
├── layout-selection.json
├── layout-validation.json
├── wechat-formatted.html
├── wechat-preview.html
├── obsidian-receipt.json
└── wechat-draft-receipt.json   # 仅 full 模式
```

### 验证与测试

```powershell
$env:PYTHONUTF8 = "1"
python -m unittest discover -s scripts -p "test_*.py"
```

### 使用边界

- 只处理用户有权访问的公开内容，不绕过删除、私密或付费访问控制。
- 不删除水印，不冒充原作者，不隐藏规范化原文链接和改编声明。
- “保存草稿”不等于“正式发布”；群发或发布始终需要用户当次明确确认。
- 生成图片需通过事实一致、原创性和手机可读性检查。

完整技能说明见 [`SKILL.md`](SKILL.md)，平台路由见 [`references/platform-routing.md`](references/platform-routing.md)，公众号草稿 API 见 [`references/wechat-draft-api.md`](references/wechat-draft-api.md)。

---

## English

### Overview

`x-to-china-social` is a standard Codex/AI Agent skill with a resumable workflow. It turns a public X (Twitter) post, thread, or article into reviewable Chinese content for WeChat Official Accounts or Xiaohongshu. The workflow covers source preservation, Chinese rewriting, AI-style cleanup, illustration adaptation, WeChat layout validation, and Obsidian archiving.

This is not a blind “copy and repost” script. Source material, media, rewritten copy, image prompts, and delivery receipts are stored separately and checked by stage gates. A WeChat draft is created only when the user explicitly requests it.

### Highlights

- **Conditional platform routing**: WeChat by default; Xiaohongshu or both only when requested.
- **Natural Chinese rewriting**: content diagnosis followed by mandatory `humanizer-zh` cleanup.
- **Traceable provenance**: canonical URL, author metadata, text, thread order, and media inventory.
- **Low-cost acquisition**: hash-based cache probes, one extractor pass, deterministic Markdown import, and indexed long-source chunks prevent repeated full-text ingestion.
- **Original illustration adaptation**: preserve factual and structural cues while creating a visibly new design.
- **Prompt archiving**: every generated image prompt becomes a separate Obsidian note linked from the article.
- **WeChat layout validation**: checks styled headings, paragraphs, inline CSS, body fidelity, and images.
- **Remote draft verification**: reads the saved draft back and verifies content, provenance, images, and layout.
- **Resumable execution**: one `workflow-state.json` ledger and hash-based artifact reuse.
- **Safe delivery**: removes visible author-callout sections by default while retaining provenance and an adaptation disclosure.

### Pipeline

| Stage | Purpose | Main artifacts |
|---|---|---|
| `preflight` | Verify required skills and capabilities | `capability-report.json` |
| `acquire` | Reuse a valid cache or acquire once and validate | `source.json`, `source.md`, `source-index.json` |
| `media` | Preserve media and choose reuse/adaptation policy | `media-manifest.json` |
| `diagnose` | Analyze audience, claims, structure, and risks | `content-analysis.md` |
| `voice` | Define point of view, tone, and first-person boundaries | `voice-brief.md` |
| `rewrite` | Produce platform copy and remove AI-like phrasing | platform Markdown, `humanization-report.json` |
| `illustrate` | Create adapted artwork and run QA | images, prompts, `illustration-report.json` |
| `layout` | Build and validate WeChat HTML | formatted HTML, preview, validation report |
| `sync` | Archive to Obsidian and optionally save a WeChat draft | archive and delivery receipts |
| `review` | Revalidate every completed stage | final delivery checks |

See [`references/workflow.md`](references/workflow.md) for gate and recovery details.

### Installation

Requirements: Python 3.9+, Git, and a Codex/Agent environment with local skill support.

Windows PowerShell:

```powershell
git clone https://github.com/pylon12345/x-to-china-social.git "$env:USERPROFILE\.codex\skills\x-to-china-social"
```

macOS / Linux:

```bash
git clone https://github.com/pylon12345/x-to-china-social.git "$HOME/.codex/skills/x-to-china-social"
```

Restart or refresh the Agent skill registry, then confirm that `$x-to-china-social` is available. This skill orchestrates downstream skills; its preflight report identifies any missing capability. Typical dependencies include:

- `chinese-social-copywriter`, `humanizer-zh`
- `guizang-material-illustration`, `guizang-social-card-skill` (preferred)
- `baoyu-article-illustrator`, `baoyu-cover-image`, `imagegen`
- `baoyu-markdown-to-html` or `dbs-wechat-html`
- `baoyu-compress-image`
- `baoyu-post-to-wechat` for the full WeChat draft flow

### Quick start

Ask Codex directly:

```text
Use $x-to-china-social to turn this X URL into a WeChat article: <X URL>
```

To request a verified WeChat draft:

```text
Use $x-to-china-social on <X URL>, format it, and save it to my WeChat drafts.
```

Manual ledger initialization:

```powershell
python scripts/init_workflow.py "<X URL>" `
  --platform auto `
  --delivery auto `
  --request-text "Create a WeChat article" `
  --root x-social

python scripts/preflight_capabilities.py "x-social/<handle>-<status-id>"
python scripts/manage_workflow.py "x-social/<handle>-<status-id>" complete preflight
```

Default routing rules:

- No platform specified: WeChat.
- Xiaohongshu explicitly requested: Xiaohongshu only.
- Both explicitly requested: generate both.
- No draft request: `fast` mode, ending with local outputs, preview, and Obsidian archive.
- Draft explicitly requested: `full` mode, adding remote save and read-back verification.

### Configuration

The Obsidian exporter can discover a single open vault, or use an explicit path:

```powershell
$env:OBSIDIAN_VAULT = "D:\Notes\My Vault"
```

The official WeChat API path reads credentials from environment variables:

```powershell
$env:WECHAT_APP_ID = "..."
$env:WECHAT_APP_SECRET = "..."
$env:WECHAT_ACCOUNT_NAME = "..."
```

A short-lived `WECHAT_ACCESS_TOKEN` is also supported. Secrets are never written to job artifacts, logs, or receipts. WeChat uploads accept JPG, PNG, or GIF; WebP is rejected during preflight.

### Validation

```powershell
$env:PYTHONUTF8 = "1"
python -m unittest discover -s scripts -p "test_*.py"
```

### Safety boundaries

- Process only public content the user is authorized to access; do not bypass deleted, private, or paid access controls.
- Do not remove watermarks, impersonate the source author, or hide the canonical source URL and adaptation disclosure.
- Saving a draft is not publishing. Broadcast or publication always requires explicit confirmation for that action.
- Generated illustrations must pass factual fidelity, originality, and mobile-readability checks.

For the complete agent contract, read [`SKILL.md`](SKILL.md). Routing details are in [`references/platform-routing.md`](references/platform-routing.md), and the WeChat API path is documented in [`references/wechat-draft-api.md`](references/wechat-draft-api.md).
