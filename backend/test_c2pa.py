"""
Unit test suite for C2PA Offline Trust and Provenance Validation Layer
"""

import os
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.c2pa_trust import validate_c2pa, OFFLINE_TRUST_ANCHORS


def run_tests():
    passed = 0
    total = 0

    def check(name: str, cond: bool, detail: str = ""):
        nonlocal passed, total
        total += 1
        if cond:
            passed += 1
            print(f"  [PASS] {name} {(' — ' + detail) if detail else ''}")
        else:
            print(f"  [FAIL] {name} {(' — ' + detail) if detail else ''}")

    print("\n====================================================================")
    print("C2PA OFFLINE TRUST VALIDATION TEST SUITE")
    print("====================================================================")

    # 1. Manifest Absent
    res1 = validate_c2pa(b"standard raw jpeg bytes without any jumbf markers")
    check("1. Manifest Absent", res1["status"] == "MANIFEST_ABSENT", f"status={res1['status']}")
    check("1b. Absence is not considered manipulation", "zero negative evidentiary weight" in res1["forensic_boundary"])

    # 2. Manifest Present but Unvalidated (corrupt/truncated cert)
    res2 = validate_c2pa(b"prefix data ... c2pa ... jumb ... c2pa.claim ... no cert block")
    check("2. Manifest Present Unvalidated", res2["status"] == "MANIFEST_PRESENT_UNVALIDATED", f"status={res2['status']}")

    # 3. Signature Invalid (tampered asset / invalid sig payload)
    sample_cert = b"\x30\x82\x02\x00CN=Test Signer, O=Test OrgIssuer: Test Issuer 20260101000000Z20300101000000Z"
    res3 = validate_c2pa(b"c2pa ... c2pa.claim ... c2pa.signature ... CORRUPT_SIG ... " + sample_cert)
    check("3. Signature Invalid", res3["status"] == "SIGNATURE_INVALID", f"status={res3['status']}")

    # 4. Signature Valid but Untrusted Signer (Self-signed / unknown root)
    untrusted_cert = b"\x30\x82\x02\x00CN=Untrusted Custom Creator, O=AdHoc Creator 20250101000000Z20300101000000Z"
    res4 = validate_c2pa(b"c2pa ... c2pa.claim ... c2pa.signature ... " + untrusted_cert)
    check("4. Signature Valid Untrusted", res4["status"] == "SIGNATURE_VALID_UNTRUSTED", f"status={res4['status']}")

    # 5. Trusted C2PA (Linked to Adobe/Sony/Truepic offline trust anchor)
    trusted_cert = b"\x30\x82\x02\x00CN=Adobe C2PA Production Root CA, O=Adobe Inc., C=US 20250101000000Z20300101000000Z"
    res5 = validate_c2pa(b"c2pa ... c2pa.claim ... c2pa.signature ... " + trusted_cert)
    check("5. Trusted C2PA Anchor", res5["status"] == "TRUSTED_C2PA", f"status={res5['status']}")
    check("5b. Trust anchor verified", res5["trust_anchor_verified"] is True)

    # 6. Legacy ITL Trust
    res6 = validate_c2pa(b"c2pa ... c2pa.claim ... Adobe ITL legacy manifest")
    check("6. Legacy ITL Trust", res6["status"] == "LEGACY_ITL_TRUST", f"status={res6['status']}")

    # 7. Trust Validation Unavailable (inaccessible file)
    res7 = validate_c2pa(Path("/non/existent/file.jpg"))
    check("7. Trust Validation Unavailable", res7["status"] == "TRUST_VALIDATION_UNAVAILABLE", f"status={res7['status']}")

    # 8. Provenance vs Authenticity boundary statement
    check("8. Boundary disclaims scene ground truth", "does NOT independently establish" in res5["forensic_boundary"])

    print(f"\nRESULTS: {passed}/{total} checks passed.\n")
    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
