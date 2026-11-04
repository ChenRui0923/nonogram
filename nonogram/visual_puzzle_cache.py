"""Match puzzle identity using aligned clue imagery and verified grid geometry."""
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

    def _features(self, image, feature_budget=2500):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        scale = min(1.0, 1200 / max(gray.shape))
        small = cv2.resize(gray, None, fx=scale, fy=scale)
        detector = self.orb if feature_budget == 2500 else cv2.ORB_create(nfeatures=feature_budget)
        points, descriptors = detector.detectAndCompute(small, None)
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
            # Escalate feature density only after cheaper registration fails.
            for budget in (2500, 5000, 8000):
                aligned, match = self._align_once(image, budget)
                if match is not None:
                    return aligned, match
            return image, None

    def _align_once(self, image, feature_budget):
        with self.lock:
            self._load()
            if not self.entries:
                return image, None
            points, desc = self._features(image, feature_budget)
            if desc is None:
                return image, None
            for record in self.entries:
                if feature_budget == 2500:
                    refpoints, refdesc = record['features']
                else:
                    extra = record.setdefault('extra_features', {})
                    if feature_budget not in extra:
                        extra[feature_budget] = self._features(record['pixels'], feature_budget)
                    refpoints, refdesc = extra[feature_budget]
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
                from nonogram.ocr_nonogram import _ink_mask
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
                return rectified, {**record, 'reuse_rows': record['row_clues'], 'reuse_cols': record['col_clues'], 'similarity': float(similarity)}
            return image, None

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
