# 公众号草稿 API

仅在 `delivery.mode=full` 且用户明确要求保存草稿时使用。

环境变量：`WECHAT_APP_ID`、`WECHAT_APP_SECRET`（或短期 `WECHAT_ACCESS_TOKEN`）、`WECHAT_ACCOUNT_NAME`。密钥只从环境读取，不得写入任务目录、日志或收据。

先执行无网络预检：

```powershell
python "{baseDir}/scripts/publish_wechat_draft.py" "<job-dir>" --preflight --account "<账号>"
```

预检通过后保存：

```powershell
python "{baseDir}/scripts/publish_wechat_draft.py" "<job-dir>" --account "<账号>" --author "<署名>"
```

公众号 API 的正文图和封面必须是 JPG、PNG 或 GIF。WebP 需要先转换发布副本；`--preflight` 会在联网前列出 `unsupported_images`。脚本更新已有草稿前会先调用 `draft/get`，只有旧 ID 明确返回 `40007 invalid media_id` 时才自动新建，网络超时等不确定错误不会触发重复创建。

脚本上传正文图和封面，创建或更新草稿，然后调用 draft/get 读取远端内容。只有标题、正文、来源作者、来源 URL、改编声明和排版样式全部通过才生成成功收据。

浏览器或 `baoyu-post-to-wechat` 路径需把远端编辑器正文 HTML 保存为文件，再运行：

```powershell
python "{baseDir}/scripts/verify_wechat_remote.py" "<job-dir>" --remote-html "<文件>" --draft-id "<ID>" --account "<账号>" --title "<标题>" --mode publisher_skill
```

超时后先检查草稿箱，避免不确定状态下重复创建；只有确认不存在时才 `--force-create`。
