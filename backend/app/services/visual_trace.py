"""
SROT Visual Forensic Trace & Spatial Localization Service.

Generates scientifically grounded spatial trace visualizations:
1. noise_residual: Sensor noise / PRNU high-pass residual energy map.
2. ela_residual: Error Level Analysis (compression quantization rate difference).
3. gradient_inconsistency: High-frequency edge gradient distribution map.

HONESTY STATEMENT:
These maps visualize mathematical signal properties (high-pass residuals,
quantization error levels, and edge gradients). They are forensic decision-support
tools that highlight spatial variations, NOT automatic proof of manipulation.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image as PILImage


def get_available_traces() -> list[dict[str, str]]:
    """Return metadata about available forensic trace types."""
    return [
        {
            "id": "noise_residual",
            "name": "Sensor Noise Residual Map",
            "description": "High-pass spatial residual isolating sensor noise variations and smooth synthetic regions.",
            "interpretation": "Natural camera photos exhibit uniform noise floor. Synthetic media or spliced regions display flat or discontinuous noise energy.",
        },
        {
            "id": "ela_residual",
            "name": "Error Level Analysis (ELA)",
            "description": "Quantization difference map comparing the frame against a controlled re-compression baseline.",
            "interpretation": "Regions saved at different compression levels or spliced from different sources light up with differing error intensity.",
        },
        {
            "id": "gradient_inconsistency",
            "name": "High-Frequency Gradient Map",
            "description": "Spatial edge energy distribution highlighting unnatural sharp vector borders vs natural optical roll-off.",
            "interpretation": "UI elements and synthetic vector boundaries produce extreme localized gradient spikes compared to optical camera lenses.",
        },
    ]


def generate_noise_residual_map(img_bgr: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Extract noise residual via spatial high-pass filtering and compute local variance energy.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    denoised = cv2.medianBlur(gray, 3)
    residual = np.abs(gray.astype(np.float32) - denoised.astype(np.float32))

    # Compute local standard deviation in 16x16 windows
    kernel = np.ones((9, 9), np.float32) / 81.0
    mean = cv2.filter2D(residual, -1, kernel)
    mean_sq = cv2.filter2D(residual ** 2, -1, kernel)
    variance = np.maximum(mean_sq - mean ** 2, 0)
    std_dev = np.sqrt(variance)

    # Normalize to 0..255
    std_norm = cv2.normalize(std_dev, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    heatmap = cv2.applyColorMap(std_norm, cv2.COLORMAP_VIRIDIS)

    # Blend with original for context (40% original, 60% heatmap)
    blended = cv2.addWeighted(img_bgr, 0.35, heatmap, 0.65, 0)

    uniformity = float(1.0 - (np.std(std_dev) / (np.mean(std_dev) + 1e-6)))
    return blended, {
        "trace_type": "noise_residual",
        "mean_residual": round(float(np.mean(residual)), 3),
        "noise_uniformity": round(max(0.0, min(1.0, uniformity)), 3),
        "colormap": "viridis",
    }


def generate_ela_map(img_bgr: np.ndarray, quality: int = 90, scale: int = 15) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Compute Error Level Analysis (ELA) map by re-compressing at specified quality
    and scaling the absolute difference.
    """
    # Encode to JPEG in memory
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    _, enc = cv2.imencode(".jpg", img_bgr, encode_param)
    recompressed = cv2.imdecode(enc, cv2.IMREAD_COLOR)

    # Compute absolute difference
    diff = np.abs(img_bgr.astype(np.float32) - recompressed.astype(np.float32))

    # Scale difference for visual inspection
    diff_scaled = np.clip(diff * scale, 0, 255).astype(np.uint8)

    # Convert to grayscale and apply colormap
    diff_gray = cv2.cvtColor(diff_scaled, cv2.COLOR_BGR2GRAY)
    heatmap = cv2.applyColorMap(diff_gray, cv2.COLORMAP_INFERNO)

    # Blend with original
    blended = cv2.addWeighted(img_bgr, 0.30, heatmap, 0.70, 0)

    mean_diff = float(np.mean(diff))
    max_diff = float(np.max(diff))

    return blended, {
        "trace_type": "ela_residual",
        "baseline_quality": quality,
        "amplification_scale": scale,
        "mean_error_level": round(mean_diff, 2),
        "max_error_level": round(max_diff, 2),
        "colormap": "inferno",
    }


def generate_gradient_map(img_bgr: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Compute high-frequency Sobel gradient magnitude map.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = np.sqrt(grad_x ** 2 + grad_y ** 2)

    mag_norm = cv2.normalize(magnitude, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    heatmap = cv2.applyColorMap(mag_norm, cv2.COLORMAP_TURBO)
    blended = cv2.addWeighted(img_bgr, 0.30, heatmap, 0.70, 0)

    p95 = float(np.percentile(magnitude, 95))
    return blended, {
        "trace_type": "gradient_inconsistency",
        "p95_gradient_magnitude": round(p95, 2),
        "mean_gradient": round(float(np.mean(magnitude)), 2),
        "colormap": "turbo",
    }


def generate_trace(frame_path: str | Path, trace_type: str) -> tuple[bytes | None, dict[str, Any]]:
    """
    Generate the requested forensic trace image as PNG bytes along with metadata.
    """
    p = Path(frame_path)
    if not p.exists():
        return None, {"error": f"Frame file not found: {p}"}

    img = cv2.imread(str(p))
    if img is None:
        return None, {"error": f"Failed to load frame image: {p}"}

    trace_type = trace_type.lower().strip()
    if trace_type == "noise_residual":
        rendered, meta = generate_noise_residual_map(img)
    elif trace_type == "ela_residual":
        rendered, meta = generate_ela_map(img)
    elif trace_type in ("gradient_inconsistency", "gradient"):
        rendered, meta = generate_gradient_map(img)
    else:
        return None, {"error": f"Unknown trace type: {trace_type}. Available: noise_residual, ela_residual, gradient_inconsistency"}

    # Encode rendered image to PNG bytes
    ok, buf = cv2.imencode(".png", rendered)
    if not ok:
        return None, {"error": "Failed to encode trace image to PNG"}

    meta["trace_type"] = trace_type
    meta["dimensions"] = f"{img.shape[1]}x{img.shape[0]}"
    return buf.tobytes(), meta
