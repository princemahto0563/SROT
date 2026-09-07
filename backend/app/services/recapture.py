"""
Recapture forensics — the answer to "metadata hata diya to?".

Stripping metadata changes the bytes, not the pixels. When a video is forwarded by
screen-recording, the source application's interface is recorded INTO the frames:
letterbox bars, a status bar that never changes, UI chrome, and often the original
poster's handle. All of the checks below are real measurements on the frames.

We never invent a recovered handle. If nothing is read, we say nothing was read.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from . import ocr as ocr_svc

UI_TEXT_HINTS = ("forwarded", "views", "subscribe", "share", "reply", "story",
                 "live", "followers", "whatsapp", "telegram", "instagram",
                 "youtube", "shorts", "reels", "facebook", "twitter", "x.com")


def _load(path: str) -> np.ndarray | None:
    return cv2.imread(str(path), cv2.IMREAD_COLOR)


def detect_letterbox(frame_paths: list[str]) -> dict[str, Any]:
    """Uniform border rows/columns across frames → the media was placed inside a
    differently-shaped canvas (classic screen-record / re-frame artefact)."""
    tops = bots = lefts = rights = []
    tops, bots, lefts, rights = [], [], [], []
    h = w = 0
    for p in frame_paths[:8]:
        img = _load(p)
        if img is None:
            continue
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = g.shape
        row_std = g.std(axis=1)
        col_std = g.std(axis=0)
        thr = 3.0
        t = int(np.argmax(row_std > thr)) if (row_std > thr).any() else 0
        b = int(np.argmax(row_std[::-1] > thr)) if (row_std > thr).any() else 0
        l = int(np.argmax(col_std > thr)) if (col_std > thr).any() else 0
        r = int(np.argmax(col_std[::-1] > thr)) if (col_std > thr).any() else 0
        tops.append(t); bots.append(b); lefts.append(l); rights.append(r)

    if not tops or h == 0:
        return {"detected": False, "reason": "no readable frames"}
    top, bot = int(np.median(tops)), int(np.median(bots))
    left, right = int(np.median(lefts)), int(np.median(rights))
    v_frac = (top + bot) / max(1, h)
    h_frac = (left + right) / max(1, w)
    detected = v_frac > 0.02 or h_frac > 0.02
    return {"detected": bool(detected),
            "top_px": top, "bottom_px": bot, "left_px": left, "right_px": right,
            "vertical_fraction": round(v_frac, 4), "horizontal_fraction": round(h_frac, 4),
            "frame_size": [w, h],
            "kind": ("letterbox (horizontal bars)" if v_frac > h_frac else
                     "pillarbox (vertical bars)") if detected else "none"}


def detect_static_bands(frame_paths: list[str]) -> dict[str, Any]:
    """
    Rows whose pixel values barely change across the whole clip. A phone status bar
    or a persistent app header behaves exactly like this, while real video content
    does not.
    """
    stack = []
    for p in frame_paths[:12]:
        img = _load(p)
        if img is None:
            continue
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
        if stack and g.shape != stack[0].shape:
            g = cv2.resize(g, (stack[0].shape[1], stack[0].shape[0]))
        stack.append(g)
    if len(stack) < 3:
        return {"detected": False, "reason": "insufficient frames"}

    arr = np.stack(stack)                       # (n, h, w)
    row_temporal_std = arr.std(axis=0).mean(axis=1)   # per-row variation over time
    overall = float(row_temporal_std.mean()) + 1e-6
    h = arr.shape[1]
    static = row_temporal_std < (0.25 * overall)

    def _band(rows: np.ndarray) -> int:
        c = 0
        for v in rows:
            if v:
                c += 1
            else:
                break
        return c

    top_band = _band(static[:int(h * 0.25)])
    bottom_band = _band(static[::-1][:int(h * 0.25)])
    return {"detected": bool(top_band >= max(4, h * 0.02) or bottom_band >= max(4, h * 0.02)),
            "top_static_rows": int(top_band), "bottom_static_rows": int(bottom_band),
            "frame_height": int(h),
            "mean_row_temporal_std": round(overall, 4),
            "top_band_fraction": round(top_band / h, 4),
            "bottom_band_fraction": round(bottom_band / h, 4),
            "method": "per-row standard deviation across sampled frames"}


def detect_rescale_moire(frame_paths: list[str]) -> dict[str, Any]:
    """
    Screen re-capture and integer rescaling leave periodic peaks in the frequency
    domain. We measure how much energy sits in narrow off-centre peaks.
    """
    scores = []
    detail = {}
    for p in frame_paths[:6]:
        img = _load(p)
        if img is None:
            continue
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
        g = g - g.mean()
        f = np.fft.fftshift(np.abs(np.fft.fft2(g)))
        hh, ww = f.shape
        cy, cx = hh // 2, ww // 2
        f[cy - 3:cy + 4, cx - 3:cx + 4] = 0          # kill DC
        med = float(np.median(f)) + 1e-9
        peaks = f > (med * 40)
        peak_frac = float(peaks.sum()) / peaks.size
        scores.append(peak_frac)
        if not detail:
            detail = {"median_magnitude": round(med, 3),
                      "peak_threshold": round(med * 40, 3)}
    if not scores:
        return {"detected": False, "reason": "no readable frames"}
    mean_peak = float(np.mean(scores))
    return {"detected": bool(mean_peak > 4e-4),
            "peak_energy_fraction": round(mean_peak, 8),
            **detail,
            "method": "2-D FFT narrow-peak fraction (moiré / rescale periodicity)"}


def ocr_ui_regions(frame_paths: list[str], static: dict, letterbox: dict) -> dict[str, Any]:
    """
    OCR only the regions that plausibly contain interface chrome, then report what
    was actually read. Handles are reported ONLY if OCR produced them.
    """
    regions_scanned: list[dict] = []
    recovered: list[dict] = []
    ui_hits: list[dict] = []

    for fi, p in enumerate(frame_paths[:8]):
        img = _load(p)
        if img is None:
            continue
        h, w = img.shape[:2]
        candidates: list[tuple[str, tuple[int, int, int, int]]] = [
            ("top-band", (0, 0, w, max(24, int(h * 0.16)))),
            ("bottom-band", (0, int(h * 0.80), w, h - int(h * 0.80))),
        ]
        tb = int(static.get("top_static_rows") or 0)
        if tb > 6:
            candidates.append(("static-top-band", (0, 0, w, min(h, tb + 12))))

        for region, crop in candidates:
            res = ocr_svc.ocr_frame(p, region=region, crop=crop, min_conf=35.0)
            if not res.get("ok") or not res["words"]:
                continue
            regions_scanned.append({"frame_index": fi, "region": region,
                                    "words": len(res["words"]),
                                    "text": res["text"][:200]})
            low = res["text"].lower()
            for hint in UI_TEXT_HINTS:
                if hint in low:
                    ui_hits.append({"frame_index": fi, "region": region, "hint": hint,
                                    "text": res["text"][:120]})
                    break
            for ent in ocr_svc.extract_entities(res["words"], fi, None, None):
                if ent["entity_type"] == "HANDLE":
                    recovered.append({
                        "handle": ent["value"], "frame_index": fi, "region": region,
                        "bbox": ent["bbox"], "confidence": ent["ocr_confidence"],
                        "method": "UI-region OCR",
                    })

    # keep the highest-confidence occurrence of each distinct handle
    dedup: dict[str, dict] = {}
    for r in recovered:
        k = r["handle"].lower()
        if k not in dedup or (r["confidence"] or 0) > (dedup[k]["confidence"] or 0):
            dedup[k] = r
    return {"regions_scanned": regions_scanned, "ui_text_hits": ui_hits,
            "recovered_handles": list(dedup.values())}


def analyse(frame_paths: list[str]) -> dict[str, Any]:
    """Full recapture assessment. Score and likelihood are derived from the
    measurements above — no fixed values anywhere."""
    if not frame_paths:
        return {"likelihood": "INCONCLUSIVE", "score": 0.0,
                "note": "No frames were available for recapture analysis.",
                "letterbox": {}, "static": {}, "fft": {},
                "ui": {"regions_scanned": [], "ui_text_hits": [], "recovered_handles": []}}

    lb = detect_letterbox(frame_paths)
    st = detect_static_bands(frame_paths)
    ff = detect_rescale_moire(frame_paths)
    ui = ocr_ui_regions(frame_paths, st, lb)

    score = 0.0
    if lb.get("detected"):
        score += 30 * min(1.0, (lb.get("vertical_fraction", 0) + lb.get("horizontal_fraction", 0)) / 0.10)
    if st.get("detected"):
        score += 30 * min(1.0, (st.get("top_band_fraction", 0) + st.get("bottom_band_fraction", 0)) / 0.10)
    if ff.get("detected"):
        score += 15
    if ui.get("ui_text_hits"):
        score += 15
    if ui.get("recovered_handles"):
        score += 10
    score = round(min(100.0, score), 1)

    if score >= 60:
        likelihood = "HIGH"
    elif score >= 35:
        likelihood = "MEDIUM"
    elif score >= 15:
        likelihood = "LOW"
    else:
        likelihood = "INCONCLUSIVE"

    if ui["recovered_handles"]:
        note = (f"{len(ui['recovered_handles'])} candidate source handle(s) recovered from "
                f"interface regions by OCR. Requires human verification.")
    elif score >= 35:
        note = ("Recapture indicators detected, but no reliable source handle was recovered "
                "from the interface regions.")
    else:
        note = ("No strong recapture indicators measured. This does not rule out re-encoding "
                "or forwarding.")
    return {"likelihood": likelihood, "score": score, "letterbox": lb, "static": st,
            "fft": ff, "ui": ui, "note": note}
