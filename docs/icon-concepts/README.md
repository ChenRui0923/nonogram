# 应用图标备选

C 款修正版已选定为应用图标，并已导出 Windows ICO 和 macOS ICNS、接入打包配置。其余图片保留作设计过程参考。

## 数织主题（最新一组）

加入了顶部和左侧数字线索。上排为 A、B，下排为 C、D。

- **A**：奶油白底、黑色网格、橙色叉号。
- **B**：深蓝底、青色格子、白色数字。
- **C**：白底、青绿网格、橙色提示框。
- **D**：暖黄底、纸质卡片、橙色数字。

![数织主题图标备选 A–D](nonogram-options.png)

[打开原图](nonogram-options.png)

## 第一组探索

上排为 A、B、C，下排为 D、E、F。

![第一组图标备选 A–F](initial-options.png)

[打开原图](initial-options.png)

## C 款修正版

保留青绿配色、橙色提示框与原有格子图案，修正数字线索：

- 顶部（左→右）：**2、3、5、3、2**。
- 左侧（上→下）：**1、5、5、3、1**。
- 格子图案：`00100 / 11111 / 11111 / 01110 / 00100`（1 为填色）。

![C 款：数字与格子一致的修正版](nonogram-c-corrected.png)

[打开修正版原图](nonogram-c-corrected.png)。旧对比图保留用于回顾，数字错误以本修正版为准。此修正版已用于应用图标。图标文件见 [`assets/icons`](../../assets/icons/)，可执行 `python packaging/build_icons.py` 重新生成。
