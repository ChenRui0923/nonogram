"""Register screenshots using clue features, then verify each clue independently."""
import base64
import threading

import cv2
import numpy as np


class VisualPuzzleCache:
    def __init__(self, store, minimum_similarity=0.995):
        self.store = store
        self.minimum_similarity = minimum_similarity
        self.entries = None
        self.lock = threading.RLock()
        self.orb = cv2.ORB_create(nfeatures=2500)

    def _features(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        scale = min(1.0, 1200 / max(gray.shape))
        small = cv2.resize(gray, None, fx=scale, fy=scale)
        points, descriptors = self.orb.detectAndCompute(small, None)
        coords = np.float32([p.pt for p in points]).reshape(-1, 2) / scale
        return coords, descriptors

    def _load(self):
        if self.entries is None:
            self.entries = []
            for record in self.store.recent_values():
                try:
                    if record.get('cache_version') != self.store.version:
                        continue
                    image = cv2.imdecode(np.frombuffer(base64.b64decode(record['image']), np.uint8), cv2.IMREAD_COLOR)
                    if image is not None:
                        record['pixels'] = image
                        record['features'] = self._features(image)
                        self.entries.append(record)
                except (ValueError, KeyError, cv2.error):
                    continue

    def align(self, image):
        with self.lock:
            self._load()
            if not self.entries:
                return image, None
            points, desc = self._features(image)
            if desc is None:
                return image, None
            for record in self.entries:
                refpoints, refdesc = record['features']
                if refdesc is None:
                    continue
                pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(desc, refdesc, k=2)
                good = [a for pair in pairs if len(pair) == 2 for a, b in [pair] if a.distance < 0.7 * b.distance]
                if len(good) < 30:
                    continue
                src = np.float32([points[m.queryIdx] for m in good])
                dst = np.float32([refpoints[m.trainIdx] for m in good])
                homography, inliers = cv2.findHomography(src, dst, cv2.RANSAC, 2.0)
                if homography is None or inliers is None or inliers.sum() < 25 or inliers.mean() < 0.4:
                    continue
                reference = record['pixels']
                height, width = reference.shape[:2]
                selected = dst[inliers.ravel() > 0]
                if cv2.contourArea(cv2.convexHull(selected)) < width * height * 0.1:
                    continue
                # Reject extreme/projectively unstable mappings and cropped clue areas.
                corners = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
                try:
                    inverse = np.linalg.inv(homography)
                except np.linalg.LinAlgError:
                    continue
                mapped = cv2.perspectiveTransform(corners[None], inverse)[0]
                if not np.isfinite(mapped).all() or not cv2.isContourConvex(mapped.astype(np.float32)):
                    continue
                area_ratio = cv2.contourArea(mapped) / (image.shape[0] * image.shape[1])
                if not 0.35 < area_ratio < 1.5:
                    continue
                aligned = cv2.warpPerspective(image, homography, (width, height), borderValue=(255, 255, 255))
                # Symmetric foreground coverage after registration. Background
                # pixels do not contribute, so blank margins cannot inflate it.
                from ocr_nonogram import _ink_mask
                clue_pixels = aligned.copy()
                clue_pixels[record['h'][0]:, record['v'][0]:] = 255
                old = _ink_mask(reference) > 0
                new = _ink_mask(clue_pixels) > 0
                kernel = np.ones((3, 3), np.uint8)
                old_near = cv2.dilate(old.astype(np.uint8), kernel) > 0
                new_near = cv2.dilate(new.astype(np.uint8), kernel) > 0
                similarity = min(np.count_nonzero(old & new_near) / max(1, np.count_nonzero(old)),
                                 np.count_nonzero(new & old_near) / max(1, np.count_nonzero(new)))
                if similarity < self.minimum_similarity:
                    continue
                # A homography is only a candidate. Every reused line must pass
                # its own glyph comparison; changed/ambiguous lines still run OCR.
                row_values, col_values = self._verified_lines(reference, aligned, record)
                matched = sum(x is not None for x in row_values + col_values)
                if matched < 0.3 * (len(row_values) + len(col_values)):
                    continue
                # Verify the expected grid itself before using reference geometry.
                v, h = record['v'], record['h']
                dark = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY) < 180
                vertical = [dark[h[0]:h[-1], max(0, x-2):x+3].any(axis=1).mean() for x in v]
                horizontal = [dark[max(0, y-2):y+3, v[0]:v[-1]].any(axis=0).mean() for y in h]
                if min(vertical + horizontal) < 0.8:
                    continue
                scale = np.diag([2., 2., 1.])
                rectified = cv2.warpPerspective(image, scale @ homography,
                                                (width * 2, height * 2),
                                                borderValue=(255, 255, 255))
                return rectified, {**record, 'reuse_rows': row_values, 'reuse_cols': col_values, 'similarity': float(similarity)}
            return image, None

    @staticmethod
    def _same_strip(a, b, clue):
        from ocr_nonogram import _ink_mask, _normalize_glyph, _glyph_score, _count_holes, _glyph_templates
        def components(image):
            bw = _ink_mask(image)
            n, labels, stats, _ = cv2.connectedComponentsWithStats(bw)
            items = []
            for i in range(1, n):
                x, y, w, h, area = stats[i]
                if area < 6:
                    continue
                # Full-length border segments are not digit strokes.
                if w >= bw.shape[1] * 0.9 or h >= bw.shape[0] * 0.95:
                    continue
                mask = (labels[y:y+h, x:x+w] == i).astype(np.uint8)
                items.append((x, y, w, h, mask))
            return sorted(items, key=lambda c: (round(c[1] / 4), c[0]))
        left, right = components(a), components(b)
        digits = [int(d) for n in clue for d in str(n)]
        if not left or len(left) != len(right) or len(left) != len(digits):
            return False
        # Sort by reading order, matching spatial positions too (including gaps).
        horizontal = a.shape[1] > a.shape[0]
        left.sort(key=lambda c: c[0] if horizontal else (c[1], c[0]))
        right.sort(key=lambda c: c[0] if horizontal else (c[1], c[0]))
        templates = _glyph_templates()
        for x, y, expected in zip(left, right, digits):
            if abs(x[0]-y[0]) > 2 or abs(x[1]-y[1]) > 2:
                return False
            if not 0.8 < (y[2]*y[3]) / (x[2]*x[3]) < 1.25:
                return False
            if _count_holes(x[4]) != _count_holes(y[4]):
                return False
            m, n = _normalize_glyph(x[4]), _normalize_glyph(y[4])
            if m is None or n is None:
                return False
            dm = cv2.distanceTransform(1-m, cv2.DIST_L2, 3)
            dn = cv2.distanceTransform(1-n, cv2.DIST_L2, 3)
            distance = _glyph_score(m, dm, n, dn)
            if distance > 0.24:
                return False
            # A visually similar different digit must not inherit the old clue.
            # Compare to competing digit templates without the costly shift search;
            # ambiguous cases go through the normal OCR pipeline instead.
            yy, xx = np.nonzero(n)
            alternative = min((float(dt[yy, xx].mean()) + float(dn[tpl > 0].mean())) / 2
                              for key, (tpl, dt) in templates.items() if key[1] != expected)
            if alternative <= distance + 0.1:
                return False
        return True

    def _verified_lines(self, reference, image, record):
        v, h = record['v'], record['h']
        rows, cols = [], []
        for r, clue in enumerate(record['row_clues']):
            region = (slice(h[r]+3, h[r+1]-3), slice(3, v[0]-3))
            rows.append(clue if self._same_strip(reference[region], image[region], clue) else None)
        for c, clue in enumerate(record['col_clues']):
            region = (slice(3, h[0]-3), slice(v[c]+3, v[c+1]-3))
            cols.append(clue if self._same_strip(reference[region], image[region], clue) else None)
        return rows, cols

    def remember(self, image, v, h, rows, cols):
        with self.lock:
            self._load()
            masked = image.copy()
            masked[h[0]:, v[0]:] = 255  # Never retain the player's filled board.
            png = cv2.imencode('.png', masked)[1].tobytes()
            record = {'cache_version': self.store.version, 'image': base64.b64encode(png).decode(), 'v': list(map(int, v)),
                      'h': list(map(int, h)), 'row_clues': rows, 'col_clues': cols}
            self.store.get_or_compute(png, lambda: record)
            # Keep at most four references; replacement is cheap and bounded.
            record['pixels'] = masked
            record['features'] = self._features(masked)
            self.entries.insert(0, record)
            self.entries = self.entries[:4]
