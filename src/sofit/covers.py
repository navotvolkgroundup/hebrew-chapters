"""Pick a good still for a clip cover.

The obvious approach - grab the frame a third of the way in - keeps landing on
blinks and downward glances, which look terrible as a cover in the profile
grid. This scores candidate frames instead and returns the best timestamp.

Score = eye contrast (an open eye shows a dark pupil against sclera, a closed
one is near-uniform skin) x face size x frame sharpness. No eye-state model
needed, and the YuNet detector sofit already ships gives the eye landmarks.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

_FACE_MODEL = Path(__file__).parent / "data" / "face_detection_yunet_2023mar.onnx"


def _grab(video: Path, t: float, out: Path) -> bool:
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t}",
           "-i", str(video), "-frames:v", "1", "-y", str(out)]
    return subprocess.run(cmd, capture_output=True).returncode == 0


def score_frame(img_path: Path) -> tuple[float, dict]:
    """Score one still: (score, details). 0.0 when no usable face is found."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return 0.0, {"reason": "no-opencv"}
    if not _FACE_MODEL.exists():
        return 0.0, {"reason": "no-model"}

    img = cv2.imread(str(img_path))
    if img is None:
        return 0.0, {"reason": "unreadable"}
    h, w = img.shape[:2]
    det = cv2.FaceDetectorYN.create(str(_FACE_MODEL), "", (w, h),
                                    score_threshold=0.6)
    det.setInputSize((w, h))
    _, faces = det.detect(img)
    if faces is None or not len(faces):
        return 0.0, {"reason": "no-face"}

    face = max(faces, key=lambda f: f[2] * f[3])
    fx, fy, fw, fh = face[:4]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # YuNet landmarks: right eye, left eye, nose, right mouth, left mouth.
    eyes = [(face[4], face[5]), (face[6], face[7])]
    r = max(4, int(fw * 0.09))          # eye patch radius, scales with the face
    contrasts = []
    for ex, ey in eyes:
        x0, x1 = int(max(0, ex - r)), int(min(w, ex + r))
        y0, y1 = int(max(0, ey - r)), int(min(h, ey + r))
        patch = gray[y0:y1, x0:x1]
        if patch.size:
            contrasts.append(float(patch.std()))
    if not contrasts:
        return 0.0, {"reason": "no-eye-patch"}

    eye_contrast = min(contrasts)        # the WORSE eye decides - one shut eye is enough to reject
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    face_frac = float(fw * fh) / float(w * h)

    score = eye_contrast * (face_frac ** 0.25) * min(sharpness, 400.0) ** 0.25
    return score, {"eye_contrast": round(eye_contrast, 1),
                   "sharpness": round(sharpness, 1),
                   "face_frac": round(face_frac, 4)}


def _signature(img_path: Path):
    """Coarse colour signature of a still, for telling one shot from another."""
    try:
        import cv2
    except ImportError:
        return None
    img = cv2.imread(str(img_path))
    if img is None:
        return None
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [24, 24], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    return hist


def _sig_similarity(a, b) -> float:
    if a is None or b is None:
        return 1.0
    try:
        import cv2
        return max(0.0, float(cv2.compareHist(a, b, cv2.HISTCMP_CORREL)))
    except Exception:  # noqa: BLE001
        return 1.0


def best_frame(video: Path, start: float, end: float, step: float = 0.5,
               max_samples: int = 40, ref: Path | None = None,
               ref_weight: float = 2.0) -> tuple[float, float, dict]:
    """Sample [start, end] and return (timestamp, score, details) of the best.

    Falls back to the midpoint with score 0 when nothing scores (no OpenCV, no
    face, an audio-only source) so callers always get a usable timestamp.
    """
    span = max(0.0, end - start)
    n = min(max_samples, max(1, int(span / step)))
    times = [start + span * (i + 0.5) / n for i in range(n)]
    best = (start + span / 2, 0.0, {"reason": "no-candidate"})
    ref_sig = _signature(ref) if ref else None
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "f.png"
        for t in times:
            if not _grab(video, t, tmp):
                continue
            s, info = score_frame(tmp)
            if s <= 0:
                continue
            if ref_sig is not None:
                # Multi-camera shows cut to reaction shots, and a wide-eyed
                # reaction from the OTHER host outscores the speaker every
                # time. Weight by how much the frame looks like the reference
                # shot so the cover shows whoever owns the clip.
                sim = _sig_similarity(ref_sig, _signature(tmp))
                info = dict(info, shot_similarity=round(sim, 3))
                s *= sim ** ref_weight
            if s > best[1]:
                best = (t, s, info)
    return best
