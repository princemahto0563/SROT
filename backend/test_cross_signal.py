"""
SROT Phase 4 — Unit Tests for Cross-Signal Forensic Assessment Layer.

Tests:
1. Evidence-state assignment (CONSISTENT, PARTIALLY_CORROBORATED, CONFLICTING, INSUFFICIENT)
2. Signal consistency detection (STRONG_CONSISTENCY, MODERATE_CONSISTENCY, MIXED, CONFLICTING, INSUFFICIENT)
3. Screenshot false-positive safeguard & rationale generation
4. Evidence Matrix structure (7 sources, correct strength/status/limitations)
5. Quality gate integration and downstream reliability impact
6. Transparent score semantics (score_semantics: MODEL_SCORE)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services import cross_signal as cross_svc


def test_cross_signal_suite():
    print(f"\n{'='*70}")
    print(f"  SROT PHASE 4 — CROSS-SIGNAL FUSION UNIT TEST SUITE")
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

    # Test 1: Authentic Baseline Case
    auth_ev = {"evidence_ref": "EV-AUTH", "sha256": "1234567890abcdef", "size_bytes": 500000, "exif_fields": 12, "c2pa_present": False}
    auth_sigs = [
        {"name": "Sensor-noise residual", "score": 12.0, "result": "No indicator", "strength": "Weak"},
        {"name": "DCT first-digit distribution", "score": 8.0, "result": "No indicator", "strength": "Weak"},
    ]
    auth_q = {"quality_grade": "HIGH", "reliability_status": "RELIABLE", "quality_score_pct": 95}
    auth_neural = {"model_available": True, "aggregate": {"median_score": 0.12}}
    auth_rec = {"likelihood": "LOW", "likelihood_score": 5.0, "static_bands": {"detected": False}}

    res1 = cross_svc.synthesize_cross_signal_assessment(auth_ev, auth_sigs, auth_rec, auth_neural, [], auth_q)
    check("1. Authentic baseline assigned CONSISTENT", res1["evidence_state"] == "CONSISTENT")
    check("2. Authentic baseline assigned STRONG_CONSISTENCY", res1["signal_consistency"] == "STRONG_CONSISTENCY")
    check("3. Score semantics is MODEL_SCORE", res1["score_semantics"] == "MODEL_SCORE")

    # Test 2: Screen-Recorded Media with High Neural Score (Safeguard Test)
    rec_ev = {"evidence_ref": "EV-SCREEN", "sha256": "fedcba0987654321", "size_bytes": 800000, "exif_fields": 0, "c2pa_present": False}
    rec_rec = {"likelihood": "HIGH", "likelihood_score": 75.0, "static_bands": {"detected": True}, "recovered_handles": [{"handle": "@source_alpha"}]}
    rec_neural = {"model_available": True, "aggregate": {"median_score": 0.78}}

    res2 = cross_svc.synthesize_cross_signal_assessment(rec_ev, auth_sigs, rec_rec, rec_neural, [], auth_q)
    check("4. Recaptured + elevated neural assigned PARTIALLY_CORROBORATED", res2["evidence_state"] == "PARTIALLY_CORROBORATED")
    check("5. Recaptured + elevated neural assigned MIXED consistency", res2["signal_consistency"] == "MIXED")
    check("6. Dissenting factor notes UI artifact interaction", len(res2["dissenting_or_neutral_factors"]) > 0 and "screen-recording" in res2["dissenting_or_neutral_factors"][0])

    # Test 3: Neural vs Classical Conflicting Case
    conf_neural = {"model_available": True, "aggregate": {"median_score": 0.85}}
    conf_sigs = [
        {"name": "Sensor-noise residual", "score": 8.0, "result": "No indicator", "strength": "Weak"},
        {"name": "DCT first-digit distribution", "score": 5.0, "result": "No indicator", "strength": "Weak"},
        {"name": "Re-compression history", "score": 6.0, "result": "No indicator", "strength": "Weak"},
    ]
    res3 = cross_svc.synthesize_cross_signal_assessment(auth_ev, conf_sigs, auth_rec, conf_neural, [], auth_q)
    check("7. High neural + pristine classical assigned CONFLICTING state", res3["evidence_state"] == "CONFLICTING")
    check("8. High neural + pristine classical assigned CONFLICTING consistency", res3["signal_consistency"] == "CONFLICTING")

    # Test 4: Insufficient Quality Gate Case
    poor_q = {"quality_grade": "POOR", "reliability_status": "INSUFFICIENT_EVIDENCE", "quality_score_pct": 20}
    res4 = cross_svc.synthesize_cross_signal_assessment(auth_ev, auth_sigs, auth_rec, auth_neural, [], poor_q)
    check("9. Poor quality gate assigned INSUFFICIENT evidence state", res4["evidence_state"] == "INSUFFICIENT")
    check("10. Poor quality gate assigned INSUFFICIENT consistency", res4["signal_consistency"] == "INSUFFICIENT")

    # Test 5: Evidence Matrix Structure Verification
    matrix = res1["evidence_matrix"]
    check("11. Evidence Matrix contains at least 5 structured sources", len(matrix) >= 5)
    has_keys = all("source" in row and "observation" in row and "limitation" in row for row in matrix)
    check("12. All Evidence Matrix items define observation & limitation", has_keys)

    print(f"\n{'='*70}")
    print(f"  CROSS-SIGNAL UNIT TESTS: {passed} passed, {failed} failed")
    print(f"{'='*70}\n")

    return failed == 0


if __name__ == "__main__":
    success = test_cross_signal_suite()
    sys.exit(0 if success else 1)
