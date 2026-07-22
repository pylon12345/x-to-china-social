# 公众号排版候选版本

同一份 `wechat.md` 必须生成三个候选 HTML，内容、图片顺序和来源声明保持一致，只改变视觉层级。让用户查看预览后选择；用户未指定时，根据文章类型推荐一个，但不得跳过候选生成与选择记录。

| 版本 | 文件 | 适用场景 | 视觉约束 |
|---|---|---|---|
| `clean` | `wechat-layout-clean.html` | 长文、教程、信息密集内容 | 白底、克制强调色、较大行距，装饰最少 |
| `editorial` | `wechat-layout-editorial.html` | 观点、人物、趋势解读 | 杂志式标题、引语和分隔线，层级鲜明 |
| `visual` | `wechat-layout-visual.html` | 产品、案例、图片驱动内容 | 卡片分区、较强色块和图片节奏，控制移动端密度 |

三个版本分别调用实际安装的公众号格式器生成。不要用换色冒充不同版本。全部生成后运行：

```powershell
python "{baseDir}/scripts/select_wechat_layout.py" "<job-dir>" --profile clean --reason "长文优先保证连续阅读"
python "{baseDir}/scripts/validate_wechat_layout.py" "<job-dir>" --formatter "<实际技能名>"
```

只有被选版本会复制为 `wechat-formatted.html` 和 `wechat-preview.html`，并用于草稿同步。切换版本时重新运行选择与验证脚本，不需要重新改写正文或生成图片。
