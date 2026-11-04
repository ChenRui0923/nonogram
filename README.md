# nonogram助手

<img src="assets/icons/nonogram.png" alt="Nonogram 应用图标" width="128">

本地运行的数织（Nonogram）截图识别与求解工具：识别行列数字和当前棋盘、生成完整解答、检查填写冲突，并给出下一步提示。图片由本机处理，不需要上传到在线 OCR 服务。

支持 Windows / macOS 桌面窗口，也可以直接运行 Python Web 版或命令行版。

## 下载与安装

打开 [GitHub Releases](https://github.com/ChenRui0923/nonogram/releases)，选择一个**已发布且带下载附件**的版本，在 Assets 中下载对应文件。构建进度见 [Actions](https://github.com/ChenRui0923/nonogram/actions)；标签存在或 Actions 启动不代表安装包已经生成。所有平台构建通过后才发布 Release。

| 系统 | 下载文件 | 使用方式 |
| --- | --- | --- |
| Windows 10/11 x64 | `Nonogram-windows-x64.exe` | 双击运行 |
| macOS Apple Silicon（M 系列） | `Nonogram-macos-arm64.dmg` | 打开 DMG，将 App 拖入 Applications |
| macOS Intel | `Nonogram-macos-x64.dmg` | 打开 DMG，将 App 拖入 Applications |

- 桌面包无需安装 Python、字体或 Tesseract。
- Windows 界面使用 Microsoft Edge WebView2；如提示缺少运行库，安装 [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)。
- macOS 使用系统 WebKit。当前版本尚无开发者证书签名和 Apple 公证；确认下载来源后，可在系统“隐私与安全性”中按提示允许打开。
- Release 中的 `SHA256SUMS.txt` 可用于核对下载完整性，`dependencies-*.txt` 记录各平台实际打包依赖。

## 使用教程

以下图片来自本项目 Web 界面的真实操作，示例为仓库中的 [`debug.png`](examples/images/debug.png)（50×50）。桌面版使用同一界面；截图不是 Windows/macOS 原生窗口的实机验收图。

### 1. 选择一张完整截图

打开应用，点击 **选择图片**。桌面版也可以复制截图后点击 **从剪贴板粘贴**。选中后点击 **开始识别**。

截图应包含完整棋盘、顶部列提示、左侧行提示；尽量保持网格水平、文字清晰，避免裁掉边缘、旋转或透视变形。

![选择图片后，点击开始识别](docs/screenshots/01-select-image.png)

浏览器版的剪贴板功能依赖浏览器权限；粘贴失败时直接选择图片即可。

### 2. 查看识别棋盘与冲突

识别完成后，左侧显示当前棋盘，右侧显示尺寸、已标记格数和下一步提示。

- 深色格：已填黑格；红色 `×`：已标记空格；白格：未知。
- 橙框：识别出的已有填写与求得解答不一致；先核对原图与提示数字，再修改游戏中的填写。
- 蓝框：右侧当前提示对应的位置。点击 **刷新提示** 切换已有提示。
- 红色警告表示当前填写与行列约束矛盾，并不一定代表题目本身无解。
- 题目可解且未发现填写冲突时，显示绿色“恭喜你，当前没有错误”提示，以及已完成百分比（黑格和已标记空格均计入进度）。
- 右侧行提示、列提示列表用于人工核对，内容可在各栏内滚动；它们与棋盘边缘的线索重复。

![真实识别结果：50×50 棋盘、填写冲突和下一步提示](docs/screenshots/02-recognized-board.png)

示例图识别为 50×50，已有标记为 362/2500；完整解答与这些标记有 8 处冲突。没有标准答案时，不能仅凭“求出了一个解”就认定所有 OCR 数字都正确。

### 3. 缩放与显示完整解答

棋盘默认 **适应宽度**，无需横向拖动即可看到全部列。线索数字使用加粗字体；小窗口下数字会相应缩小；需要看清细节时，切换到 **100% / 150% / 200%**，再在棋盘区域滚动。

勾选棋盘下方的 **显示完整解答** 查看结果，取消勾选返回识别出的当前棋盘。页面较长时向下滚动即可找到开关。

![勾选显示完整解答后的实际界面](docs/screenshots/03-solution.png)

### 4. 导出与修正识别结果

点击顶部 **下载 JSON**，保存当前识别出的行列提示和棋盘。此按钮导出的是 OCR 数据，不是完整解答，也不会自动回填到游戏。

如果某个数字识别错了，可编辑导出的 JSON，再用命令行求解：

```bash
python -m nonogram /path/to/puzzle.json
```

当前网页没有 JSON 导入或直接修改提示数字的功能。

## 识别范围与常见问题

**能保证各种比例的图都成功吗？**不能。求解器支持长方形棋盘，界面会随行列数和窗口宽度调整；OCR 则依赖截图字体、网格、清晰度和裁剪完整性。已验证仓库中的 30×25 和 50×50 示例；仓库中 1080×2400 的 JPG 未能检测到网格，不能保证任意长截图都可识别。

**提示“题目无解”怎么办？**先核对顶部和左侧的提示数字，尤其是粘连的两位数；必要时重新裁剪清晰截图，或导出 JSON 人工修正。行列黑格总数相同只是初步检查，不证明识别完全正确。

**有解但出现冲突格怎么办？**可能是当前填写有误，也可能是 OCR 识别有误；对照截图核对。命令行在仅凭行列推理确定唯一解时，会把差异标为确定错误；存在多解时不能把所有差异都归为玩家错误。

**为什么有时慢？**程序会依次识别、求解并生成提示。示例 `debug.png` 在开发云环境中首次 OCR 加求解约 2.5 秒，其中求解和提示约 0.6 秒；不是所有机器或题目的耗时保证。需要大量回溯的题目仍可能更慢，Windows 单文件程序首次解包启动也需要额外时间。

**端口被占用？**关闭之前启动的程序，或从终端指定新端口：Windows 为 `nonogram助手.exe --port 9000`；源码 Web 版为 `python -m nonogram.web_app --port 9000`。

## 连续做题：自动匹配与缓存

正常上传每一张截图即可，**无需勾选“继续上一题”**。程序会检测变化后的填写，并自动决定线索和解答能否复用。

- **相同文件**：直接读取整图结果缓存，改名也可命中。
- **不同截图、疑似同题**：在顶部/左侧线索区匹配 ORB 特征，通过 RANSAC 求单应矩阵，将缩放、平移后的截图对齐到历史参考。已变化的棋盘内容不参与题目身份判断。
- **整体阈值**：对齐后比较线索笔画的双向覆盖率，默认至少 **99.5%**，允许 1 像素抗锯齿偏差；白色背景不计入分数。低于阈值或对齐不可靠时，完整重新 OCR。
- **题目级复用**：线索区整体相似度达标、特征配准可靠且网格结构一致，就按同一道题处理，复用全部行列线索，不再逐条 OCR；否则完整重新识别。此策略针对同题连续填写、换题线索整体明显不同的使用场景。
- **当前填写始终重读**：即使复用线索，也会重新识别黑格和叉号、生成最新错误和提示。只有已证明唯一的解答才会复用；多解题仍结合新填写求解。

状态栏会显示自动匹配的线索相似度、复用条数与服务端处理时间。`debug.png` → 缩放后的 `debug2.png` 已验证会自动匹配；自动复用 100/100 条线索，约 0.28 秒完成；完整结果与从头 OCR/求解对照一致。

常规截图优先用原始像素识别未复用的数字和当前棋盘，避免对齐插值降低 OCR 精度；原网格检测失败时才尝试基于已验证参考网格进行透视矫正。这不保证任意拍照角度、裁掉线索、遮挡或模糊图片均能成功；遇到“无解”仍应核对提示数字。

缓存保存在本机用户缓存目录，重启后仍可复用：

- macOS：`~/Library/Caches/nonogram-helper/`
- Windows：`%LOCALAPPDATA%/nonogram-helper/`
- Linux：`$XDG_CACHE_HOME/nonogram-helper/`，未设置时为 `~/.cache/nonogram-helper/`

最多保留 32 份整图结果、32 份线索区结果、32 份解答、512 条线索，以及 **4 份自动对齐参考**。参考仅保留线索区图像和几何信息，玩家填写区域被清白；不保留完整上传图片。单记录最大 2 MiB，失败请求不缓存，缓存不可写时回退到正常识别。算法和格式升级时更新版本，防止旧缓存混用。

关闭应用后删除目录中的 `*.sqlite3` 可清空缓存。更多测量方法见 [性能验证记录](docs/development/performance.md)。

## 从源码运行

推荐 Python 3.12，使用独立虚拟环境：

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell 则执行：.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements/runtime.txt
python -m nonogram.web_app
```

浏览器打开 `http://127.0.0.1:8765`。Web 服务使用 Python 标准库，无需 Flask/FastAPI。Tesseract 是可选的外部 OCR 引擎，内置字体模板识别无需安装它。

### 命令行

```bash
# 截图识别并求解，显式指定输出路径
python -m nonogram examples/images/debug.png --save-json /tmp/nonogram-result.json
# Windows 可将输出路径改为 result.json

# 只识别，不求解
python -m nonogram --ocr-only examples/images/debug.png result.json

# 从 JSON 求解
python -m nonogram result.json

# OCR 调试输出到当前目录的 debug_ocr/
python -m nonogram examples/images/debug.png --save-json result.json --debug
```

未指定输出路径时，图片识别保存到当前工作目录的 `outputs/puzzle.json`；`--debug` 写入 `outputs/debug_ocr/`。这些目录已加入 Git 忽略规则，不会覆盖示例素材。

JSON 示例：

```json
{
  "row_clues": [[2], [2], [2], [2]],
  "col_clues": [[2], [2], [2], [2]],
  "current": ["OO..", "....", "..X.", "...."]
}
```

`row_clues` 从上到下，`col_clues` 从左到右；`current` 可省略。格子使用 `O`（黑格）、`X`（空格）、`.`（未知）。

## 开发与目录导航

- [开发、测试、打包与发布](docs/development/README.md)
- [示例图片和题目说明](examples/README.md)
- [性能验证记录](docs/development/performance.md)
- [图像鲁棒性测试报告](docs/development/robustness.md)
- [应用图标与源稿](assets/icons/README.md)

```text
nonogram/           程序源码（OCR、求解、缓存、桌面与 Web）
  web/index.html    Web 界面
assets/             应用图标、图标源稿、字体及许可
examples/           示例图片、JSON 题目
packaging/          PyInstaller 配置、图标转换、启动诊断
scripts/build/      Windows / macOS 本地打包脚本
requirements/       运行与打包依赖
tests/             自动测试、可选鲁棒性测量脚本
tools/              OCR 对照检查工具
docs/               使用截图、开发与验证文档
```

从仓库根目录执行 `python -m nonogram` 启动命令行，`python -m nonogram.web_app` 启动 Web，`python -m nonogram.desktop` 启动桌面（需安装打包/桌面依赖）。桌面打包入口位于 `packaging/desktop_entry.py`。`outputs/`、`build/`、`dist/` 和 Python 缓存属于本地生成物，不提交到仓库。
