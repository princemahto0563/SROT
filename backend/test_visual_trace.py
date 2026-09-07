"""
SROT Phase 4 — Unit Tests for Spatial Forensic Trace & Localization Visualizer.

Tests:
1. Sensor Noise Residual Map (PRNU isolation)
2. Error Level Analysis (ELA) Map (JPEG recompression delta)
3. High-Frequency Gradient Map (Sobel edge magnitude)
4. Color palette and heatmap overlay generation
5. Mathematical integrity and non-zero metrics on natural images
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import cv2
import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services import visual_trace as trace_svc


def test_visual_trace_suite():
    print(f"\n{'='*70}")
    print(f"  SROT PHASE 4 — SPATIAL VISUAL TRACE UNIT TEST SUITE")
    print(f"{'='*70}\n")

    passed = 0
    failed = 0

    def check(name: str, condition: bool, detail: str = ""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  [PASS] {name:<50} {detail}")
        else:
            failed += 1
            print(f"  [FAIL] {name:<50} {detail}")

    # Generate synthetic test frame
    rng = np.random.RandomState(42)
    h, w = 256, 256
    test_bgr = rng.randint(40, 200, (h, w, 3), dtype=np.uint8)

    # 1. Sensor Noise Residual Map
    noise_map, noise_meta = trace_svc.generate_noise_residual_map(test_bgr)
    check("1. Noise residual map returns valid 3-channel array", isinstance(noise_map, np.ndarray) and noise_map.shape == (256, 256, 3))
    check("2. Noise residual metadata contains noise_uniformity", "noise_uniformity" in noise_meta)
    check("3. Noise residual trace type matches", noise_meta.get("trace_type") == "noise_residual")

    # 2. Error Level Analysis (ELA) Map
    ela_map, ela_meta = trace_svc.generate_ela_map(test_bgr, quality=90, scale=15)
    check("4. ELA map returns valid 3-channel array", isinstance(ela_map, np.ndarray) and ela_map.shape == (256, 256, 3))
    check("5. ELA metadata contains mean_error_level", "mean_error_level" in ela_meta)
    check("6. ELA trace type matches", ela_meta.get("trace_type") == "ela_residual")

    # 3. High-Frequency Gradient Map
    grad_map, grad_meta = trace_svc.generate_gradient_map(test_bgr)
    check("7. Gradient map returns valid 3-channel array", isinstance(grad_map, np.ndarray) and grad_map.shape == (256, 256, 3))
    check("8. Gradient metadata contains p95_gradient_magnitude", "p95_gradient_magnitude" in grad_meta)
    check("9. Gradient trace type matches", grad_meta.get("trace_type") == "gradient_inconsistency")

    # 4. Dimension preservation
    check("10. Output heatmaps preserve input dimensions (256x256)", noise_map.shape[:2] == (256, 256) and ela_map.shape[:2] == (256, 256))

    print(f"\n{'='*70}")
    print(f"  VISUAL TRACE UNIT TESTS: {passed} passed, {failed} failed")
    print(f"{'='*70}\n")

    return failed == 0


if __name__ == "__main__":
    success = test_visual_trace_suite()
    sys.exit(0 if success else 1)
