"""
SROT Image Quality & Forensic Reliability Gating Service.

Evaluates the physical and signal quality of submitted media to determine
whether image resolution, sharpness, exposure, and compression level are
sufficient for defensible forensic signal extraction.

Gating Statuses:
- RELIABLE: Media quality exceeds standard forensic thresholds.
- REDUCED_RELIABILITY: Quality limitations (e.g. low resolution, blur, heavy JPEG compression)
  reduce confidence in high-frequency/sensor-level signals.
- INSUFFICIENT_EVIDENCE: Extreme degradation renders fine-grained pixel forensics unreliable.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np


def _assess_single_frame(path: str | Path) -> dict[str, Any]:
    """Compute physical image quality metrics on a single frame."""
    p = Path(path)
    if not p.exists():
        return {"error": f"File not found: {p}"}

    img = cv2.imread(str(p))
    if img is None:
        return {"error": f"Failed to decode image: {p}"}

    h, w, c = img.shape
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 1. Resolution
    mp = (w * h) / 1_000_000.0

    # 2. Sharpness / Blur Metric (Laplacian variance)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    sharpness = float(lap.var())

    # 3. Dynamic Range & Exposure
    mean_lum = float(np.mean(gray))
    std_lum = float(np.std(gray))
    p1 = float(np.percentile(gray, 1))
    p99 = float(np.percentile(gray, 99))
    dyn_range = p99 - p1

    underexposed_pct = float(np.mean(gray < 10) * 100.0)
    overexposed_pct = float(np.mean(gray > 245) * 100.0)

    # 4. Compression Blocking Metric
    # Ratio of 8x8 block boundary gradient to intra-block gradient
    if h >= 16 and w >= 16:
        # vertical boundaries
        diff_v = np.abs(gray[:, 1:] .astype(np.float32) - gray[:, :-1].astype(np.float32))
        block_cols = np.arange(7, w - 1, 8)
        non_block_cols = [c for c in range(w - 1) if (c + 1) % 8 != 0]
        if len(block_cols) > 0 and len(non_block_cols) > 0:
            v_block = float(np.mean(diff_v[:, block_cols]))
            v_non = float(np.mean(diff_v[:, non_block_cols]))
            blockiness_ratio = round(v_block / (v_non + 1e-6), 3)
        else:
            blockiness_ratio = 1.0
    else:
        blockiness_ratio = 1.0

    # 5. Noise Floor (MAD estimator on high-pass filtered image)
    blur_bg = cv2.GaussianBlur(gray, (5, 5), 1.0)
    residual = np.abs(gray.astype(np.float32) - blur_bg.astype(np.float32))
    noise_mad = float(np.median(residual) * 1.4826)

    return {
        "width": w,
        "height": h,
        "megapixels": round(mp, 3),
        "sharpness_laplacian": round(sharpness, 2),
        "mean_luminance": round(mean_lum, 2),
        "contrast_std": round(std_lum, 2),
        "dynamic_range": round(dyn_range, 1),
        "underexposed_pct": round(underexposed_pct, 2),
        "overexposed_pct": round(overexposed_pct, 2),
        "blockiness_ratio": blockiness_ratio,
        "noise_floor": round(noise_mad, 2),
    }


def assess_quality(frame_paths: list[str | Path]) -> dict[str, Any]:
    """
    Assess quality across sampled frames and produce a forensic reliability gate.
    """
    if not frame_paths:
        return {
            "quality_grade": "UNKNOWN",
            "reliability_status": "INSUFFICIENT_EVIDENCE",
            "gating_factors": ["No frames available for quality assessment."],
            "metrics": {},
            "signal_impact": "Cannot evaluate forensic signal reliability without visual frames.",
        }

    frame_metrics: list[dict[str, Any]] = []
    for fp in frame_paths:
        m = _assess_single_frame(fp)
        if "error" not in m:
            frame_metrics.append(m)

    if not frame_metrics:
        return {
            "quality_grade": "POOR",
            "reliability_status": "INSUFFICIENT_EVIDENCE",
            "gating_factors": ["Failed to decode image frames."],
            "metrics": {},
            "signal_impact": "Pixel data unreadable.",
        }

    # Compute aggregate medians
    w = int(np.median([m["width"] for m in frame_metrics]))
    h = int(np.median([m["height"] for m in frame_metrics]))
    mp = round(float(np.median([m["megapixels"] for m in frame_metrics])), 3)
    sharpness = round(float(np.median([m["sharpness_laplacian"] for m in frame_metrics])), 2)
    mean_lum = round(float(np.median([m["mean_luminance"] for m in frame_metrics])), 2)
    contrast = round(float(np.median([m["contrast_std"] for m in frame_metrics])), 2)
    dyn_range = round(float(np.median([m["dynamic_range"] for m in frame_metrics])), 1)
    under_exp = round(float(np.median([m["underexposed_pct"] for m in frame_metrics])), 2)
    over_exp = round(float(np.median([m["overexposed_pct"] for m in frame_metrics])), 2)
    blockiness = round(float(np.median([m["blockiness_ratio"] for m in frame_metrics])), 3)
    noise_floor = round(float(np.median([m["noise_floor"] for m in frame_metrics])), 2)

    gating_factors: list[str] = []
    penalties = 0

    # 1. Resolution Check
    if min(w, h) < 360 or mp < 0.2:
        gating_factors.append(f"Low resolution ({w}×{h}, {mp} MP): fine-grained sensor noise & PRNU cannot be reliably extracted.")
        penalties += 2
    elif min(w, h) < 720:
        gating_factors.append(f"Moderate resolution ({w}×{h}): acceptable for perceptual hashing and OCR, reduced sensitivity for DCT analysis.")
        penalties += 1

    # 2. Sharpness / Blur Check
    if sharpness < 25.0:
        gating_factors.append(f"Severe motion/optical blur (Laplacian variance {sharpness}): high-frequency forensic features suppressed.")
        penalties += 2
    elif sharpness < 80.0:
        gating_factors.append(f"Mild blur (Laplacian variance {sharpness}): high-frequency energy measurements attenuated.")
        penalties += 1

    # 3. Dynamic Range & Exposure Clipping Check
    if (under_exp + over_exp) > 35.0:
        gating_factors.append(f"Extreme exposure clipping ({under_exp:.1f}% shadows, {over_exp:.1f}% highlights): clipped pixel regions lack noise residuals.")
        penalties += 2
    elif dyn_range < 80.0:
        gating_factors.append(f"Compressed dynamic range ({dyn_range:.0f}/255): low contrast may affect texture analysis.")
        penalties += 1

    # 4. Compression Blocking Check
    if blockiness > 1.4:
        gating_factors.append(f"Heavy compression blocking (block ratio {blockiness:.2f}): DCT structure dominated by coarse quantization grid.")
        penalties += 2
    elif blockiness > 1.15:
        gating_factors.append(f"Noticeable compression grid (block ratio {blockiness:.2f}): re-compression history signals should be prioritized.")
        penalties += 1

    # Overall Quality Grade & Reliability Status
    if penalties == 0:
        quality_grade = "HIGH"
        reliability_status = "RELIABLE"
        impact_summary = "Media quality is excellent. All classical forensic and neural signals are operating within high-confidence operational parameters."
    elif penalties <= 2:
        quality_grade = "ADEQUATE"
        reliability_status = "RELIABLE"
        impact_summary = "Media quality is adequate for standard forensic casework. Minor compression/resolution limits noted without invalidating findings."
    elif penalties <= 4:
        quality_grade = "DEGRADED"
        reliability_status = "REDUCED_RELIABILITY"
        impact_summary = "Media exhibits significant compression or resolution degradation. Sensor-noise and high-frequency signals carry reduced confidence; perceptual hashing and recapture signals remain resilient."
    else:
        quality_grade = "POOR"
        reliability_status = "INSUFFICIENT_EVIDENCE"
        impact_summary = "Severe quality degradation prevents reliable pixel-level forensic discrimination. Findings must be treated with substantial caution."

    if not gating_factors:
        gating_factors.append("No adverse quality gating factors identified. Resolution, dynamic range, and sharpness are satisfactory.")

    return {
        "quality_grade": quality_grade,
        "reliability_status": reliability_status,
        "quality_score_pct": max(15, min(100, int(100 - penalties * 18))),
        "gating_factors": gating_factors,
        "impact_summary": impact_summary,
        "metrics": {
            "width": w,
            "height": h,
            "megapixels": mp,
            "sharpness_laplacian": sharpness,
            "mean_luminance": mean_lum,
            "contrast_std": contrast,
            "dynamic_range": dyn_range,
            "underexposed_pct": under_exp,
            "overexposed_pct": over_exp,
            "blockiness_ratio": blockiness,
            "noise_floor": noise_floor,
            "frames_evaluated": len(frame_metrics),
        },
    }
