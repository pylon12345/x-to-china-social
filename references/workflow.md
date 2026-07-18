# V8 产物与门禁

每个 X 状态建立独立目录。`workflow-state.json` 是唯一账本，不要跨阶段补写状态。

| 阶段 | 必需产物 | 完成条件 |
|---|---|---|
| preflight | `capability-report.json` | `status=ready`、`workflow_version=8`、无缺失技能 |
| acquire | `source.json`, `source.md` | URL、作者、非空正文、线程顺序、媒体数已核验 |
| media | `media-manifest.json` | 每项决定为 `reuse/transform/reference_adapt/recreate/omit` |
| diagnose | `content-analysis.md` | 受众、主张、结构、风险、平台策略清楚 |
| voice | `voice-brief.md` | 视角、语气、受众、第一人称边界清楚 |
| rewrite | 平台初稿与终稿、`humanization-report.json` | 每个目标都通过；事实、引语、链接保真 |
| illustrate | `illustration-report.json` | 所有改编/重绘图有 prompt、输出与 QA |
| layout | 公众号四件套 | 格式器已记录，正文匹配且样式阈值通过 |
| sync | `obsidian-receipt.json`；full 公众号另需草稿收据 | 平台稿与每张配图提示词均归档；远端草稿内容和样式复验通过 |
| review | 无新增强制文件 | 全部已完成阶段重新验证通过 |

公众号四件套：`layout-decision.md`、`layout-validation.json`、`wechat-formatted.html`、`wechat-preview.html`。

## 报告最小格式

`humanization-report.json`：

```json
{
  "status": "passed",
  "skill": "humanizer-zh",
  "targets": [{"target": "wechat", "status": "passed"}],
  "fidelity_checks": {
    "facts_preserved": true,
    "quotes_preserved": true,
    "source_links_preserved": true
  },
  "notes": []
}
```

`illustration-report.json`：

```json
{
  "status": "passed",
  "items": [{
    "source_media_id": "media-1",
    "mode": "reference_adapt",
    "prompt_path": "media/adapted/media-1.prompt.md",
    "output_path": "media/adapted/media-1.webp"
  }],
  "qa": {
    "facts_preserved": true,
    "originality": true,
    "mobile_readability": true
  }
}
```

没有需要改编的图时仍生成通过报告，`items` 为空，并在 `notes` 说明原因。

## 恢复

- `status` 查看当前阶段。
- `complete <stage>` 只接受当前 `in_progress` 阶段，并重新检查门禁。
- `block <stage> --note "..."` 记录真正阻断；`resume` 恢复。
- 已完成产物缺失或报告后来变为不合格时，`validate` 必须失败。
- V2–V4 旧账本自动迁移为 V8 元数据，但保留旧阶段列表，避免破坏已完成任务。

## 性能

- 默认 `fast`，不登录公众号、不上传图片、不等待草稿回读。
- 来源和原图存在且哈希一致时复用。
- 两个平台共用 acquire/media/diagnose，但 rewrite/layout 独立。
- 只有明确要求草稿箱时才走 `full`；远端同步不得与本地创作阶段串行反复重试。
