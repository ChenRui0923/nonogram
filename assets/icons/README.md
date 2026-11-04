# Nonogram 应用图标

使用已确认的 [C 款修正版](../../docs/icon-concepts/nonogram-c-corrected.png)，保留白色圆角底、青绿网格和橙色提示框。外部为透明通道，无灰色方形背景；导出时应用抗锯齿圆角轮廓。应用显示名为 `nonogram助手`。

- `nonogram.png`：1024×1024 原生图标转换源，可用于文档展示。
- `nonogram.ico`：Windows 多尺寸图标（16、24、32、48、64、128、256）。
- `nonogram.icns`：macOS 多尺寸图标，最大 1024×1024。

Windows 的 `nonogram.spec` 与 macOS 的 `nonogram_macos.spec` 已引用相应文件，重新打包后生效。原有安装包不会自动更换图标。

重新生成：`python packaging/build_icons.py`，需要 Pillow。

透明源稿为 `docs/icon-concepts/nonogram-c-transparent.png`，旧的灰底对比稿仅用于设计回顾。
