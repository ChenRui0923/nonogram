"""OCR 自测：把图片识别结果和一份"标准答案"JSON 逐项对比。

用法:
    python3 ocr_selftest.py <图片> <标准答案.json>

对比三部分：行提示、列提示、当前棋盘，并打印每处差异与总准确率。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parser import load
from ocr_nonogram import ocr_nonogram, validate_and_fix


def _fmt_diff(name, ocr_list, ref_list):
    bad = []
    for i in range(max(len(ocr_list), len(ref_list))):
        a = ocr_list[i] if i < len(ocr_list) else None
        b = ref_list[i] if i < len(ref_list) else None
        if a != b:
            bad.append((i + 1, a, b))
    print(f"{name}: {len(bad)}/{max(len(ocr_list), len(ref_list))} 行不符")
    for i, a, b in bad:
        print(f"  {name[0]}{i:>2}: OCR={a}  正确={b}")
    return len(bad), max(len(ocr_list), len(ref_list))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1

    img_path, ref_path = sys.argv[1], sys.argv[2]
    ref = load(ref_path)

    print(f"图片: {img_path}")
    print(f"标准: {ref_path}")
    print("识别中...")
    ocr = validate_and_fix(ocr_nonogram(img_path))

    nrows = len(ref["row_clues"])
    ncols = len(ref["col_clues"])
    print(f"棋盘: OCR {len(ocr['row_clues'])}x{len(ocr['col_clues'])} / "
          f"标准 {nrows}x{ncols}")
    print()

    rw, rt = _fmt_diff("行提示", ocr["row_clues"], ref["row_clues"])
    cw, ct = _fmt_diff("列提示", ocr["col_clues"], ref["col_clues"])
    print()

    cur_o = ocr.get("current") or []
    cur_r = ref.get("current") or []
    cell_bad = cell_total = 0
    marks_bad = 0
    for r in range(min(len(cur_o), len(cur_r))):
        marks = ""
        for c in range(min(len(cur_o[r]), len(cur_r[r]))):
            same = cur_o[r][c] == cur_r[r][c]
            cell_total += 1
            cell_bad += 0 if same else 1
            if not same and (cur_o[r][c] != "." or cur_r[r][c] != "."):
                marks_bad += 1
            marks += " " if same else "^"
        if marks.strip():
            print(f"  R{r + 1:>2} OCR={cur_o[r]}")
            print(f"     正确={cur_r[r]}")
            print(f"          {marks}")

    print(f"当前棋盘: {cell_bad}/{cell_total} 格不符"
          f"（其中有标记的格子 {marks_bad} 处不同）")
    print()

    # 提示数字级别准确率
    o_digits = sum(len(str(x)) for line in ocr["row_clues"] + ocr["col_clues"] for x in line)
    r_digits = sum(len(str(x)) for line in ref["row_clues"] + ref["col_clues"] for x in line)
    total_lines = rt + ct
    bad_lines = rw + cw
    print("=" * 52)
    print(f"提示整行准确率: {total_lines - bad_lines}/{total_lines} "
          f"= {100.0 * (total_lines - bad_lines) / max(1, total_lines):.1f}%")
    print(f"棋盘格子准确率: {cell_total - cell_bad}/{cell_total} "
          f"= {100.0 * (cell_total - cell_bad) / max(1, cell_total):.1f}%")
    return 0 if (bad_lines == 0 and cell_bad == 0) else 2


if __name__ == "__main__":
    sys.exit(main())
