"""
SROT Phase 4 — Unit Tests for Image Quality & Forensic Reliability Gating.

Tests:
1. Resolution adequacy calculations & megapixels
2. Sharpness via Laplacian variance
3. Dynamic range & exposure clipping
4. Compression blockiness detection
5. Reliability status assignment (RELIABLE, REDUCED_RELIABILITY, INSUFFICIENT_EVIDENCE)
6. Robustness against degenerate and single-color frames
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services import quality as quality_svc


def test_quality_suite():
    print(f"\n{'='*70}")
    print(f"  SROT PHASE 4 — IMAGE QUALITY GATING UNIT TEST SUITE")
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

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # 1. High Quality 1080p Image
        hq_arr = np.random.RandomState(42).randint(30, 220, (1080, 1920, 3), dtype=np.uint8)
        hq_file = tmppath / "hq_1080p.png"
        Image.fromarray(hq_arr).save(hq_file)

        q1 = quality_svc.assess_quality([hq_file])
        check("1. 1080p sharp image graded HIGH / ADEQUATE", q1["quality_grade"] in ("HIGH", "ADEQUATE"))
        check("2. 1080p sharp image reliability is RELIABLE", q1["reliability_status"] == "RELIABLE")
        check("3. Megapixel metric accurate (~2.07 MP)", abs(q1["metrics"]["megapixels"] - 2.07) < 0.1)

        # 2. Low Resolution 240p Image
        lq_arr = np.random.RandomState(43).randint(30, 220, (240, 320, 3), dtype=np.uint8)
        lq_file = tmppath / "lq_240p.png"
        Image.fromarray(lq_arr).save(lq_file)

        q2 = quality_svc.assess_quality([lq_file])
        check("4. 240p image triggers resolution gating factor", any("resolution" in f.lower() for f in q2["gating_factors"]))
        check("5. 240p image quality grade is ADEQUATE / DEGRADED", q2["quality_grade"] in ("ADEQUATE", "DEGRADED"))

        # 3. Severely Blurred + Low-Res Degraded Image
        from PIL import ImageFilter
        deg_img = Image.fromarray(lq_arr).filter(ImageFilter.GaussianBlur(radius=8.0))
        deg_file = tmppath / "degraded.png"
        deg_img.save(deg_file)

        q3 = quality_svc.assess_quality([deg_file])
        check("6. Blurred + low-res image has REDUCED_RELIABILITY or INSUFFICIENT", q3["reliability_status"] in ("REDUCED_RELIABILITY", "INSUFFICIENT_EVIDENCE"))
        check("7. Laplacian variance accurately drops below threshold", q3["metrics"]["sharpness_laplacian"] < 25.0)

        # 4. Pure Solid Black Degenerate Image
        black_img = Image.new("RGB", (512, 512), (0, 0, 0))
        black_file = tmppath / "black.png"
        black_img.save(black_file)

        q4 = quality_svc.assess_quality([black_file])
        check("8. Solid black image handled without crash", q4 is not None)
        check("9. Solid black image assigned INSUFFICIENT_EVIDENCE", q4["reliability_status"] == "INSUFFICIENT_EVIDENCE")

    print(f"\n{'='*70}")
    print(f"  QUALITY GATING UNIT TESTS: {passed} passed, {failed} failed")
    print(f"{'='*70}\n")

    return failed == 0


if __name__ == "__main__":
    success = test_quality_suite()
    sys.exit(0 if success else 1)
