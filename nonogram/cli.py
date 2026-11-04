import sys
import os
import json
from nonogram.parser import load
from nonogram.solver import Solver, UNKNOWN
from nonogram.renderer import print_board, print_compact
from nonogram.hint import (next_hint, find_errors, validate_current_board, progress,
                  conflicting_line, find_conflicts)

HAS_OCR = False
try:
    from nonogram.ocr_nonogram import ocr_nonogram, validate_and_fix
    HAS_OCR = True
except Exception as e:
    print(f"[警告] OCR 模块不可用: {e}")

# OCR 输出写入当前工作目录的 outputs/，不会覆盖示例素材。
DEFAULT_OCR_JSON = os.path.abspath(os.path.join("outputs", "puzzle.json"))


def banner(title):
    w = 60
    print("=" * w)
    print(f" {title} ".center(w, "="))
    print("=" * w)


def print_clues_summary(row_clues, col_clues):
    print(f"棋盘大小: {len(row_clues)} 行 × {len(col_clues)} 列")
    total_row_black = sum(sum(r) for r in row_clues)
    total_col_black = sum(sum(c) for c in col_clues)
    print(f"行提示总黑格: {total_row_black}, 列提示总黑格: {total_col_black}", end="")
    if total_row_black != total_col_black:
        print(" ⚠️  不匹配!")
    else:
        print(" ✓")
    print()


def report_unsolvable_clues():
    print("❌ 题目无解：行提示与列提示互相矛盾（不是当前棋盘的问题）")
    print("请检查:")
    print("  1. 提示数字是否正确(OCR识别是否准确)")
    print("  2. 行列黑格总数是否一致")
    print()
    print("💡 OCR修正建议:")
    print(f"   1) 编辑已保存的JSON文件 (--save-json 输出的那个)")
    print(f"   2) 修改其中的 row_clues / col_clues 数字")
    print(f"   3) 再运行: python3 -m nonogram <修正后的json>")
    print(f"   4) 或运行: python3 -m nonogram --ocr-only <图片> out.json 只OCR不求解，先手动修正")


def report_conflict(current, solution, unique, row_clues, col_clues, errors):
    """current 与解答冲突时的诊断输出。"""
    filled, total = progress(current)
    # 冲突格很少 → 基本可以确定是当前棋盘填错了；
    # 冲突格一大片 → 更像提示数字本身识别/录入有误。
    clues_suspect = len(errors) > max(5, int(0.1 * filled))

    if clues_suspect:
        banner("当前棋盘与解答冲突")
        print(f"当前棋盘有 {len(errors)}/{filled} 处与解答不符，数量偏多。")
        print("这么大规模的冲突，通常不是「填错一两格」，而是提示数字本身有问题")
        print("(OCR 识别/录入错误)，请先核对 row_clues / col_clues。")
        print()
    else:
        banner("当前棋盘有误 (题目本身有解)")
        if unique:
            print("提示经纯行列推理即可推满全盘 → 解答唯一，下面的格子一定是填错的：")
        else:
            print("提示的解答不唯一，下面是会导致当前棋盘无解的可疑格子：")
        print()
        if not errors:
            print("  (未能定位到具体格子，请对照解答逐个核对当前棋盘)")

    show = errors[:20]
    for i, e in enumerate(show, 1):
        mark = "确定错误" if unique and not clues_suspect else "可疑"
        print(f"  {i:>2}. R{e['row']}C{e['col']}: 当前={e['current_cn']} → 应为 {e['correct_cn']}   [{mark}]")
    if len(errors) > len(show):
        print(f"  ... 以及其余 {len(errors) - len(show)} 处")
    print()

    if not clues_suspect:
        conflict = conflicting_line(row_clues, col_clues, current)
        if conflict:
            axis, idx = conflict
            clues = row_clues[idx] if axis == "row" else col_clues[idx]
            name = "行" if axis == "row" else "列"
            print(f"  连锁冲突: 第 {idx + 1} {name} 的提示 {clues} 在已有填写下无法满足")
            print()

    if clues_suspect:
        print("建议: 先用 python3 -m nonogram --ocr-only <图片> out.json 导出并核对提示数字，")
        print("      确认提示无误后，再修正上面这些与解答不符的格子。")
    else:
        print("修正上面这些格子后重新运行即可得到完整解答。")
    print()


def solve_and_analyze(data):
    row_clues = data["row_clues"]
    col_clues = data["col_clues"]
    current = data.get("current")

    banner("Nonogram 助手")
    print_clues_summary(row_clues, col_clues)

    nrows = len(row_clues)
    ncols = len(col_clues)

    if current:
        banner("当前棋盘")
        filled, total = progress(current)
        print(f"进度: {filled}/{total} ({filled*100//total if total>0 else 0}%)")
        print()
        issues = validate_current_board(current, row_clues, col_clues)
        if issues:
            print("⚠️  当前状态冲突警告:")
            for iss in issues:
                print(f"  - {iss['message']}")
            print()
        print_board(current, row_clues, col_clues, show_numbers=True)
        print()

    print("正在求解...", end="", flush=True)
    solution = Solver(row_clues, col_clues, current).solve() if current else None
    conflict_cells = None
    unique = False

    if solution is None:
        # 先看提示本身是否有解：题目的可解性只由 clues 决定
        probe = Solver(row_clues, col_clues)
        propagated = probe.propagate()
        unique = propagated and all(ch != UNKNOWN for row in probe.board for ch in row)
        base = probe.board if unique else Solver(row_clues, col_clues).solve()
        print(" 完成!")
        print()
        if base is None:
            report_unsolvable_clues()
            banner("结束")
            return
        if not current:
            report_unsolvable_clues()
            banner("结束")
            return
        # 提示有解 → 是当前棋盘填错了，不是"无解"
        solution = base
        conflict_mode = True
        conflict_cells, conflict_definite = find_conflicts(
            row_clues, col_clues, current, solution, unique)
        errors = find_errors(current, solution)
        if conflict_definite and conflict_cells:
            keep = {(r + 1, c + 1) for (r, c) in conflict_cells}
            errors = [e for e in errors if (e["row"], e["col"]) in keep]
        report_conflict(current, solution, unique and bool(conflict_definite),
                        row_clues, col_clues, errors)
    else:
        conflict_mode = False
        print(" 完成!")
        print()

    banner("完整解答")
    print_board(solution, row_clues, col_clues, show_numbers=True)
    print()

    if current:
        errors = find_errors(current, solution)
        if conflict_mode:
            print("当前棋盘（<> 标出冲突格）:")
            print_board(current, row_clues, col_clues, errors=errors, show_numbers=True)
            print()
            banner("下一步")
            print("先修正上面的冲突格，再运行一次: python3 -m nonogram <json>")
            banner("结束")
            return
        banner(f"错误检查 (发现 {len(errors)} 个错误)")
        if errors:
            for i, e in enumerate(errors, 1):
                print(f"  {i:>2}. R{e['row']}C{e['col']}: {e['current_cn']} → 应为 {e['correct_cn']}")
            print()
            print("错误位置标记如下 <错误格>:")
            print_board(current, row_clues, col_clues, errors=errors, show_numbers=True)
            print()
        else:
            print("✓ 当前没有错误，继续加油！")
            print()

        filled, total = progress(current)
        if filled < total:
            banner("下一步提示")
            hint = next_hint(current, solution, row_clues, col_clues)
            if hint:
                print(f"📍 位置: 第 {hint['row']} 行, 第 {hint['col']} 列")
                print(f"🎯 应填: {hint['value_cn']}")
                print(f"💡 推理: {hint['reason']}")
                print()
                print("提示位置标记如下 (提示格):")
                print_board(current, row_clues, col_clues, errors=errors,
                            hint_pos=(hint["row"], hint["col"]), show_numbers=True)
                print()
            else:
                print("🎉 恭喜！已全部完成！")
        else:
            banner("完成")
            print("🎉 恭喜你已经完成了所有格子！")

    banner("结束")


def do_ocr(img_path, output_json=None, debug=False):
    if not HAS_OCR:
        print("❌ OCR 模块不可用，请安装 opencv-python 和 numpy")
        return None
    print(f"正在识别图片: {img_path}")
    debug_dir = os.path.join("outputs", "debug_ocr") if debug else None
    try:
        data = ocr_nonogram(img_path, debug_dir=debug_dir)
        data = validate_and_fix(data)
    except Exception as e:
        print(f"❌ OCR 失败: {e}")
        import traceback
        traceback.print_exc()
        return None

    if output_json:
        out_path = os.path.abspath(output_json)
        out_dir = os.path.dirname(out_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✓ 已保存识别结果到: {out_path}")
    return data


def usage():
    print("""
Nonogram 助手 - 使用方法
========================

1. 从图片识别并求解:
   python3 -m nonogram <图片路径> [--save-json out.json] [--debug]
   (识别结果默认保存到 outputs/puzzle.json，可用 --save-json / 第二个参数改路径)

2. 从 JSON 文件求解:
   python3 -m nonogram <puzzle.json>

3. 仅识别图片为 JSON (不求解):
   python3 -m nonogram --ocr-only <图片路径> [out.json] [--debug]
   (同样默认保存到 outputs/puzzle.json)

格式说明:
  O = 黑格
  X = 空格
  . = 未知
""")


def main():
    args = sys.argv[1:]
    if not args or "--help" in args or "-h" in args:
        usage()
        return

    debug = "--debug" in args
    args = [a for a in args if a != "--debug"]

    ocr_only = False
    if "--ocr-only" in args:
        ocr_only = True
        args.remove("--ocr-only")

    save_json = None
    if "--save-json" in args:
        idx = args.index("--save-json")
        if idx + 1 < len(args):
            save_json = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    if not args:
        usage()
        return

    input_path = args[0]
    ext = os.path.splitext(input_path)[1].lower()

    img_exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff"}

    if ext in img_exts:
        # 默认总是保存一份最新识别结果，方便直接复算 / 手改后再跑
        out_json = save_json or (args[1] if len(args) > 1 else None) or DEFAULT_OCR_JSON
        if ocr_only:
            data = do_ocr(input_path, out_json, debug)
            if data:
                banner("OCR 识别结果")
                print_clues_summary(data["row_clues"], data["col_clues"])
                print("行提示:", data["row_clues"])
                print("列提示:", data["col_clues"])
                if data.get("current"):
                    print("\n当前棋盘:")
                    for row in data["current"]:
                        print(row)
            return
        else:
            data = do_ocr(input_path, out_json, debug)
            if not data:
                return
            solve_and_analyze(data)
            return

    if ext == ".json" or os.path.isfile(input_path):
        data = load(input_path)
        solve_and_analyze(data)
        return

    print(f"❌ 无法识别输入: {input_path}")
    usage()


if __name__ == "__main__":
    main()
