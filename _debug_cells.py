import cv2, numpy as np, os
from ocr_nonogram import detect_grid_lines, find_board_region, detect_sub_lines, recognize_number_cell, fallback_recognize_digit, build_digit_templates

img = cv2.imread('/Users/bili/nonogram/Screenshots/PixPin_2026-09-24_17-31-14.png')
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
v_lines, h_lines = detect_grid_lines(gray)
vs, ve, hs, he = find_board_region(v_lines, h_lines)

row_clue_img = img[h_lines[hs]:h_lines[he], 0:v_lines[vs]]
rc_gray = cv2.cvtColor(row_clue_img, cv2.COLOR_BGR2GRAY)

col_clue_img = img[0:h_lines[hs], v_lines[vs]:v_lines[ve]]
cc_gray = cv2.cvtColor(col_clue_img, cv2.COLOR_BGR2GRAY)

print(f'Row clue area: {rc_gray.shape}')
print(f'Col clue area: {cc_gray.shape}')

v_sub = detect_sub_lines(rc_gray, axis=0)
h_sub = detect_sub_lines(rc_gray, axis=1)
v_sub_full = [0] + v_sub + [rc_gray.shape[1]]
h_sub_full = [0] + h_sub + [rc_gray.shape[0]]
print(f'Row clue sub lines: V={len(v_sub_full)-1} cols, H={len(h_sub_full)-1} rows')
print(f'  V: {v_sub_full}')
print(f'  H: {h_sub_full[:6]}...')

outdir = '/tmp/cells_sample'
os.makedirs(outdir, exist_ok=True)

# 行提示 R1~R5 的所有cell
correct_rc = {
    0: [1,5,1,3,2], 1: [2,1,1,1,1], 2: [6,1,1], 3: [5,3,1], 4: [4,13,1,2]
}
board_h_grid = h_lines[hs:he+1]
print(f'\n=== Row Clue Cells with recognize (正确的对应数字标在后面) ===')
for r in range(5):
    y1 = board_h_grid[r] - h_lines[hs]
    y2 = board_h_grid[r+1] - h_lines[hs]
    y1 = max(0, y1); y2 = min(rc_gray.shape[0], y2)
    correct = correct_rc.get(r, [])
    print(f'\nR{r+1} (correct={correct}): cells along x')
    for c in range(len(v_sub_full)-1):
        x1, x2 = v_sub_full[c], v_sub_full[c+1]
        if x2-x1<5 or y2-y1<5: continue
        cell = rc_gray[y1:y2, x1:x2]
        num = recognize_number_cell(cell)
        fname = f'R{r+1}_C{c+1}_got{num}.png'
        cv2.imwrite(os.path.join(outdir, fname), cell)
        print(f'  [{x1}:{x2},{y1}:{y2}] recognize={num}')

# 列提示 C1~C5 的所有cell
correct_cc = {
    0: [7,4,2,3], 1: [13,3,3], 2: [1,5,1,1,3], 3: [3,6,1], 4: [5,3,3,3]
}
cv_sub_v = detect_sub_lines(cc_gray, axis=0)
cv_sub_h = detect_sub_lines(cc_gray, axis=1)
cv_sub_v_full = [0] + cv_sub_v + [cc_gray.shape[1]]
cv_sub_h_full = [0] + cv_sub_h + [cc_gray.shape[0]]
print(f'\nCol clue sub lines: V={len(cv_sub_v_full)-1} cols, H={len(cv_sub_h_full)-1} rows')
print(f'  V full: {cv_sub_v_full}')
print(f'  H full: {cv_sub_h_full}')

board_v_grid = v_lines[vs:ve+1]
print(f'\n=== Col Clue Cells (C1~C5, columns of clues stacked vertically) ===')
for c in range(5):
    x1 = board_v_grid[c] - v_lines[vs]
    x2 = board_v_grid[c+1] - v_lines[vs]
    x1 = max(0, x1); x2 = min(cc_gray.shape[1], x2)
    correct = correct_cc.get(c, [])
    # 逐行扫 (h方向)
    items = []
    for hr in range(len(cv_sub_h_full)-1):
        y1, y2 = cv_sub_h_full[hr], cv_sub_h_full[hr+1]
        if x2-x1<5 or y2-y1<5: continue
        cell = cc_gray[y1:y2, x1:x2]
        num = recognize_number_cell(cell)
        fname = f'C{c+1}_R{hr+1}_got{num}.png'
        cv2.imwrite(os.path.join(outdir, fname), cell)
        if num is not None and num > 0:
            items.append(num)
            print(f'  C{c+1} row{hr+1} [{x1}:{x2},{y1}:{y2}] recognize={num}')
    print(f'C{c+1} final got={items}, correct={correct}')

print(f'\nSaved all cell images to {outdir}')
