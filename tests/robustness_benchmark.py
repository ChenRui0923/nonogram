"""Optional real-image robustness matrix; outputs stay outside the checkout.

Run: python -B tests/robustness_benchmark.py [output-directory]
This is intentionally separate from the fast unit-test suite.
"""
import json
import signal
from pathlib import Path
import sys
import tempfile
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nonogram import ocr_nonogram as ocr
from nonogram.result_cache import ResultCache
from nonogram.visual_puzzle_cache import VisualPuzzleCache


def transformed_images(image):
    height, width = image.shape[:2]
    yield 'original', image
    for factor in (.5, .75, 1.25, 1.5):
        yield f'scale-{factor}', cv2.resize(image, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA if factor < 1 else cv2.INTER_CUBIC)
    yield 'anisotropic-0.85x1.1', cv2.resize(image, (int(width*.85), int(height*1.1)))
    yield 'white-padding', cv2.copyMakeBorder(image, 40, 60, 70, 30, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    yield 'trim-2px', image[2:-2, 2:-2].copy()
    yield 'cut-off-clues', image[80:, 100:].copy()
    for quality in (95, 80):
        encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, quality])[1]
        yield f'jpeg-{quality}', cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    for sigma in (.45, .8, 1.2):
        yield f'blur-{sigma}', cv2.GaussianBlur(image, (0, 0), sigma)
    yield 'brightness', cv2.convertScaleAbs(image, alpha=.85, beta=20)
    for degrees in (.5, 2):
        matrix = cv2.getRotationMatrix2D((width/2, height/2), degrees, 1)
        matrix[:, 2] += 40
        yield f'rotation-{degrees}', cv2.warpAffine(image, matrix, (width+80, height+80), borderValue=(255, 255, 255))
    source = np.float32([[0, 0], [width-1, 0], [width-1, height-1], [0, height-1]])
    for shift in (20, 60):
        target = np.float32([[shift, 10], [width+10, shift], [width+20, height+15], [10, height+shift]])
        matrix = cv2.getPerspectiveTransform(source, target)
        yield f'perspective-{shift}', cv2.warpPerspective(image, matrix, (width+100, height+100), borderValue=(255, 255, 255))


def cell_differences(actual, expected):
    if len(actual) != len(expected) or any(len(a) != len(b) for a, b in zip(actual, expected)):
        return 'dimension-mismatch'
    return sum(x != y for a, b in zip(actual, expected) for x, y in zip(a, b))


def main():
    output = Path(sys.argv[1] if len(sys.argv) > 1 else '/tmp/nonogram-robustness')
    output.mkdir(parents=True, exist_ok=True)
    report = output / 'results.json'
    results = json.loads(report.read_text()) if report.exists() else []
    done = {(r['pair'], r['case']) for r in results}
    def timeout(signum, frame):
        raise TimeoutError('Per-case OCR limit of 10 seconds exceeded')
    if hasattr(signal, 'SIGALRM'):
        signal.signal(signal.SIGALRM, timeout)
    for reference_name, target_name in [('debug.png', 'debug2.png'), ('progress-30x25.png', 'progress-30x25-later.png')]:
        baseline = ocr.ocr_nonogram(str(ROOT / "examples/images" / target_name))
        with tempfile.TemporaryDirectory() as folder:
            store = ResultCache(Path(folder) / 'references.db', max_entries=4)
            visual = VisualPuzzleCache(store)
            ocr.ocr_nonogram(str(ROOT / "examples/images" / reference_name), visual_cache=visual)
            reference = visual.entries[0]
            image = cv2.imread(str(ROOT / "examples/images" / target_name))
            for name, changed in transformed_images(image):
                if (reference_name + ' -> ' + target_name, name) in done:
                    continue
                cv2.setRNGSeed(42)
                # Every case starts with the same known-good reference only.
                visual = VisualPuzzleCache(store)
                visual.entries = [reference]
                path = output / f'{Path(target_name).stem}-{name}.png'
                cv2.imwrite(str(path), changed)
                started = time.perf_counter()
                item = {'pair': reference_name + ' -> ' + target_name, 'case': name}
                try:
                    if hasattr(signal, 'alarm'):
                        signal.alarm(10)
                    result = ocr.ocr_nonogram(str(path), clue_cache=ResultCache(Path(folder)/'clues.db'), visual_cache=visual)
                    item.update(reused=result['auto_puzzle_match'], similarity=result['puzzle_similarity'],
                                clue_hits=result['clue_cache_hits'],
                                clues_correct=(result['row_clues'] == baseline['row_clues'] and result['col_clues'] == baseline['col_clues']),
                                cell_differences=cell_differences(result['current'], baseline['current']))
                except Exception as exc:
                    item['error'] = type(exc).__name__ + ': ' + str(exc)
                if hasattr(signal, 'alarm'):
                    signal.alarm(0)
                item['seconds'] = round(time.perf_counter() - started, 4)
                results.append(item)
                print(json.dumps(item, ensure_ascii=False), flush=True)
                (output/'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
            # Genuine other screenshots: no same-puzzle reuse is permitted.
            for other in ['progress-30x25.png', 'debug.png', 'unsupported-mobile.jpg']:
                if other == reference_name:
                    continue
                visual = VisualPuzzleCache(store)
                visual.entries = [reference]
                started = time.perf_counter()
                _, match = visual.align(cv2.imread(str(ROOT / "examples/images" / other)))
                item = {'pair': reference_name + ' -> other', 'case': other, 'negative': True,
                        'reused': match is not None, 'seconds': round(time.perf_counter()-started, 4)}
                results.append(item)
                print(json.dumps(item, ensure_ascii=False), flush=True)
                (output/'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
