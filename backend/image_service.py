import base64
import io
import math
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageOps

try:
    import mediapipe as mp
except Exception:  # optional at runtime; quality checks still work without it
    mp = None


@dataclass
class PreparedImage:
    original_data_uri: str
    overview_data_uri: str
    crop_data_uri: str
    enhanced_data_uri: str
    score: float
    issues: list[str]
    hand_side: str
    hand_detected: bool


def _data_uri(image_bytes: bytes, mime: str = "image/jpeg") -> str:
    return f"data:{mime};base64," + base64.b64encode(image_bytes).decode("ascii")


def _encode_bgr(image: np.ndarray, quality: int = 92) -> bytes:
    ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise ValueError("image encoding failed")
    return encoded.tobytes()


def _overview_bgr(image: np.ndarray, max_edge: int = 1800) -> np.ndarray:
    """Create a complete-hand overview without dropping wrist or side edges."""
    height, width = image.shape[:2]
    edge = max(height, width)
    if edge <= max_edge:
        return image
    scale = max_edge / edge
    return cv2.resize(image, (max(1, int(width * scale)), max(1, int(height * scale))), interpolation=cv2.INTER_AREA)


def _quality(gray: np.ndarray, crop_ratio: float) -> tuple[float, list[str]]:
    issues: list[str] = []
    h, w = gray.shape[:2]
    if min(h, w) < 640:
        issues.append("分辨率偏低")
    brightness = float(gray.mean())
    if brightness < 35:
        issues.append("画面过暗")
    if brightness > 225:
        issues.append("画面过曝")
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if sharpness < 35:
        issues.append("掌纹可能模糊")
    if crop_ratio < 0.35:
        issues.append("掌心在画面中占比过小")
    score = 1.0
    score -= 0.18 * len(issues)
    score -= 0.25 if sharpness < 15 else 0
    return max(0.0, min(1.0, score)), issues


def _skin_fallback(bgr: np.ndarray) -> tuple[np.ndarray | None, float]:
    """Conservative fallback for palms where MediaPipe misses cropped fingers."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
    hsv_mask = cv2.inRange(hsv, (0, 20, 40), (35, 220, 255))
    ycrcb_mask = cv2.inRange(ycrcb, (0, 130, 75), (255, 190, 145))
    mask = cv2.morphologyEx(hsv_mask & ycrcb_mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    if count <= 1:
        return None, 0.0
    index = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h, area = stats[index]
    image_area = bgr.shape[0] * bgr.shape[1]
    ratio = float(area / image_area)
    bbox_ratio = float((w * h) / image_area)
    aspect = w / max(h, 1)
    if ratio < 0.22 or bbox_ratio < 0.30 or not 0.12 < aspect < 2.5:
        return None, ratio
    pad_x, pad_y = int(w * 0.08), int(h * 0.08)
    x1, y1 = max(0, x - pad_x), max(0, y - pad_y)
    x2, y2 = min(bgr.shape[1], x + w + pad_x), min(bgr.shape[0], y + h + pad_y)
    return bgr[y1:y2, x1:x2], ratio


def prepare_image(image_bytes: bytes, mime: str) -> PreparedImage:
    raw_source = Image.open(io.BytesIO(image_bytes))
    source_format = raw_source.format
    source = ImageOps.exif_transpose(raw_source)
    if source_format not in {"JPEG", "PNG"}:
        raise ValueError("图片内容不是 JPG、JPEG 或 PNG")
    image = source.convert("RGB")
    if max(image.size) > 4096:
        scale = 4096 / max(image.size)
        image = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))))
    rgb = np.asarray(image)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    crop = bgr
    hand_side = "unknown"
    crop_ratio = 1.0
    hand_detected = False
    used_skin_fallback = False
    if mp is not None:
        try:
            hands = mp.solutions.hands.Hands(static_image_mode=True, max_num_hands=1, min_detection_confidence=0.55)
            result = hands.process(rgb)
            hands.close()
            if result.multi_hand_landmarks:
                hand_detected = True
                points = result.multi_hand_landmarks[0].landmark
                h, w = bgr.shape[:2]
                xs = [p.x * w for p in points]
                ys = [p.y * h for p in points]
                # Keep a generous border so palm edges, wrist and little-finger
                # side lines remain available to the local view.
                pad_x, pad_y = 0.22 * w, 0.22 * h
                x1, x2 = max(0, int(min(xs) - pad_x)), min(w, int(max(xs) + pad_x))
                y1, y2 = max(0, int(min(ys) - pad_y)), min(h, int(max(ys) + pad_y))
                if x2 > x1 and y2 > y1:
                    crop = bgr[y1:y2, x1:x2]
                    crop_ratio = (x2 - x1) * (y2 - y1) / (w * h)
                handedness = result.multi_handedness[0].classification[0].label.lower() if result.multi_handedness else ""
                hand_side = "left" if handedness == "left" else "right" if handedness == "right" else "unknown"
        except Exception:
            pass

    if not hand_detected:
        fallback, skin_ratio = _skin_fallback(bgr)
        if fallback is not None:
            crop = fallback
            crop_ratio = (fallback.shape[0] * fallback.shape[1]) / (bgr.shape[0] * bgr.shape[1])
            hand_detected = True
            used_skin_fallback = True

    crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    score, issues = _quality(crop_gray, crop_ratio)
    if used_skin_fallback:
        issues.append("手部关键点未确认，已使用掌心区域回退检测")
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(crop_gray)
    enhanced_bgr = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
    overview = _overview_bgr(bgr)
    return PreparedImage(
        original_data_uri=_data_uri(image_bytes, mime),
        overview_data_uri=_data_uri(_encode_bgr(overview, quality=86)),
        crop_data_uri=_data_uri(_encode_bgr(crop)),
        enhanced_data_uri=_data_uri(_encode_bgr(enhanced_bgr)),
        score=score,
        issues=issues,
        hand_side=hand_side,
        hand_detected=hand_detected,
    )
