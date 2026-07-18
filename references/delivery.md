# 交付

## fast（默认）

1. 将所选平台最终 Markdown 归档到 Obsidian。
2. 读取 `illustration-report.json`，把每个 `prompt_path` 分别保存为 Obsidian 独立笔记，并在平台归档笔记末尾加入提示词链接。
3. 生成 `obsidian-receipt.json`，`status=saved`；`items` 覆盖全部目标平台，`prompt_notes` 覆盖全部生成图提示词。
4. 公众号提供本地 `wechat-preview.html`，不登录公众号、不上传图片、不写草稿收据。

## full（仅明确要求公众号草稿）

先完成 fast 的全部内容，再执行：

1. 确认 `layout-validation.json.valid=true`。
2. 上传所有 `intended_images`，不得保留本地路径或 data URL。
3. 用 `baoyu-post-to-wechat`、官方 API 或已登录浏览器保存草稿。
4. 重新读取草稿内容，验证标题、非空正文、原文出处链接、改编声明、图片和内联排版。可见正文不强制显示原作者姓名。
5. 只有全部通过才能写 `status=draft_saved`、`verified=true` 的 `wechat-draft-receipt.json`。

远端排版最小证据：4 个内联样式、1 个带样式标题、2 个带样式段落。只看到草稿列表或只核对标题不算验证成功。

正式发布/群发不属于自动交付；必须展示账号、标题、图片数和草稿 ID 后，获得用户当次明确确认。
