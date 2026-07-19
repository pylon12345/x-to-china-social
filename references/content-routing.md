# 内容诊断与去 AI 味

## 诊断

用 `chinese-social-copywriter` 分析，不让诊断工具代写事实。`content-analysis.md` 至少包含：

- 原文核心主张与证据
- 中国读者需要的上下文
- 目标平台、受众和阅读场景
- 可删冗余、需解释术语、潜在争议
- 推荐结构、标题角度、开头抓手
- 不能越过的事实与第一人称边界

先读 `source-index.json`。短来源只展开一次 `source.md`；长来源按索引逐段处理并把稳定结论写入 `content-analysis.md`。rewrite 阶段复用该分析，只按需回看对应 source part；禁止再次同时载入 `source-raw.md`、`source.json` 和 `source.md`。

## 两遍写作

第一遍写 `*-draft.md`：忠实、完整、结构合理。第二遍调用 `humanizer-zh` 写最终稿：

- 句长有变化，允许自然停顿和编辑判断。
- 删除空泛过渡、总结腔、模板化排比、过密小标题。
- 把术语解释成人话，但不牺牲精确性。
- 不虚构“我亲测/我经历/我做过”。
- 不改变数字、代码、命令、链接、引语和不确定性。

终稿必须逐项对照 `source.md` 和初稿，填写 `humanization-report.json`。三个 fidelity checks 任何一个不通过，就回到 rewrite 修复。
