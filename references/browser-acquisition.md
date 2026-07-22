# Codex 内置浏览器获取 X 正文

本流程用于 `acquire` 阶段。正文 DOM 优先，截图只做页面状态和视觉内容辅助，不把长文默认变成截图 OCR。

## 为什么 DOM 优先

- 一次获得标题、段落、列表、时间、作者和媒体 URL。
- 保留结构和链接，避免滚动截图遗漏、OCR 错字与图片拼接。
- 只返回摘要统计并直接写入 JSON，不把整篇浏览器输出塞进模型上下文。

截图用于确认页面是否完整、识别登录墙/弹窗、检查封面或图表。只有 DOM 确实没有正文时，才对可见截图做有限识别；截图不能证明隐藏文本或媒体 URL。

## 步骤

1. 先运行缓存探测。命中即停止，不打开浏览器。
2. 使用 `browser:control-in-app-browser`，明确选择 Codex 内置浏览器 `iab`，完整读取其运行时文档。
3. 调用 `iab.user.openTabs()`。若目标 URL 已打开，按可见 URL 精确匹配并 `claimTab`；否则创建新标签页并导航到状态永久链接。
4. 获取一次 `domSnapshot()`，确认页面存在主文章、标题或 `tweetText`。不要读取整页 `body.innerText`。
5. 导入 `{baseDir}/scripts/browser_source.mjs`，让脚本在文章 DOM 上做有限投影并直接写入 `<job-dir>/browser-source.json`：

```javascript
var browserSource = await import("{baseDir}/scripts/browser_source.mjs");
var sourceSummary = await browserSource.extractXSource(tab, {
  sourceUrl: "<X URL>",
  outputPath: "<absolute job-dir>/browser-source.json",
  includeThread: true,
});
nodeRepl.write(sourceSummary);
```

6. 将结构化结果交给确定性导入器：

```powershell
python "{baseDir}/scripts/build_source.py" "<job-dir>/browser-source.json" --source-url "<X URL>" --output-dir "<job-dir>"
```

7. 导入成功后立即停止浏览器读取。保留用户原本打开的标签页；任务新建的中间标签页可在浏览器阶段结束时清理。

## 截图辅助

当快照显示空壳、弹窗、登录墙或图表需要目视检查时，保存当前视口：

```javascript
await browserSource.saveViewportScreenshot(tab, "<absolute job-dir>/source-visual.png");
```

随后用本地图片查看能力检查页面状态。不要先截图整篇再 OCR。若 DOM 和截图都无法确认完整正文，请用户在内置浏览器登录或提供正文；不得改用搜索摘要补句子。

## 提取边界

- 只处理 `main article` 中与目标状态永久链接匹配的主文章。
- 长文章读取 `h1` 后的标题、段落、标题层级和列表；普通帖子读取 `tweetText`。
- 线程只继续收集紧邻且作者 handle 相同的文章，遇到其他作者即停止。
- 只保存正文媒体，过滤头像、推荐卡片、导航和互动指标。
- 不采集点赞、转发、浏览量；不展开推荐回复。
- URL、状态 ID、作者 handle、非空正文/媒体必须通过 `build_source.py` 门禁。
