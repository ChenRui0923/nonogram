# 开发、测试与打包

所有命令从仓库根目录运行。程序源码在 `nonogram/`；命令行、Web 和桌面入口分别是 `python -m nonogram`、`python -m nonogram.web_app` 和 `python -m nonogram.desktop`。

## 安装与运行

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell：.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements/runtime.txt
python -m nonogram.web_app
```

CLI 示例：

```bash
python -m nonogram examples/images/debug.png --save-json outputs/result.json
python -m nonogram examples/puzzles/progress-30x25.json
python tools/ocr_selftest.py screenshot.png reference.json
```

OCR 对照工具需要真正匹配、人工核对过的参考 JSON；退出码 2 表示识别存在差异。示例 JSON 不都与示例图片处于同一填写进度，见 [素材说明](../../examples/README.md)。

默认识别输出到 `outputs/puzzle.json`，调试输出到 `outputs/debug_ocr/`；不覆盖示例文件。

## 测试

```bash
python -B -m unittest discover -s tests -v
# 可选：较慢的真实图片变换矩阵，结果写到仓库外
python -B tests/robustness_benchmark.py /tmp/nonogram-robustness
```

测试覆盖求解器穷举对照、真实截图 OCR、同题复用、换题回退、字体、图标透明通道和无窗口桌面启动。

- [性能记录](performance.md)
- [鲁棒性报告](robustness.md)
- [原始鲁棒性结果](robustness-results.json)

报告中的历史图片名 `image.png` / `image copy.png` 现已归档为 `examples/images/progress-30x25.png` / `progress-30x25-later.png`，图片内容未变。

## 本地打包

PyInstaller 不能在 Linux 上直接生成 Windows/macOS 原生程序，需要在目标系统运行。

```powershell
# Windows PowerShell，脚本会定位到仓库根目录
.\scripts\build\build_windows.ps1
# 或双击 scripts/build/build_windows.bat
```

```bash
# macOS
bash scripts/build/build_macos.sh
bash scripts/build/build_dmg.sh
```

运行依赖在 `requirements/runtime.txt`，打包依赖在 `requirements/build.txt`。配置分别是 `packaging/windows.spec`、`packaging/macos.spec`；网页和字体使用显式资源路径，源代码运行和 PyInstaller 解包后均可读取。

输出：Windows 为 `dist/nonogram助手.exe`；macOS 为 `dist/nonogram助手.app` 与 `dist/Nonogram-macOS.dmg`。

```bash
# Windows
.\dist\nonogram助手.exe --smoke-test --port 0
# macOS
./dist/nonogram助手.app/Contents/MacOS/nonogram助手 --smoke-test --port 0
```

无窗口检查日志默认位于系统临时目录 `nonogram-smoke.log`，可通过 `NONOGRAM_STARTUP_LOG` 指定路径。检查验证 HTTP 页面、字体和基本求解，不代替目标系统的窗口、剪贴板及安装实机验收。

## 自动构建和 Release

[Desktop builds and releases](https://github.com/ChenRui0923/nonogram/actions) 会先测试，再分别打包 Windows x64、macOS Intel 和 Apple Silicon。推送新的 `v*` 标签会在全部构建成功后发布安装包、依赖版本清单与 SHA-256 校验值。

发布前提交并推送代码，再创建一个尚未使用的新版本标签；不要覆盖旧版本标签。手动选择 Actions → Run workflow 则只生成 Actions artifacts，不发布 Release。GitHub Actions 需要启用，发布任务需要 `contents: write` 权限。

Windows 启动超时请查看任务日志及 `windows-startup-diagnostics` 附件；Python 启动后卡住超过 90 秒会记录线程堆栈。没有日志则表示尚未进入 Python runtime hook，需检查解包或系统拦截。

## 图标

源稿为 `assets/icons/source.png`，导出结果为 PNG、ICO、ICNS。执行 `python packaging/build_icons.py` 可重新生成，详见 [图标说明](../../assets/icons/README.md)。不再保留未采用的设计草稿。
