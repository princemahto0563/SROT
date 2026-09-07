"""
SROT Phase 4 — Unit Test for Case Replay & Deterministic Reproducibility.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if sys.platform == "darwin":
    for p in ["/opt/homebrew/lib", "/usr/local/lib"]:
        if os.path.exists(p):
            cur = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
            if p not in cur:
                os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = f"{p}:{cur}" if cur else p

from app.db import SessionLocal
from app.models import Evidence
from replay_case import replay_evidence


def test_replay_reproducibility():
    db = SessionLocal()
    try:
        ev = db.query(Evidence).first()
        assert ev is not None, "No evidence in database to test replay."
        res = replay_evidence(ev.evidence_ref)
        assert res["ok"], f"Replay failed for {ev.evidence_ref}"
        assert res["hash_immutable"], "Hash immutability check failed."
        print(f"\n[PASS] Replay reproducibility verified for {ev.evidence_ref}")
    finally:
        db.close()


if __name__ == "__main__":
    test_replay_reproducibility()
