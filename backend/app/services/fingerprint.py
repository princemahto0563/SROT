"""
Perceptual fingerprinting.

A copy that has been re-encoded, downscaled, cropped, watermarked, screen-recorded
or letterboxed is still the same content. A perceptual hash of the *whole frame*,
however, also encodes the canvas — black padding bars and burned-in interface
bands shift the DCT and push genuine derivatives towards the noise floor.

We therefore hash each frame under several normalised VIEWS and match on the best
view pair, recording which normalisation produced the match so the report can state
it. Nothing here is heuristic hand-waving: the threshold below was measured.

── Threshold calibration (measured, reproducible: backend/calibrate.py) ─────────
Distance alone is not enough. Taking the minimum over 4 views x 8 frames x 4 views x
8 frames is a minimum over ~1000 comparisons, and a degenerate control (SMPTE colour
bars) occasionally produces one lucky frame pair at 14 bits — close enough to be
mistaken for a real derivative.

So a match requires BOTH conditions:

    1. minimum multi-view Hamming distance <= MATCH_THRESHOLD          (12 bits)
    2. at least MIN_CORROBORATING_FRAMES query frames independently
       match some candidate frame within that distance                 (2 frames)

Measured on 8 sampled frames per clip, 64-bit pHash:

                                      min distance   corroborating frames
    true derivatives      (n=5)         8 - 10 bits           4 - 5 of 8
    unrelated controls    (n=9)        14 - 32 bits           0 of 8

Corroboration is what actually separates the two populations: every control scores
zero corroborating frames, while every true derivative scores at least four. A
result failing either condition is reported as "no match in searched corpus" —
never as a weak match.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Iterable

import cv2
import imagehash
import numpy as np
from PIL import Image

HASH_BITS = 64
MATCH_THRESHOLD = 12            # bits; measured, see the calibration note above
MIN_CORROBORATING_FRAMES = 2    # a single lucky frame pair is not a match
STRONG_MATCH_BITS = MATCH_THRESHOLD

CALIBRATION = {
    "method": "minimum multi-view 64-bit pHash Hamming distance, corroborated across "
              "independently matching frames",
    "threshold_bits": MATCH_THRESHOLD,
    "min_corroborating_frames": MIN_CORROBORATING_FRAMES,
    "true_derivative_distance_bits": [8, 10],
    "true_derivative_corroborating_frames": [4, 5],
    "unrelated_control_distance_bits": [14, 32],
    "unrelated_control_corroborating_frames": [0, 0],
    "samples": {"true_derivatives": 5, "unrelated_controls": 9, "frames_per_clip": 8},
    "note": "Calibrated on synthetic demonstration media only. Distance alone does not "
            "separate the populations — one degenerate control reaches 14 bits on a "
            "single frame pair but corroborates on none. Re-calibration is required "
            "before use on operational material.",
}


def qualifies(match: dict) -> bool:
    """Both conditions must hold. Used everywhere a match is accepted."""
    return (match.get("hamming", HASH_BITS) <= MATCH_THRESHOLD
            and match.get("matched_frames", 0) >= MIN_CORROBORATING_FRAMES)


# ── frame views ──────────────────────────────────────────────────────────────
def _gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img


def trim_border_bars(img: np.ndarray) -> np.ndarray:
    """
    Remove genuinely black padding bars (letterbox / pillarbox) from the frame edges.

    Strict on purpose: a row is a bar only if it is dark *and* has no bright pixels.
    A dark but detailed row is content, and trimming it would corrupt the hash.
    """
    g = _gray(img)
    h, w = g.shape
    row_dark = (g.mean(axis=1) < 26) & (np.percentile(g, 98, axis=1) < 90)
    col_dark = (g.mean(axis=0) < 26) & (np.percentile(g, 98, axis=0) < 90)

    y0 = 0
    while y0 < h and row_dark[y0]:
        y0 += 1
    y1 = h
    while y1 > y0 and row_dark[y1 - 1]:
        y1 -= 1
    x0 = 0
    while x0 < w and col_dark[x0]:
        x0 += 1
    x1 = w
    while x1 > x0 and col_dark[x1 - 1]:
        x1 -= 1

    if (y1 - y0) < h * 0.4 or (x1 - x0) < w * 0.4:
        return img                                    # refuse an implausible crop
    return img[y0:y1, x0:x1]


def center_crop(img: np.ndarray, frac: float = 0.80) -> np.ndarray:
    """Discard the outer border — survives added banners, overlays and re-framing."""
    h, w = img.shape[:2]
    dy, dx = int(h * (1 - frac) / 2), int(w * (1 - frac) / 2)
    if h - 2 * dy < 16 or w - 2 * dx < 16:
        return img
    return img[dy:h - dy, dx:w - dx]


VIEWS: dict[str, Any] = {
    "full":     lambda i: i,
    "trim":     trim_border_bars,
    "c80":      center_crop,
    "trim_c80": lambda i: center_crop(trim_border_bars(i)),
}
VIEW_LABEL = {
    "full": "whole frame",
    "trim": "border bars removed",
    "c80": "central 80% of frame",
    "trim_c80": "border bars removed, then central 80%",
}


def view_hash_type(view: str) -> str:
    """Storage key. 'full' keeps the plain name so existing rows stay meaningful."""
    return "phash" if view == "full" else f"phash:{view}"


def view_of_hash_type(hash_type: str) -> str | None:
    if hash_type == "phash":
        return "full"
    if hash_type.startswith("phash:"):
        v = hash_type.split(":", 1)[1]
        return v if v in VIEWS else None
    return None


# ── hashing ──────────────────────────────────────────────────────────────────
def _pil(img: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


def hash_image(path: str | Path) -> dict[str, Any]:
    """
    Returns the three whole-frame hashes (phash/dhash/whash, used for display and
    for exact-copy checks) plus a pHash per normalised view, used for matching.
    """
    raw = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if raw is None:
        with Image.open(path) as im:
            pil = im.convert("RGB").copy()
        base = {"phash": str(imagehash.phash(pil)), "dhash": str(imagehash.dhash(pil)),
                "whash": str(imagehash.whash(pil))}
        return {**base, "views": {"full": base["phash"]}}

    pil_full = _pil(raw)
    views: dict[str, str] = {}
    for name, fn in VIEWS.items():
        try:
            views[name] = str(imagehash.phash(_pil(fn(raw))))
        except Exception:  # noqa: BLE001
            continue
    return {
        "phash": views.get("full", str(imagehash.phash(pil_full))),
        "dhash": str(imagehash.dhash(pil_full)),
        "whash": str(imagehash.whash(pil_full)),
        "views": views,
    }


def hash_frames(frame_paths: list[str]) -> list[dict[str, Any]]:
    out = []
    for i, p in enumerate(frame_paths):
        try:
            out.append({"frame_index": i, **hash_image(p)})
        except Exception:  # noqa: BLE001
            continue
    return out


# ── comparison ───────────────────────────────────────────────────────────────
def hamming(a: str, b: str) -> int:
    """Cast to a Python int — imagehash returns a NumPy scalar."""
    return int(imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b))


def similarity(a: str, b: str, bits: int = HASH_BITS) -> float:
    """Percentage similarity derived from Hamming distance. Computed, never assumed."""
    return float(round((1.0 - hamming(a, b) / bits) * 100.0, 2))


def sim_from_hamming(ham: int, bits: int = HASH_BITS) -> float:
    return float(round((1.0 - ham / bits) * 100.0, 2))


def best_match(query_hashes: list[str], candidate_hashes: list[str]) -> tuple[int, float, int]:
    """Single-view comparison of two flat hash lists. (min_hamming, similarity, matched)."""
    if not query_hashes or not candidate_hashes:
        return (int(HASH_BITS), 0.0, 0)
    best, matched = HASH_BITS, 0
    for q in query_hashes:
        local = min(hamming(q, c) for c in candidate_hashes)
        best = min(best, local)
        if local <= STRONG_MATCH_BITS:
            matched += 1
    return int(best), sim_from_hamming(best), int(matched)


def group_view_rows(rows: Iterable[Any]) -> list[dict[str, str]]:
    """
    Turn Fingerprint / FingerprintLedger rows into one {view: hash} dict per frame.
    Rows whose hash_type is not a pHash view are ignored.
    """
    by_frame: dict[Any, dict[str, str]] = {}
    for r in rows:
        view = view_of_hash_type(getattr(r, "hash_type", "") or "")
        if not view:
            continue
        hx = getattr(r, "hash_hex", None) or getattr(r, "perceptual_hash", None)
        if not hx:
            continue
        key = getattr(r, "frame_index", None)
        if key is None:
            key = f"{getattr(r, 'id', id(r))}"
        by_frame.setdefault(key, {})[view] = hx
    return [v for _, v in sorted(by_frame.items(), key=lambda kv: str(kv[0]))]


def frame_views(frame_hashes: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Extract the per-frame view maps from hash_frames() output."""
    return [f.get("views") or ({"full": f["phash"]} if f.get("phash") else {})
            for f in frame_hashes]


def best_match_views(query: list[dict[str, str]],
                     candidate: list[dict[str, str]]) -> dict[str, Any]:
    """
    Compare two sets of per-frame view maps across every view pair.

    Returns the minimum Hamming distance found, the view pair that produced it, and
    how many query frames matched some candidate frame within STRONG_MATCH_BITS.
    """
    if not query or not candidate:
        return {"hamming": int(HASH_BITS), "similarity": 0.0, "matched_frames": 0,
                "query_view": None, "candidate_view": None, "normalisation": None,
                "total_frames": len(query)}

    best = HASH_BITS
    best_pair: tuple[str, str] | None = None
    matched = 0
    for q in query:
        local = HASH_BITS
        for qv, qh in q.items():
            for c in candidate:
                for cv, ch in c.items():
                    d = hamming(qh, ch)
                    if d < local:
                        local = d
                    if d < best:
                        best, best_pair = d, (qv, cv)
        if local <= STRONG_MATCH_BITS:
            matched += 1

    norm = None
    if best_pair:
        qv, cv = best_pair
        norm = (f"query: {VIEW_LABEL.get(qv, qv)}; reference: {VIEW_LABEL.get(cv, cv)}")
    return {"hamming": int(best), "similarity": sim_from_hamming(best),
            "matched_frames": int(matched), "query_view": best_pair[0] if best_pair else None,
            "candidate_view": best_pair[1] if best_pair else None,
            "normalisation": norm, "total_frames": len(query)}
