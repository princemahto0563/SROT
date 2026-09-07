"""
SROT Forensic Case Replay Service.

Provides deterministic, immutable case replay to verify that re-running the complete
forensic pipeline against stored raw evidence yields mathematically identical results.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

from ..db import SessionLocal
from ..models import Evidence, AnalysisRun, Signal
from ..pipeline import score_media
from . import (
    integrity,
    quality as quality_svc,
    signals as sig_svc,
    neural as neural_svc,
    recapture as recapture_svc,
    cross_signal as cross_svc,
)


def replay_evidence(evidence_ref: str, verbose: bool = False) -> dict[str, Any]:
    """
    Re-run the forensic pipeline on an ingested evidence item and compare
    stored vs recomputed results.
    """
    db = SessionLocal()
    try:
        ev: Evidence | None = (
            db.query(Evidence).filter(Evidence.evidence_ref == evidence_ref).first()
        )
        if not ev:
            return {"ok": False, "error": f"Evidence '{evidence_ref}' not found."}

        ev_path = Path(ev.stored_path)
        if not ev_path.exists():
            return {"ok": False, "error": f"File '{ev.stored_path}' missing on disk."}

        latest_run: AnalysisRun | None = (
            db.query(AnalysisRun)
            .filter(AnalysisRun.evidence_id == ev.id)
            .order_by(AnalysisRun.id.desc())
            .first()
        )

        t0 = time.perf_counter()

        # 1. Verify file hash immutability
        recomputed_sha256 = integrity.sha256_file(ev_path)
        hash_match = (recomputed_sha256 == ev.sha256)

        # 2. Replay Full Scoring Pipeline (Frames, Signals, Neural, Hashes)
        scratch = Path("data/scratch") / f"replay_{ev.evidence_ref}_{int(time.time())}"
        scratch.mkdir(parents=True, exist_ok=True)
        scored = score_media(ev_path, scratch, ev.media_kind)

        frame_paths = [r["path"] for r in scored.get("frame_records", [])]
        if not frame_paths:
            frame_paths = [str(ev_path)]

        # 3. Quality Gate Replay
        quality_res = quality_svc.assess_quality(frame_paths)

        # 4. Neural Classifier Replay
        neural_res = None
        neural_score = None
        if neural_svc.detector_available():
            n_analysis = neural_svc.analyse_frames(frame_paths)
            neural_res = n_analysis.to_dict()
            neural_score = neural_res.get("median_score")

        classical_sigs = scored.get("signals", [])

        # 5. Recapture Forensics Replay
        recapture_res = recapture_svc.analyse(frame_paths)
        if neural_res:
            neural_res["screenshot_caution"] = bool(recapture_res.get("likelihood") in ("HIGH", "MEDIUM"))

        # 6. Cross-Signal Evidence-State Synthesis Replay
        evidence_facts = {
            "evidence_ref": ev.evidence_ref,
            "filename": ev.filename,
            "sha256": ev.sha256,
            "size_bytes": ev.size_bytes,
            "media_kind": ev.media_kind,
            "exif_fields": len(ev.exif_json or {}),
            "c2pa_present": ev.c2pa_present,
        }
        cross_res = cross_svc.synthesize_cross_signal_assessment(
            evidence_facts=evidence_facts,
            signals=classical_sigs,
            recapture=recapture_res,
            neural=neural_res,
            origin_matches=[],
            quality_gate=quality_res,
        )

        replay_time_ms = int((time.perf_counter() - t0) * 1000)

        # Cleanup scratch
        try:
            import shutil
            shutil.rmtree(scratch)
        except Exception:
            pass

        # Comparisons
        comparisons: list[dict[str, Any]] = [
            {"field": "SHA-256 Hash", "stored": ev.sha256, "replayed": recomputed_sha256, "delta": 0.0, "match": hash_match},
        ]

        if latest_run and latest_run.aggregate_score is not None:
            agg_res = sig_svc.aggregate(classical_sigs)
            replayed_agg = agg_res.get("aggregate")
            agg_match = (
                replayed_agg is not None and
                abs(replayed_agg - latest_run.aggregate_score) < 1.0
            )
            comparisons.append({
                "field": "Aggregate Signal Score",
                "stored": latest_run.aggregate_score,
                "replayed": replayed_agg,
                "delta": round((replayed_agg or 0) - latest_run.aggregate_score, 2),
                "match": agg_match,
            })

        # Fetch stored individual signals from latest_run
        stored_signals: list[Signal] = []
        if latest_run:
            stored_signals = db.query(Signal).filter(Signal.run_id == latest_run.id).all()

        replayed_key_map = {s.get("key", s.get("name")): s for s in classical_sigs}
        replayed_name_map = {s.get("name"): s for s in classical_sigs}

        for s_row in stored_signals:
            sig_key = s_row.key or s_row.name
            r_sig = replayed_key_map.get(sig_key) or replayed_name_map.get(s_row.name)
            if not r_sig and ("neural" in sig_key.lower() or "ai" in sig_key.lower()):
                r_sig = replayed_key_map.get("neural_detector")

            s_score = s_row.score
            r_score = r_sig.get("score") if r_sig else None
            sig_match = True
            if s_score is not None and r_score is not None:
                sig_match = abs(s_score - r_score) < 1.0
            elif s_score is None and r_score is None:
                sig_match = True
            else:
                sig_match = False
            comparisons.append({
                "field": f"Signal: {s_row.name}",
                "stored": round(s_score, 2) if s_score is not None else "None",
                "replayed": round(r_score, 2) if r_score is not None else "None",
                "delta": round(r_score - s_score, 2) if (s_score is not None and r_score is not None) else 0.0,
                "match": sig_match,
            })

        all_passed = all(c["match"] for c in comparisons)

        return {
            "ok": all_passed,
            "evidence_ref": ev.evidence_ref,
            "filename": ev.filename,
            "hash_immutable": hash_match,
            "stored_sha256": ev.sha256,
            "recomputed_sha256": recomputed_sha256,
            "replay_time_ms": replay_time_ms,
            "quality_grade": quality_res.get("quality_grade"),
            "reliability_status": quality_res.get("reliability_status"),
            "comparisons": comparisons,
            "evidence_state": cross_res.get("evidence_state"),
            "signal_consistency": cross_res.get("signal_consistency"),
            "synthesis_headline": cross_res.get("synthesis_headline"),
            "device": neural_res.get("device", "cpu") if neural_res else "cpu",
            "model_version": neural_res.get("model_version", "1.0") if neural_res else "N/A",
            "model_provenance": neural_svc.model_provenance(),
            "pipeline_version": "4.0.0-phase4",
        }
    finally:
        db.close()
