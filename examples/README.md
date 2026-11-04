# 示例素材

这些文件用于演示、回归与鲁棒性验证，不是运行应用所必需的资源，也不会被打包进桌面应用。

## 图片

| 文件 | 用途 |
| --- | --- |
| [images/debug.png](images/debug.png) | 50×50，较早填写进度，当前识别有 8 个冲突格 |
| [images/debug2.png](images/debug2.png) | 同一道 50×50 题的新进度与不同缩放，当前识别剩 1 个冲突格 |
| [images/progress-30x25.png](images/progress-30x25.png) | 原 `image.png`，30×25 示例 |
| [images/progress-30x25-later.png](images/progress-30x25-later.png) | 原 `image copy.png`，同题后续进度 |
| [images/unsupported-mobile.jpg](images/unsupported-mobile.jpg) | 原微信长截图，保留作网格检测失败/异题负样本 |

## JSON

- [puzzles/progress-30x25.json](puzzles/progress-30x25.json)：原 `puzzle.json`，保留原始提示和已有填写，填写进度与上述两张图片不完全一致。
- [puzzles/puzzle-30x30.json](puzzles/puzzle-30x30.json)：原 `puzzle_gpt.json`，独立的 30×30 题目。

不要把不同填写进度的 JSON 与图片当成完全匹配的 OCR 标准答案。需要识别输出时保存到 `outputs/`，不要覆盖本目录素材。
