import cv2
import numpy as np
import json
import sys
import os

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False


def merge_lines(arr, gap=5):
    if not arr:
        return []
    groups = [[arr[0]]]
    for x in arr[1:]:
        if x - groups[-1][-1] <= gap:
            groups[-1].append(x)
        else:
            groups.append([x])
    return [int(np.mean(g)) for g in groups]


def detect_grid_lines(gray):
    h, w = gray.shape
    _, th = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY_INV)

    v_sum = th.sum(axis=0) / 255
    h_sum = th.sum(axis=1) / 255

    candidates = []
    for ratio in [0.85, 0.75, 0.65, 0.55, 0.45, 0.35, 0.25, 0.15]:
        v_thresh = h * ratio
        h_thresh = w * ratio
        v_lines = merge_lines([i for i, x in enumerate(v_sum) if x > v_thresh])
        h_lines = merge_lines([i for i, x in enumerate(h_sum) if x > h_thresh])
        candidates.append((v_lines, h_lines, ratio))
        if len(v_lines) >= 15 and len(h_lines) >= 15:
            break

    def _score(vl, hl):
        if len(vl) < 6 or len(hl) < 6:
            return -999
        diff = abs(len(vl) - len(hl))
        square = -diff * 5
        size = min(len(vl), len(hl))
        return size * 10 + square

    best_v, best_h = None, None
    best_s = -9999
    for v_lines, h_lines, ratio in candidates:
        s = _score(v_lines, h_lines)
        if s > best_s:
            best_s = s
            best_v, best_h = v_lines, h_lines
    return best_v, best_h


def find_board_region(v_lines, h_lines, min_cells=5):
    def best_axis(lines):
        """Find the largest regular run independently for one axis.

        Nonograms are not necessarily square.  The old implementation used
        one shared ``size`` for both axes, so a 30x25 board was truncated to
        25x25 before clue OCR even started.
        """
        best = None
        max_cells = len(lines) - 1
        for size in range(max_cells, min_cells - 1, -1):
            for start in range(0, len(lines) - size):
                end = start + size
                spacing = np.diff(lines[start:end + 1]).astype(float)
                mean = float(np.mean(spacing)) if len(spacing) else 0.0
                cv = float(np.std(spacing) / mean) if mean > 0 else 999.0
                if mean < 10 or cv > 0.15:
                    continue
                # Prefer the longest regular run, then the most even one.
                score = (size, -cv, mean)
                if best is None or score > best[0]:
                    best = (score, start, end)
            if best is not None:
                break

        if best is not None:
            return best[1], best[2]

        # Conservative fallback for unusual screenshots.
        return 1, max(1, len(lines) - 1)

    vs, ve = best_axis(v_lines)
    hs, he = best_axis(h_lines)
    return vs, ve, hs, he


def detect_sub_lines(region_gray, axis=0, min_gap=6):
    h, w = region_gray.shape
    if h < 3 or w < 3:
        return []

    _, th = cv2.threshold(region_gray, 140, 255, cv2.THRESH_BINARY_INV)
    kernel = np.ones((3,1), np.uint8) if axis == 0 else np.ones((1,3), np.uint8)
    if axis == 0:
        dilated = cv2.dilate(th, np.ones((max(3, h//5), 1), np.uint8), iterations=1)
        s = dilated.sum(axis=0) / 255
        thresh = max(2, h * 0.08)
    else:
        dilated = cv2.dilate(th, np.ones((1, max(3, w//5)), np.uint8), iterations=1)
        s = dilated.sum(axis=1) / 255
        thresh = max(2, w * 0.08)

    strong_lines = merge_lines([i for i, x in enumerate(s) if x > thresh], gap=min_gap)
    if not strong_lines:
        return []

    content_between = []
    for i in range(len(strong_lines) - 1):
        mid_start = strong_lines[i]
        mid_end = strong_lines[i + 1]
        if mid_end - mid_start < min_gap * 2:
            continue
        if axis == 0:
            sub = th[:, mid_start:mid_end]
            ss = sub.sum(axis=0) / 255
            low_t = max(1, h * 0.03)
        else:
            sub = th[mid_start:mid_end, :]
            ss = sub.sum(axis=1) / 255
            low_t = max(1, w * 0.03)
        finer = merge_lines([mid_start + j for j, x in enumerate(ss) if x > low_t], gap=max(2, min_gap//2))
        content_between.extend(finer)

    all_lines = sorted(set(strong_lines + content_between))
    return all_lines


def ocr_number(cell_img, debug_path=None):
    if cell_img is None or cell_img.size == 0:
        return None

    h, w = cell_img.shape[:2]
    if h < 5 or w < 5:
        return None

    if len(cell_img.shape) == 3:
        gray = cv2.cvtColor(cell_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = cell_img.copy()

    gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    coords = cv2.findNonZero(bw)
    if coords is None:
        return None
    x, y, cw, ch = cv2.boundingRect(coords)
    if cw < 3 or ch < 3:
        return None
    bw = bw[y:y + ch, x:x + cw]

    pad = 8
    bw = cv2.copyMakeBorder(bw, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
    bw = cv2.resize(bw, (48, 64), interpolation=cv2.INTER_AREA)

    if debug_path:
        cv2.imwrite(debug_path, bw)

    if HAS_TESSERACT:
        try:
            custom_config = r'--oem 3 --psm 10 -c tessedit_char_whitelist=0123456789'
            text = pytesseract.image_to_string(bw, config=custom_config).strip()
            text = text.replace('O', '0').replace('l', '1').replace('I', '1').replace('Z', '2').replace('S', '5').replace('B', '8')
            if text.isdigit():
                return int(text)
        except Exception:
            pass

    return fallback_recognize_digit(bw)


def build_digit_templates():
    size = (48, 64)
    templates = {}
    digits = {
        0: ["0000000000000000",
            "0000011111100000",
            "0001111111111000",
            "0011110000111100",
            "0011100000011100",
            "0111000000001110",
            "0110000000000110",
            "0110000000000110",
            "0110000000000110",
            "0110000000000110",
            "0110000000000110",
            "0110000000000110",
            "0110000000000110",
            "0011100000011100",
            "0011110000111100",
            "0001111111111000",
            "0000011111100000",
            "0000000000000000"],
        1: ["0000000000000000",
            "0000000110000000",
            "0000001110000000",
            "0000011110000000",
            "0000111110000000",
            "0001111110000000",
            "0011101110000000",
            "0111000110000000",
            "0110000110000000",
            "0100000110000000",
            "0000000110000000",
            "0000000110000000",
            "0000000110000000",
            "0000000110000000",
            "0000000110000000",
            "0111111111111110",
            "0111111111111110",
            "0000000000000000"],
        2: ["0000000000000000",
            "0000111111110000",
            "0011111111111100",
            "0111100000011110",
            "0111000000001110",
            "0000000000011110",
            "0000000000111100",
            "0000000001111000",
            "0000000011110000",
            "0000000111100000",
            "0000001111000000",
            "0000011110000000",
            "0000111100000000",
            "0001111000000000",
            "0011110000000000",
            "0111111111111110",
            "0111111111111110",
            "0000000000000000"],
        3: ["0000000000000000",
            "0000111111110000",
            "0011111111111100",
            "0111100000011110",
            "0000000000011110",
            "0000000000011110",
            "0000000000111100",
            "0000000011111000",
            "0000000111111000",
            "0000000001111000",
            "0000000000111100",
            "0000000000011110",
            "0000000000011110",
            "0111000000011100",
            "0111100000011110",
            "0011111111111100",
            "0000111111110000",
            "0000000000000000"],
        4: ["0000000000000000",
            "0000000001110000",
            "0000000111110000",
            "0000001111110000",
            "0000011101110000",
            "0000111001110000",
            "0001110001110000",
            "0011100001110000",
            "0111000001110000",
            "0110000001110000",
            "0111111111111110",
            "0111111111111110",
            "0000000001110000",
            "0000000001110000",
            "0000000001110000",
            "0000000001110000",
            "0000000001110000",
            "0000000000000000"],
        5: ["0000000000000000",
            "0111111111111110",
            "0111111111111110",
            "0111100000000000",
            "0111100000000000",
            "0111100000000000",
            "0111111111110000",
            "0111111111111100",
            "0000000000011110",
            "0000000000011110",
            "0000000000011110",
            "0000000000011110",
            "0000000000011110",
            "0111100000011110",
            "0111100000011110",
            "0011111111111100",
            "0000111111110000",
            "0000000000000000"],
        6: ["0000000000000000",
            "0000011111110000",
            "0001111111111000",
            "0011111000000000",
            "0111100000000000",
            "0111000000000000",
            "0111000000000000",
            "0111111111110000",
            "0111111111111100",
            "0111000000001110",
            "0111000000000110",
            "0111000000000110",
            "0111000000001110",
            "0111100000011110",
            "0111100000011110",
            "0011111111111100",
            "0001111111111000",
            "0000000000000000"],
        7: ["0000000000000000",
            "0111111111111110",
            "0111111111111110",
            "0111111000011110",
            "0000000000111100",
            "0000000001111000",
            "0000000001110000",
            "0000000011100000",
            "0000000111000000",
            "0000000111000000",
            "0000001110000000",
            "0000001110000000",
            "0000011100000000",
            "0000011100000000",
            "0000111000000000",
            "0000111000000000",
            "0000111000000000",
            "0000000000000000"],
        8: ["0000000000000000",
            "0000111111110000",
            "0011111111111100",
            "0111100000011110",
            "0111000000001110",
            "0111000000001110",
            "0011110000111100",
            "0001111111111000",
            "0000111111110000",
            "0001111111111000",
            "0011110000111100",
            "0111000000001110",
            "0111000000001110",
            "0111100000011110",
            "0111100000011110",
            "0011111111111100",
            "0000111111110000",
            "0000000000000000"],
        9: ["0000000000000000",
            "0000111111110000",
            "0011111111111100",
            "0111100000011110",
            "0111000000011110",
            "0111000000011110",
            "0011110000111100",
            "0011111111111100",
            "0001111111111100",
            "0000000000011110",
            "0000000000011110",
            "0000000000011100",
            "0000000000111000",
            "0000000001110000",
            "0000000011110000",
            "0011111111100000",
            "0011111111000000",
            "0000000000000000"],
    }
    for d, rows in digits.items():
        arr = np.zeros((len(rows), len(rows[0])), dtype=np.uint8)
        for i, r in enumerate(rows):
            for j, c in enumerate(r):
                arr[i, j] = 255 if c == '1' else 0
        templates[d] = cv2.resize(arr, size, interpolation=cv2.INTER_AREA)
    return templates


DIGIT_TEMPLATES = build_digit_templates()


def _preprocess_digit(bw_img, target_size=(48, 64)):
    if bw_img is None or bw_img.size == 0:
        return None
    coords = cv2.findNonZero(bw_img)
    if coords is None:
        return None
    x, y, w, h = cv2.boundingRect(coords)
    if w < 2 or h < 2:
        return None
    cropped = bw_img[y:y + h, x:x + w]
    tw, th = target_size
    max_w = int(tw * 0.8)
    max_h = int(th * 0.8)
    scale = min(max_w / w, max_h / h)
    scale = min(scale, 4.0)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    resized = cv2.resize(cropped, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    canvas = np.zeros((th, tw), dtype=np.uint8)
    ox = (tw - nw) // 2
    oy = (th - nh) // 2
    canvas[oy:oy + nh, ox:ox + nw] = resized
    _, canvas = cv2.threshold(canvas, 1, 255, cv2.THRESH_BINARY)
    return canvas


def _hu_moments_match(img1, img2):
    try:
        _, img1_b = cv2.threshold(img1, 1, 255, cv2.THRESH_BINARY)
        _, img2_b = cv2.threshold(img2, 1, 255, cv2.THRESH_BINARY)
        m1 = cv2.HuMoments(cv2.moments(img1_b)).flatten()
        m2 = cv2.HuMoments(cv2.moments(img2_b)).flatten()
        m1_log = -np.sign(m1) * np.log10(np.abs(m1) + 1e-20)
        m2_log = -np.sign(m2) * np.log10(np.abs(m2) + 1e-20)
        weights = np.array([1.0, 1.0, 0.8, 0.6, 0.4, 0.4, 0.4])
        diff = np.abs(m1_log - m2_log) * weights
        dist = float(np.sqrt(np.sum(diff * diff)))
        return dist
    except Exception:
        return 999.0


DIGIT_MATCH_CACHE = {}


def fallback_recognize_digit(img):
    if img is None or img.size == 0:
        return None
    try:
        proc = _preprocess_digit(img, (48, 64))
    except Exception:
        return None
    if proc is None:
        return None
    best_digit = None
    best_hu = 1e9
    best_iou = -1
    for d, tpl in DIGIT_TEMPLATES.items():
        tpr = tpl
        if tpr.shape != proc.shape:
            tpr = cv2.resize(tpr, (proc.shape[1], proc.shape[0]), interpolation=cv2.INTER_AREA)
            _, tpr = cv2.threshold(tpr, 1, 255, cv2.THRESH_BINARY)
        hu = _hu_moments_match(proc, tpr)
        intersection = cv2.bitwise_and(proc, tpr)
        union = cv2.bitwise_or(proc, tpr)
        i_sum = float(np.sum(intersection > 0))
        u_sum = float(np.sum(union > 0))
        iou = (i_sum / u_sum) if u_sum > 0 else 0.0
        score_comb = hu * 0.7 - iou * 5.0
        if score_comb < (best_hu * 0.7 - best_iou * 5.0):
            best_hu = hu
            best_iou = iou
            best_digit = d
    if best_digit is None:
        return None
    hu_ok = best_hu < 1.2
    iou_ok = best_iou > 0.15
    if hu_ok or iou_ok:
        return best_digit
    return None


def recognize_number_cell(cell_img, debug_path=None):
    if cell_img is None or cell_img.size == 0:
        return None
    h, w = cell_img.shape[:2]
    if h < 6 or w < 6:
        return None

    if len(cell_img.shape) == 3:
        gray = cv2.cvtColor(cell_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = cell_img.copy()

    best_num = None
    for thr_mode in ['otsu', 'binv140', 'binv160', 'binv120', 'adaptive']:
        if thr_mode == 'otsu':
            _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        elif thr_mode == 'adaptive':
            bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 8)
        else:
            t = int(thr_mode.replace('binv', ''))
            _, bw = cv2.threshold(gray, t, 255, cv2.THRESH_BINARY_INV)
        for dk in range(3):
            bw_trial = bw
            if dk > 0:
                bw_trial = cv2.dilate(bw, np.ones((dk + 1, dk + 1), np.uint8), iterations=1)
            else:
                bw_trial = cv2.morphologyEx(bw_trial, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
            nlabels, labels, stats, centroids = cv2.connectedComponentsWithStats(bw_trial, connectivity=8)
            comps = []
            h_img, w_img = bw_trial.shape
            for i in range(1, nlabels):
                x, y, cw, ch, area = stats[i]
                if area < 4:
                    continue
                if cw < 1 or ch < 3:
                    continue
                if ch < h_img * 0.18:
                    continue
                comps.append((x, y, cw, ch, i))
            if not comps:
                continue
            comps.sort(key=lambda c: c[0])
            digits = []
            for (x, y, cw, ch, idx) in comps:
                mask = np.zeros_like(bw_trial)
                mask[labels == idx] = 255
                digit_img = mask[y:y + ch, x:x + cw]
                pad = max(1, min(cw, ch) // 3)
                digit_img = cv2.copyMakeBorder(digit_img, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
                d = fallback_recognize_digit(digit_img)
                if d is not None:
                    digits.append(str(d))
            if digits:
                num_str = ''.join(digits)
                if num_str.isdigit():
                    val = int(num_str)
                    if best_num is None:
                        best_num = val
                        first_len = len(digits)
                    else:
                        if len(digits) > first_len:
                            best_num = val
                            first_len = len(digits)
    return best_num


# --------------------------------------------------------------- 提示数字识别
# 思路：提示区没有任何分隔线，数字之间的间隔也不固定，所以按
#   1) 二值化 + 去掉长直线
#   2) 连通域切字形（粘连的两位数沿投影谷值切开）
#   3) 按间距聚成"数字"
#   4) 每个字形缩放到固定画布，与多种粗体字体的 0-9 模板做容差匹配
# 的顺序识别，比"把整格丢给 OCR 猜一个数"稳得多。

_GLYPH_CANVAS = (32, 40)
_GLYPH_SHIFTS = [(dy, dx)
                 for dy in (-1, 0, 1)
                 for dx in (-1, 0, 1)]
_GLYPH_TEMPLATES = None

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Verdana Bold.ttf",
    "/System/Library/Fonts/Supplemental/Tahoma Bold.ttf",
    "/System/Library/Fonts/Supplemental/Verdana.ttf",
    "/System/Library/Fonts/Supplemental/Tahoma.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/System/Library/Fonts/Supplemental/Trebuchet MS Bold.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]


def _normalize_glyph(mask, size=_GLYPH_CANVAS):
    """按高度归一化并居中，保留长宽比（'1' 就该是窄的）。"""
    tw, th = size
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    crop = (mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1] * 255).astype(np.uint8)
    h, w = crop.shape
    scale = (th * 0.86) / h
    nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    if nw > tw * 0.9:
        scale = (tw * 0.9) / w
        nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    resized = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((th, tw), np.uint8)
    ox, oy = (tw - nw) // 2, (th - nh) // 2
    canvas[oy:oy + nh, ox:ox + nw] = resized
    return (canvas > 100).astype(np.uint8)


def _glyph_templates():
    """渲染 0-9 模板（多字体），带距离变换缓存。"""
    global _GLYPH_TEMPLATES
    if _GLYPH_TEMPLATES is not None:
        return _GLYPH_TEMPLATES

    out = {}
    try:
        from PIL import Image, ImageDraw, ImageFont
        for path in _FONT_CANDIDATES:
            if not os.path.exists(path):
                continue
            try:
                font = ImageFont.truetype(path, 64)
            except Exception:
                continue
            for d in range(10):
                im = Image.new("L", (200, 200), 0)
                ImageDraw.Draw(im).text((60, 60), str(d), fill=255, font=font)
                arr = np.array(im)
                ys, xs = np.nonzero(arr)
                if len(xs) == 0:
                    continue
                m = (arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1] > 100).astype(np.uint8)
                nm = _normalize_glyph(m)
                if nm is None:
                    continue
                out[(path.split("/")[-1], d)] = (
                    nm, cv2.distanceTransform((1 - nm).astype(np.uint8), cv2.DIST_L2, 3))
    except Exception:
        out = {}

    if not out:
        # 没有任何可用字体时，退回内置点阵模板
        for d, tpl in DIGIT_TEMPLATES.items():
            m = (np.array(tpl, dtype=np.uint8) > 0).astype(np.uint8)
            nm = _normalize_glyph(m)
            if nm is not None:
                out[("builtin", d)] = (
                    nm, cv2.distanceTransform((1 - nm).astype(np.uint8), cv2.DIST_L2, 3))

    _GLYPH_TEMPLATES = out
    return out


def _glyph_score(a, dt_a, b, dt_b):
    """带平移容差的对称距离，越小越像。"""
    ys_a, xs_a = np.nonzero(a)
    ys_b, xs_b = np.nonzero(b)
    best = 1e9
    for dy, dx in _GLYPH_SHIFTS:
        d1 = np.roll(np.roll(dt_b, -dy, 0), -dx, 1)[ys_a, xs_a].mean()
        d2 = np.roll(np.roll(dt_a, dy, 0), dx, 1)[ys_b, xs_b].mean()
        s = (float(d1) + float(d2)) / 2
        if s < best:
            best = s
    return best


def _count_holes(mask):
    """统计掩码中内部孔洞的数量（'0' 有 1 个，'8' 有 2 个，实心块有 0 个）。"""
    if mask is None or mask.size == 0:
        return 0
    bw = (mask > 0).astype(np.uint8)
    contours, hierarchy = cv2.findContours(bw, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return 0
    holes = 0
    for i in range(len(contours)):
        if hierarchy[0][i][3] != -1:  # has parent → inner contour → hole
            holes += 1
    return holes


def _recognize_glyph(mask, templates, coarse_limit=8):
    """返回 (digit, score, margin)；识别不出来返回 (None, 9.9, 0)。"""
    nm = _normalize_glyph(mask)
    if nm is None:
        return None, 9.9, 0.0
    dt_nm = cv2.distanceTransform((1 - nm).astype(np.uint8), cv2.DIST_L2, 3)
    ys, xs = np.nonzero(nm)

    coarse = []
    for key, (tpl, dt_tpl) in templates.items():
        s = (float(dt_tpl[ys, xs].mean()) + float(dt_nm[tpl > 0].mean())) / 2
        coarse.append((s, key))
    coarse.sort(key=lambda x: x[0])

    best_key, best_s, second = None, 1e9, 1e9
    for _, key in coarse[:coarse_limit]:
        tpl, dt_tpl = templates[key]
        s = _glyph_score(nm, dt_nm, tpl, dt_tpl)
        if s < best_s:
            second, best_s, best_key = best_s, s, key
        elif s < second:
            second = s
    if best_key is None:
        return None, 9.9, 0.0

    # 拓扑修正：低分辨率下 '0' 归一化后孔洞消失，形似实心椭圆，容易被
    # 误判为 '8'。两种情况需要纠正：
    #   1) '8' 应有 2 个孔洞，但掩码只有 0-1 个 → 很可能是 '0'
    #   2) '8' 的得分偏高（> 0.15，说明匹配并不好），且 '0' 得分接近 → '0'
    best_digit = best_key[1]
    if best_digit == 8:
        holes = _count_holes(mask)
        # 找 '0' 的最佳得分（遍历全部模板，不受 coarse_limit 限制，
        # 因为 '0' 的粗略得分可能较差而不在前 N 名中）
        zero_s = 1e9
        zero_key = None
        for key, (tpl, dt_tpl) in templates.items():
            if key[1] == 0:
                s = _glyph_score(nm, dt_nm, tpl, dt_tpl)
                if s < zero_s:
                    zero_s, zero_key = s, key
        if zero_key is not None:
            # 孔洞不足，或 '8' 得分差且 '0' 接近 → 改判 '0'
            if holes < 2 or (best_s > 0.15 and zero_s - best_s < 0.25):
                second = best_s
                best_s, best_key = zero_s, zero_key
                best_digit = 0

    # 反向修正：'0' 被正确识别但字形实际有 2 个孔洞（即 '8'），且 '8'
    # 模板得分更好 → 改判 '8'。低分辨率下 '8' 的孔洞可能模糊，使 '0'
    # 模板粗略得分更优而不在 coarse 候选中，故需遍历全部模板。
    if best_digit == 0:
        holes = _count_holes(mask)
        if holes >= 2:
            eight_s = 1e9
            eight_key = None
            for key, (tpl, dt_tpl) in templates.items():
                if key[1] == 8:
                    s = _glyph_score(nm, dt_nm, tpl, dt_tpl)
                    if s < eight_s:
                        eight_s, eight_key = s, key
            if eight_key is not None and eight_s < best_s:
                second = best_s
                best_s, best_key = eight_s, eight_key
                best_digit = 8

    return best_digit, best_s, second - best_s


def _ink_mask(bgr):
    """笔迹掩码（ink=255）。

    不能只看灰度：游戏会把"当前行/列"的提示数字标成橙色，橙色转成灰度约 140，
    而一条提示里往往同时有黑字和白底，Otsu 的阈值会夹在中间，橙色数字直接被当背景
    丢掉。这里改成用 "暗(255-V) 或 饱和(S)" 作为笔迹强度，黑字和彩色字都能拿到高分，
    白底和浅色高亮底都很低。
    """
    if len(bgr.shape) == 2:
        bgr = cv2.cvtColor(bgr, cv2.COLOR_GRAY2BGR)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2].astype(np.int16)
    s = hsv[:, :, 1].astype(np.int16)
    score = np.clip(np.maximum(255 - v, s), 0, 255).astype(np.uint8)
    _, ink = cv2.threshold(score, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return ink


def _binarize_strip(img):
    bw = _ink_mask(img)
    h, w = bw.shape
    if h < 3 or w < 3:
        return bw
    # 只清掉"贯穿整条"的直线（边框/分组线）。注意不能用"像素总数多"来判定：
    # 相邻两位数字的底部连起来也能占到 80% 宽度，那会把字形切掉一截。
    ink = (bw > 0).astype(np.uint8)
    row_runs = np.array([_longest_run(r) for r in ink])
    col_runs = np.array([_longest_run(c) for c in ink.T])
    for i in np.where(row_runs >= w * 0.92)[0]:
        bw[max(0, i - 1):i + 2, :] = 0
    for i in np.where(col_runs >= h * 0.92)[0]:
        bw[:, max(0, i - 1):i + 2] = 0
    return bw


def _longest_run(bits):
    best = cur = 0
    for v in bits:
        if v:
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 0
    return best


def _split_touching(mask, x, y, w, h, templates=None):
    """粘连的两位数（如 '13'/'10'）沿投影谷值切开。

    当投影谷值不够低（两位数字底部相连）或字形明显偏宽时，改用
    识别引导切割：遍历所有切割位置，选两侧识别得分之和最小的点。
    """
    if w < h * 0.95:
        return [(mask, x, y, w, h)]
    sub = mask[y:y + h, x:x + w]
    colsum = sub.sum(axis=0)
    lo = max(1, int(w * 0.25))
    hi = min(w - 1, max(int(w * 0.75), lo + 1))
    seg = colsum[lo:hi]
    if seg.size == 0:
        return [(mask, x, y, w, h)]
    cut = lo + int(np.argmin(seg))
    # 谷径阈值：谷值占列峰值 30% 以下才认为是真缝隙。
    # 但若字形明显偏宽（w > 1.3*h，几乎不可能是单数字），即使谷值
    # 较高也强制切开——两位数底部相连时投影谷值会偏高。
    force_split = w > h * 1.3
    if (colsum[cut] > 0.30 * max(1, colsum.max()) and not force_split) or cut < 2 or w - cut < 2:
        return [(mask, x, y, w, h)]
    # 投影谷值切割可能切到字形内部（如 '0' 的孔洞），产生高得分碎片。
    # 在切割点附近 ±2 列找真正的最窄处，避免切到字形内部。
    search_lo = max(1, cut - 2)
    search_hi = min(w - 1, cut + 3)
    cut = search_lo + int(np.argmin(colsum[search_lo:search_hi]))

    out = _make_split(mask, x, y, w, h, cut)
    if len(out) == 2:
        # 验证切割质量：若任一侧识别得分很高（> 0.3），说明切错了位置
        # （如切到了 '0' 的孔洞里）。改用识别引导切割。
        if templates is not None and _split_score(out, templates) > 0.3:
            guided = _recognition_guided_split(mask, x, y, w, h, templates)
            if guided:
                return guided
        return out

    # 识别引导的回退：若投影切割不成功，遍历所有切割位置，
    # 选两侧归一化字形得分之和最小的点。
    if templates is not None:
        guided = _recognition_guided_split(mask, x, y, w, h, templates)
        if guided:
            return guided
    return [(mask, x, y, w, h)]


def _split_score(pieces, templates):
    """两侧识别得分之和（越高越不像合法切割）。"""
    total = 0.0
    for m, px, py, pw, ph in pieces:
        d, s, _ = _recognize_glyph(m, templates)
        total += s
    return total


def _recognition_guided_split(mask, x, y, w, h, templates):
    """遍历所有切割位置，选两侧得分之和最小的切割点。"""
    best = None
    for sp in range(3, w - 2):
        out = _make_split(mask, x, y, w, h, sp)
        if len(out) != 2:
            continue
        score = _split_score(out, templates)
        if best is None or score < best[0]:
            best = (score, out)
    if best and best[0] < 0.35:
        return best[1]
    return []


def _make_split(mask, x, y, w, h, cut):
    """在 x+cut 处切割掩码，返回两个子掩码（含各自包围盒）。"""
    if cut < 2 or cut > w - 2:
        return []
    out = []
    for keep_left in (True, False):
        m = mask.copy()
        if keep_left:
            m[:, x + cut:] = 0
        else:
            m[:, :x + cut] = 0
        ys, xs = np.nonzero(m)
        if len(xs) == 0:
            continue
        out.append((m, int(xs.min()), int(ys.min()),
                    int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)))
    return out if len(out) == 2 else []


def _strip_glyphs(img, templates=None):
    bw = _binarize_strip(img)
    h, w = bw.shape
    n, labels, stats, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
    comps = []
    for i in range(1, n):
        x, y, cw, ch, area = stats[i]
        if area < 6 or ch < 5 or cw < 2:
            continue
        if ch > h * 0.7:
            continue
        for piece in _split_touching((labels == i).astype(np.uint8), x, y, cw, ch, templates):
            if piece[3] > w * 0.7:
                continue
            comps.append(piece)
    return comps


def _group_glyphs(comps, axis):
    """把字形按间距聚成数字：axis='x' 横向排列，'y' 纵向堆叠。"""
    if not comps:
        return []
    if axis == "x":
        comps = sorted(comps, key=lambda c: c[1])
        groups = [[comps[0]]]
        for c in comps[1:]:
            prev = groups[-1][-1]
            gap = c[1] - (prev[1] + prev[3])
            # 同一数字内两位之间的间距通常很紧（字距 < 0.35×字高），
            # 不同数字之间间距更宽。用 0.35 而非 0.55 避免把 "4" "10" 合成 "410"。
            if gap > max(c[4], prev[4]) * 0.35:
                groups.append([c])
            else:
                groups[-1].append(c)
    else:
        comps = sorted(comps, key=lambda c: c[2])
        groups = [[comps[0]]]
        for c in comps[1:]:
            prev = groups[-1][-1]
            overlap = min(c[2] + c[4], prev[2] + prev[4]) - max(c[2], prev[2])
            gap = c[2] - (prev[2] + prev[4])
            if overlap <= 0 and gap > max(c[4], prev[4]) * 0.3:
                groups.append([c])
            else:
                groups[-1].append(c)
    return groups


def _numbers_in_cell(cell_img, axis, templates, max_value=None):
    """一小块提示区（一行或一列的一条）里的数字列表。

    max_value：线索最大值（棋盘维度），用于检测并修正粘连分组。
    """
    groups = _group_glyphs(_strip_glyphs(cell_img, templates), axis)
    numbers = []
    for group in groups:
        digits = []
        for comp in sorted(group, key=lambda c: c[1]):
            d, score, margin = _recognize_glyph(comp[0], templates)
            if d is None:
                digits = []
                break
            digits.append(str(d))
        if not digits:
            continue
        value = int("".join(digits))
        # 如果结果超出棋盘维度，尝试在位数边界拆分
        if max_value and value > max_value and len(digits) > 1:
            best = None
            for split_pos in range(1, len(digits)):
                left = int("".join(digits[:split_pos]))
                right = int("".join(digits[split_pos:]))
                if left <= max_value and right <= max_value:
                    best = (left, right)
                    break
            if best:
                numbers.extend(best)
            else:
                numbers.append(value)
        else:
            numbers.append(value)
    return numbers


def _read_clues_by_glyphs(clue_img, axis, board_grid_lines):
    templates = _glyph_templates()
    if not templates:
        return []
    if len(clue_img.shape) == 2:
        clue_img = cv2.cvtColor(clue_img, cv2.COLOR_GRAY2BGR)
    n_cells = len(board_grid_lines) - 1
    offset = board_grid_lines[0]
    h, w = clue_img.shape[:2]
    # 线索最大值 = 棋盘维度，用于检测粘连分组
    max_value = n_cells
    clues = []
    for i in range(n_cells):
        a = max(0, board_grid_lines[i] - offset + 1)
        b = min((h if axis == 1 else w) - 1, board_grid_lines[i + 1] - offset - 1)
        if b - a < 4:
            clues.append([])
            continue
        cell = clue_img[a:b, :] if axis == 1 else clue_img[:, a:b]
        clues.append(_numbers_in_cell(cell, "x" if axis == 1 else "y", templates, max_value=max_value))
    return clues


def read_clue_area(clue_img, axis, board_grid_lines=None):
    """读取提示区数字。

    优先走"字形切割 + 模板匹配"的新实现（能处理粘连数字、不同字体），
    新实现不可用或识别为空时退回旧实现。
    """
    if clue_img is None or clue_img.size == 0:
        return []

    if board_grid_lines is not None and len(board_grid_lines) >= 2:
        try:
            nums = _read_clues_by_glyphs(clue_img, axis, board_grid_lines)
            if any(nums):
                return nums
        except Exception:
            pass

    return _read_clue_area_legacy(clue_img, axis, board_grid_lines)


def _read_clue_area_legacy(clue_img, axis, board_grid_lines=None):
    if len(clue_img.shape) == 3:
        clue_gray = cv2.cvtColor(clue_img, cv2.COLOR_BGR2GRAY)
    else:
        clue_gray = clue_img.copy()

    h, w = clue_gray.shape
    if h < 5 or w < 5:
        return []

    v_sub = detect_sub_lines(clue_gray, axis=0)
    h_sub = detect_sub_lines(clue_gray, axis=1)

    if axis == 1:
        n_cells = len(board_grid_lines) - 1 if board_grid_lines is not None else 0
        y_ranges = []
        if board_grid_lines is not None and n_cells > 0:
            offset_y = board_grid_lines[0]
            for i in range(n_cells):
                y1 = board_grid_lines[i] - offset_y
                y2 = board_grid_lines[i + 1] - offset_y
                y1 = max(0, min(h - 1, y1))
                y2 = max(y1 + 1, min(h, y2))
                y_ranges.append((y1, y2))
        else:
            if len(h_sub) < 2:
                h_sub_full = [0, h]
            else:
                h_sub_full = [0] + h_sub + [h]
            for i in range(len(h_sub_full) - 1):
                y_ranges.append((h_sub_full[i], h_sub_full[i + 1]))
            n_cells = len(y_ranges)

        if len(v_sub) < 2:
            v_sub_full = [0, w]
        else:
            v_sub_full = [0] + v_sub + [w]

        clues = [[] for _ in range(n_cells)]
        for r in range(n_cells):
            y1, y2 = y_ranges[r]
            for c in range(len(v_sub_full) - 1):
                x1, x2 = v_sub_full[c], v_sub_full[c + 1]
                if x2 - x1 < 5 or y2 - y1 < 5:
                    continue
                cell = clue_gray[y1:y2, x1:x2]
                num = recognize_number_cell(cell)
                if num is not None and num > 0:
                    clues[r].append(num)
        return clues
    else:
        n_cells = len(board_grid_lines) - 1 if board_grid_lines is not None else 0
        x_ranges = []
        if board_grid_lines is not None and n_cells > 0:
            offset_x = board_grid_lines[0]
            for i in range(n_cells):
                x1 = board_grid_lines[i] - offset_x
                x2 = board_grid_lines[i + 1] - offset_x
                x1 = max(0, min(w - 1, x1))
                x2 = max(x1 + 1, min(w, x2))
                x_ranges.append((x1, x2))
        else:
            if len(v_sub) < 2:
                v_sub_full = [0, w]
            else:
                v_sub_full = [0] + v_sub + [w]
            for i in range(len(v_sub_full) - 1):
                x_ranges.append((v_sub_full[i], v_sub_full[i + 1]))
            n_cells = len(x_ranges)

        if len(h_sub) < 2:
            h_sub_full = [0, h]
        else:
            h_sub_full = [0] + h_sub + [h]

        col_cells = [[] for _ in range(n_cells)]
        for c in range(n_cells):
            x1, x2 = x_ranges[c]
            row_items = []
            for r in range(len(h_sub_full) - 1):
                y1, y2 = h_sub_full[r], h_sub_full[r + 1]
                if x2 - x1 < 5 or y2 - y1 < 5:
                    continue
                cell = clue_gray[y1:y2, x1:x2]
                num = recognize_number_cell(cell)
                if num is not None and num > 0:
                    row_items.append((r, num))
            row_items.sort(key=lambda x: x[0])
            col_cells[c] = [n for (_, n) in row_items]
        return col_cells


def _extract_numbers_in_strip(strip, vertical=False):
    if strip is None or strip.size == 0:
        return []

    if vertical:
        strip = cv2.rotate(strip, cv2.ROTATE_90_COUNTERCLOCKWISE)

    sh, sw = strip.shape
    if sh < 5 or sw < 5:
        return []

    _, bw = cv2.threshold(strip, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    col_sum = bw.sum(axis=0) / 255
    row_sum = bw.sum(axis=1) / 255

    strong_v_cols = [i for i, v in enumerate(col_sum) if v > sh * 0.8]
    for i in strong_v_cols:
        r = max(1, sh // 10)
        bw[:, max(0, i - r):min(sw, i + r + 1)] = 0

    col_sum_clean = bw.sum(axis=0) / 255
    max_content = col_sum_clean.max() if col_sum_clean.size > 0 else 0
    if max_content == 0:
        return []
    threshold = max(1.0, max_content * 0.08)

    gaps = []
    in_gap = True
    gap_start = 0
    content_start = 0
    segments = []
    min_content_cols = max(2, sh // 10)
    min_gap_cols = max(1, sh // 15)

    for i in range(sw):
        has_content = col_sum_clean[i] > threshold
        if in_gap and has_content:
            gap_end = i
            gap_len = gap_end - gap_start
            if segments and gap_len >= min_gap_cols:
                gaps.append(len(segments) - 1)
            content_start = i
            in_gap = False
        elif not in_gap and not has_content:
            content_end = i
            if content_end - content_start >= min_content_cols:
                segments.append((content_start, content_end))
            in_gap = True
            gap_start = i
    if not in_gap:
        if sw - content_start >= min_content_cols:
            segments.append((content_start, sw))

    if not segments:
        return []

    gap_set = set(gaps)
    merged = []
    for idx, (s, e) in enumerate(segments):
        if merged and (idx - 1) not in gap_set and s - merged[-1][1] <= max(3, sh // 5):
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))

    results = []
    for (s, e) in merged:
        pad_l = max(0, s - 1)
        pad_r = min(sw, e + 1)
        cell = strip[:, pad_l:pad_r]
        if cell.size == 0:
            continue
        num = recognize_number_cell(cell)
        if num is not None and num > 0:
            results.append(num)

    return results


def read_board_cells(img, v_lines, h_lines, vs, ve, hs, he):
    nrows = he - hs
    ncols = ve - vs
    current = []
    for r in range(nrows):
        row_str = ""
        for c in range(ncols):
            x1, x2 = v_lines[vs + c], v_lines[vs + c + 1]
            y1, y2 = h_lines[hs + r], h_lines[hs + r + 1]
            margin_x = max(2, int((x2 - x1) * 0.1))
            margin_y = max(2, int((y2 - y1) * 0.1))
            cx1, cx2 = x1 + margin_x, x2 - margin_x
            cy1, cy2 = y1 + margin_y, y2 - margin_y
            if cx2 <= cx1 or cy2 <= cy1:
                row_str += "."
                continue
            cell = img[cy1:cy2, cx1:cx2]
            if cell.size == 0:
                row_str += "."
                continue
            hsv = cv2.cvtColor(cell, cv2.COLOR_BGR2HSV)
            v = hsv[:, :, 2]
            s = hsv[:, :, 1]
            # 黑格：暗且不饱和（这样即使高亮背景带一点底色也不会误判）
            black_ratio = np.mean((v < 100) & (s < 90))
            # 叉号：饱和的彩色笔迹（红/橙/蓝/绿都算），不再只认红蓝
            mark_ratio = np.mean((s > 120) & (v > 90))
            if black_ratio > 0.30:
                row_str += "O"
            elif mark_ratio > 0.015:
                row_str += "X"
            else:
                row_str += "."
        current.append(row_str)
    return current


def ocr_nonogram(img_path, debug_dir=None):
    img = cv2.imread(img_path)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {img_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    v_lines, h_lines = detect_grid_lines(gray)

    if len(v_lines) < 6 or len(h_lines) < 6:
        raise RuntimeError(f"Failed to detect grid. Found {len(v_lines)} vertical, {len(h_lines)} horizontal lines.")

    vs, ve, hs, he = find_board_region(v_lines, h_lines)
    nrows = he - hs
    ncols = ve - vs

    if debug_dir:
        os.makedirs(debug_dir, exist_ok=True)
        dbg = img.copy()
        for i, x in enumerate(v_lines):
            col = (0, 255, 0) if vs <= i <= ve else (0, 200, 200)
            cv2.line(dbg, (x, 0), (x, gray.shape[0]), col, 2)
        for i, y in enumerate(h_lines):
            col = (0, 0, 255) if hs <= i <= he else (200, 200, 0)
            cv2.line(dbg, (0, y), (gray.shape[1], y), col, 2)
        cv2.rectangle(dbg, (v_lines[vs], h_lines[hs]), (v_lines[ve], h_lines[he]), (255, 0, 0), 4)
        cv2.imwrite(os.path.join(debug_dir, "lines.png"), dbg)

    row_clue_img = img[h_lines[hs]:h_lines[he], 0:v_lines[vs]]
    col_clue_img = img[0:h_lines[hs], v_lines[vs]:v_lines[ve]]

    board_h_grid = h_lines[hs:he + 1]
    board_v_grid = v_lines[vs:ve + 1]

    row_clues = read_clue_area(row_clue_img, axis=1, board_grid_lines=board_h_grid)
    col_clues = read_clue_area(col_clue_img, axis=0, board_grid_lines=board_v_grid)

    while len(row_clues) < nrows:
        row_clues.append([])
    while len(col_clues) < ncols:
        col_clues.append([])
    row_clues = row_clues[:nrows]
    col_clues = col_clues[:ncols]

    current = read_board_cells(img, v_lines, h_lines, vs, ve, hs, he)

    result = {
        "row_clues": row_clues,
        "col_clues": col_clues,
        "current": current,
    }

    if debug_dir:
        with open(os.path.join(debug_dir, "raw_ocr.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def validate_and_fix(data):
    row_clues = data["row_clues"]
    col_clues = data["col_clues"]
    current = data.get("current")
    nrows = len(row_clues)
    ncols = len(col_clues)

    # 只丢掉单个不可能成立的数字（<=0 或整行都放不下），不要因为总和超了就把
    # 整行提示清空——那会把"OCR 读错一个数字"变成"整行没提示"，反而更难修。
    for r in range(nrows):
        row_clues[r] = [c for c in row_clues[r] if 0 < c <= ncols]

    for c in range(ncols):
        col_clues[c] = [cc for cc in col_clues[c] if 0 < cc <= nrows]

    # 行列线索总和必须相等（每个黑格在行和列各计一次）。不等说明 OCR 有误，
    # 打印警告便于调试，但不自动修正——无法确定是哪一行的错。
    row_sum = sum(sum(r) for r in row_clues)
    col_sum = sum(sum(c) for c in col_clues)
    if row_sum != col_sum:
        print(f"[validate_and_fix] 警告：行线索总和({row_sum}) ≠ 列线索总和({col_sum})，"
              f"差值{row_sum - col_sum}，可能存在 OCR 识别错误")

    if current:
        fixed = []
        for r, row in enumerate(current):
            if len(row) < ncols:
                row = row + "." * (ncols - len(row))
            elif len(row) > ncols:
                row = row[:ncols]
            fixed.append("".join("." if ch not in "OX" else ch for ch in row))
        while len(fixed) < nrows:
            fixed.append("." * ncols)
        data["current"] = fixed[:nrows]

    return data


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ocr_nonogram.py <image_path> [output_json] [--debug]")
        sys.exit(1)

    img_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else "puzzle_from_image.json"
    debug_dir = "debug_ocr" if "--debug" in sys.argv else None

    data = ocr_nonogram(img_path, debug_dir=debug_dir)
    data = validate_and_fix(data)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Saved to {out_path}")
    print(f"Board size: {len(data['row_clues'])} rows x {len(data['col_clues'])} cols")
    print("Row clues:", data["row_clues"])
    print("Col clues:", data["col_clues"])
    if data.get("current"):
        print("Current board:")
        for row in data["current"]:
            print(row)
