# nonogram助手图标

- [source.png](source.png)：已确认的青绿数织图标源稿。
- [nonogram.png](nonogram.png)：1024×1024 展示与转换结果。
- `nonogram.ico`：Windows 多尺寸（16、24、32、48、64、128、256）。
- `nonogram.icns`：macOS 多尺寸，最大 1024×1024。

白色圆角外部为透明通道，导出时应用抗锯齿轮廓，不包含灰色方形背景。

从仓库根目录执行 `python packaging/build_icons.py` 可重新生成，需要 Pillow。Windows 的 `packaging/windows.spec` 和 macOS 的 `packaging/macos.spec` 已引用对应文件；原有安装包不会自动更新图标，需要重新打包。
