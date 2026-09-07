"""
SROT Forensic Case Replay & Reproducibility Verifier CLI.

Usage:
    python backend/replay_case.py <evidence_ref> [--verbose]

Validates forensic reproducibility by re-executing the entire analysis
pipeline on the immutable raw evidence file and comparing recomputed
outputs against stored database records.
"""
from __future__ import annotations

import argparse
import json
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

from app.services.replay import replay_evidence


def run_cli():
    parser = argparse.ArgumentParser(description="SROT Forensic Case Replay Verifier")
    parser.add_argument("evidence_ref", help="Evidence reference (e.g. EV-CASE-2026-001-001)")
    parser.add_argument("--verbose", action="store_true", help="Show verbose output")
    args = parser.parse_args()

    res = replay_evidence(args.evidence_ref, verbose=args.verbose)
    if not res.get("ok", False) and "error" in res:
        print(f"[ERROR] {res['error']}")
        sys.exit(1)

    print(f"\n{'='*70}")
    print(f"  SROT FORENSIC CASE REPLAY VERIFIER")
    print(f"  Evidence Ref: {res['evidence_ref']} | Filename: {res.get('filename')}")
    print(f"  Stored SHA-256: {res.get('stored_sha256')}")
    print(f"{'='*70}\n")

    print("1. Cryptographic File Immutability:")
    print(f"   Stored SHA-256:     {res.get('stored_sha256')}")
    print(f"   Recomputed SHA-256: {res.get('recomputed_sha256')}")
    print(f"   Status: {'MATCH (Immutable)' if res.get('hash_immutable') else 'MISMATCH (Tampered)'}\n")

    print("2. Image Quality Gating:")
    print(f"   Quality Grade:      {res.get('quality_grade')}")
    print(f"   Reliability Status: {res.get('reliability_status')}\n")

    print("3. Execution Hardware & Model Provenance:")
    print(f"   Inference Device:   {res.get('device')}")
    print(f"   Model Version:      {res.get('model_version')}")
    print(f"   Pipeline Version:   {res.get('pipeline_version')}\n")

    print("4. Cross-Signal Evidence Synthesis:")
    print(f"   Evidence State:     {res.get('evidence_state')}")
    print(f"   Signal Consistency: {res.get('signal_consistency')}")
    print(f"   Synthesis Headline: {res.get('synthesis_headline')}\n")

    print(f"{'='*70}")
    print(f"  REPLAY COMPARISON MATRIX (Total Time: {res.get('replay_time_ms')} ms)")
    print(f"{'='*70}")

    for c in res.get("comparisons", []):
        status = "[PASS]" if c["match"] else "[FAIL]"
        delta_str = f"(Δ {c.get('delta', 0.0):+.2f})" if "delta" in c else ""
        print(f"  {status} {c['field']:<32} | Stored: {str(c['stored'])[:12]:<12} | Replayed: {str(c['replayed'])[:12]:<12} {delta_str}")

    print(f"\n  Final Reproducibility Assessment: {'100% REPRODUCIBLE' if res.get('ok') else 'DIVERGENCE DETECTED'}\n")
    sys.exit(0 if res.get("ok") else 1)


if __name__ == "__main__":
    run_cli()
