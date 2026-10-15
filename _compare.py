import json
import sys
sys.path.insert(0, '/Users/bili/nonogram')
from ocr_nonogram import ocr_nonogram, validate_and_fix

print("=== 本地OCR识别中...")
ocr = ocr_nonogram('/Users/bili/nonogram/Screenshots/PixPin_2026-09-24_17-31-14.png')
ocr = validate_and_fix(ocr)

correct = json.loads("""
{ 
   "size": { 
     "rows": 30, 
     "cols": 30 
   }, 
   "row_clues": [ 
     [1,5,1,3,2], 
     [2,1,1,1,1], 
     [6,1,1], 
     [5,3,1], 
     [4,13,1,2], 
     [2,4,5,1,1,1], 
     [1,7,3,4], 
     [1,4,4,3,1], 
     [2,4,12,1,2], 
     [2,3,1,9,1,2], 
     [2,2,3,5,4,2], 
     [2,3,11], 
     [2,5,5,3,2], 
     [2,3,2,8,1,1], 
     [1,1,3,9,1,2], 
     [3,1,1,1,5,10], 
     [1,3,21], 
     [5,8,7,4], 
     [8,1,5,5], 
     [4,3,5,3], 
     [3,3,5,1,2], 
     [1,1,3,2,4], 
     [1,4,3,3], 
     [3,1,4,2,2], 
     [2,1,6,4,2], 
     [6,1,1,6,3,2], 
     [2,3,4,2,1], 
     [3,2,1,6,1], 
     [3,1,7,1], 
     [3,1,1,1] 
   ], 
   "col_clues": [ 
     [7,4,2,3], 
     [13,3,3], 
     [1,5,1,1,3], 
     [3,6,1], 
     [5,3,3,3], 
     [4,5,3,1,3], 
     [3,3,2,1,1], 
     [2,4,2,3], 
     [1,4,1,3], 
     [1,1,1,3,2,4], 
     [1,1,1,2,2,3,1,1], 
     [1,5,3,3,5], 
     [13,6,3], 
     [1,10,1,1,2], 
     [2,3,4,1,9,6], 
     [1,2,8,7], 
     [1,3,9,8], 
     [2,10,4,1], 
     [1,2,8,3,3], 
     [], 
     [3,12,1,1], 
     [2,1,7,3], 
     [], 
     [3,3,3,4,1], 
     [1,3,9,5], 
     [2,2,3], 
     [1,4,8,1], 
     [2,1,2,4,1], 
     [1,1,3,3,4], 
     [3,3,2,5] 
   ] 
}
""")

ocr_rc = ocr['row_clues']
ocr_cc = ocr['col_clues']
cor_rc = correct['row_clues']
cor_cc = correct['col_clues']
nrows = len(cor_rc)
ncols = len(cor_cc)

print(f"\n=== 棋盘尺寸 ===")
print(f"OCR:    {len(ocr_rc)} rows x {len(ocr_cc)} cols")
print(f"正确:   {nrows} rows x {ncols} cols")

print(f"\n=== 行提示对比 (R1~R30) ===")
row_ok = 0
row_total = 0
row_num_ok = 0
row_num_total = 0
for r in range(nrows):
    a = ocr_rc[r] if r < len(ocr_rc) else ['?']
    b = cor_rc[r]
    match = a == b
    row_ok += match
    row_total += 1
    mark = "✓" if match else "✗"
    if len(a) == len(b):
        for i in range(len(a)):
            row_num_total += 1
            if a[i] == b[i]:
                row_num_ok += 1
    else:
        row_num_total += max(len(a), len(b))
    print(f"R{r+1:>2} {mark} OCR={a}  正确={b}")

print(f"\n=== 列提示对比 (C1~C30) ===")
col_ok = 0
col_total = 0
col_num_ok = 0
col_num_total = 0
for c in range(ncols):
    a = ocr_cc[c] if c < len(ocr_cc) else ['?']
    b = cor_cc[c]
    match = a == b
    col_ok += match
    col_total += 1
    mark = "✓" if match else "✗"
    if len(a) == len(b):
        for i in range(len(a)):
            col_num_total += 1
            if a[i] == b[i]:
                col_num_ok += 1
    else:
        col_num_total += max(len(a), len(b))
    print(f"C{c+1:>2} {mark} OCR={a}  正确={b}")

print(f"\n=== 总准确率 ===")
print(f"行 整行匹配: {row_ok}/{row_total} = {row_ok*100//row_total if row_total else 0}%")
print(f"列 整列匹配: {col_ok}/{col_total} = {col_ok*100//col_total if col_total else 0}%")
total_num_ok = row_num_ok + col_num_ok
total_num = row_num_total + col_num_total
print(f"单数字准确率: {total_num_ok}/{total_num} = {total_num_ok*100//total_num if total_num else 0}%")

ocr_cur = ocr.get('current', [])
cor_cur = correct.get('current', [])
print(f"\n=== 当前棋盘对比 ===")
print(f"OCR行数: {len(ocr_cur)}, 正确行数: {len(cor_cur)}")
cell_ok = 0
cell_total = 0
char_map = {'#': 'O', 'x': 'X', 'O': 'O', 'X': 'X', '.': '.'}
for r in range(min(nrows, len(cor_cur))):
    if r >= len(ocr_cur):
        break
    ocr_row = ocr_cur[r]
    cor_row = cor_cur[r]
    L = min(len(ocr_row), len(cor_row), ncols)
    for c in range(L):
        o = ocr_row[c]
        cc = cor_row[c]
        o_norm = char_map.get(o, o)
        cc_norm = char_map.get(cc, cc)
        cell_total += 1
        if o_norm == cc_norm:
            cell_ok += 1
        else:
            pass
print(f"棋盘格子准确率: {cell_ok}/{cell_total} = {cell_ok*100//cell_total if cell_total else 0}%")
