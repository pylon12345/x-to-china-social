# 媒体归档与改编

先用 `save_media.py` 保存原文件、URL、哈希、尺寸和 MIME。原文件放 `media/original/`，永不覆盖；派生图放 `media/adapted/`。

逐张目视检查并记录：内容、事实作用、水印、个人信息、权利依据、是否适合移动端。最终决定只能是：

- `reuse`：已获授权或许可明确。
- `transform`：许可允许变换；不得去水印或淡化署名。
- `reference_adapt`：原图仅作事实/关系/构图参考，生成视觉上明显原创的新图。
- `recreate`：完全从文章事实重建解释图。
- `omit`：权利不清、无必要、含敏感信息或无法安全处理。

建议字段：`rights_review`、`private_information`、`decision_reason`、`reference_use`、`adaptation_constraints`。

## reference_adapt 流程

1. 说明原图承担什么信息功能，而不是描述像素细节。
2. 记录允许借鉴的关系：对象、顺序、比例、数据、信息层级。
3. 记录必须改变的表达：版式、配色、图标、字体、装饰、构图细节。
4. 用文章事实、平台尺寸、品牌语气写 prompt 文件。
5. 规划：`baoyu-article-illustrator`；封面另用 `baoyu-cover-image`。
6. 生成：`imagegen`；不得要求复刻在世艺术家风格或移除水印。
7. 目视 QA：事实一致、原创性、手机可读性。
8. 用 `baoyu-compress-image` 优化发布版本，保留未压缩派生文件。

若原图是数据图，数字和单位必须逐项核对；若是截图，只提炼文章所需事实，不仿制界面或账号身份。
