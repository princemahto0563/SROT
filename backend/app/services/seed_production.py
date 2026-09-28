"""
Deterministic, idempotent, case-scoped seed service for SROT production deployments (Render/Docker/Local).
Safely rehydrates demo cases (CASE-2026-112, CASE-2026-119, CASE-2026-121) and bundled media
without destructive resets, duplicate records, or machine-specific absolute paths.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..db import SessionLocal, BASE_DIR, EVIDENCE_DIR, WORK_DIR, CORPUS_DIR, resolve_data_path
from ..models import (
    Case, Evidence, AnalysisRun, Signal, FrameAnalysis, NeuralFrameResult,
    RecaptureResult, ExtractedEntity, Fingerprint, ForensicComparison,
    StressTestRun, StressVariant, GraphNode, GraphEdge, TimelineEvent,
    Lead, AuditLog, CorpusItem, utcnow
)
from ..services import audit as audit_svc

log = logging.getLogger("srot.seed_production")

DEMO_DATA_DIR = Path(__file__).resolve().parents[2] / "demo_data"
FIXTURE_PATH = DEMO_DATA_DIR / "seed_cases.json"

EXPECTED_AUTH_112_SHA = "c2ff38465cf4c2faf50bdd5b9f51abcadc90beba73867ce795c1edc4393bd63f"


def _parse_dt(val: str | None) -> dt.datetime | None:
    if not val:
        return None
    try:
        return dt.datetime.fromisoformat(val)
    except Exception:
        return None


def copy_demo_files_if_missing() -> None:
    """Safely copies bundled demo media into SROT_DATA if not already present."""
    if not DEMO_DATA_DIR.exists():
        log.info("Demo data directory %s not present; skipping media copy", DEMO_DATA_DIR)
        return

    # 1. Evidence files
    ev_src_base = DEMO_DATA_DIR / "evidence"
    if ev_src_base.exists():
        for case_dir in ev_src_base.iterdir():
            if not case_dir.is_dir():
                continue
            dst_case_dir = Path(EVIDENCE_DIR) / case_dir.name
            dst_case_dir.mkdir(parents=True, exist_ok=True)
            for file_path in case_dir.iterdir():
                if file_path.is_file():
                    dst_file = dst_case_dir / file_path.name
                    if not dst_file.exists() or dst_file.stat().st_size != file_path.stat().st_size:
                        shutil.copy2(file_path, dst_file)
                        log.debug("Copied evidence %s to %s", file_path.name, dst_file)

    # 2. Work files (stress test variants, pre-computed traces)
    work_src_base = DEMO_DATA_DIR / "work"
    if work_src_base.exists():
        for ev_work_dir in work_src_base.iterdir():
            if not ev_work_dir.is_dir():
                continue
            dst_work_dir = Path(WORK_DIR) / ev_work_dir.name
            dst_work_dir.mkdir(parents=True, exist_ok=True)
            for sub in ev_work_dir.iterdir():
                if sub.is_dir():
                    dst_sub = dst_work_dir / sub.name
                    if not dst_sub.exists():
                        shutil.copytree(sub, dst_sub)
                    else:
                        for f in sub.iterdir():
                            if f.is_file() and not (dst_sub / f.name).exists():
                                shutil.copy2(f, dst_sub / f.name)

    # 3. Corpus items
    corpus_src_base = DEMO_DATA_DIR / "corpus"
    if corpus_src_base.exists():
        Path(CORPUS_DIR).mkdir(parents=True, exist_ok=True)
        for f in corpus_src_base.iterdir():
            if f.is_file():
                dst_corpus = Path(CORPUS_DIR) / f.name
                if not dst_corpus.exists():
                    shutil.copy2(f, dst_corpus)


def ensure_demo_cases(db: Session) -> dict[str, Any]:
    """
    Idempotent restoration and verification of demo cases:
    - CASE-2026-112 (Hero demo: 13 evidence, 1 auth ref, 12 derivatives, 12 comparisons, stress run, etc.)
    - CASE-2026-119 (9 evidence, comparisons, graph, timeline)
    - CASE-2026-121 (3 evidence, graph, timeline)
    - Preserves existing CASE-2026-001 or any user-created cases.
    """
    copy_demo_files_if_missing()

    if not FIXTURE_PATH.exists():
        log.warning("Seed fixture %s not found; skipping deterministic seed", FIXTURE_PATH)
        return {"status": "no_fixture"}

    try:
        with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        log.error("Failed to load seed fixture %s: %s", FIXTURE_PATH, exc)
        return {"status": "fixture_error", "error": str(exc)}

    # 1. Corpus items
    for ci in data.get("corpus", []):
        existing = db.query(CorpusItem).filter(CorpusItem.label == ci["label"]).first()
        if not existing:
            item = CorpusItem(
                label=ci["label"],
                source_kind=ci.get("source_kind"),
                filename=ci.get("filename"),
                stored_path=ci.get("stored_path"),
                sha256=ci.get("sha256"),
                observed_at=_parse_dt(ci.get("observed_at")),
                is_synthetic=ci.get("is_synthetic", True),
                note=ci.get("note", ""),
                transform=ci.get("transform", ""),
            )
            db.add(item)
    db.commit()

    results = {}

    # 2. Cases
    for case_spec in data.get("cases", []):
        case_ref = case_spec["case_ref"]
        case = db.query(Case).filter(Case.case_ref == case_ref).first()
        if not case:
            case = Case(
                case_ref=case_ref,
                title=case_spec["title"],
                category=case_spec.get("category", "Digital Media Forensics"),
                officer=case_spec.get("officer", "Investigating Officer (demo)"),
                unit=case_spec.get("unit", "Digital Forensics Unit"),
                summary=case_spec.get("summary", ""),
                status=case_spec.get("status", "Open"),
                created_at=_parse_dt(case_spec.get("created_at")) or utcnow(),
            )
            db.add(case)
            db.commit()
            db.refresh(case)
            audit_svc.record(
                db, case_id=case.id, action=f"Case {case.case_ref} opened",
                component="case manager", payload={"seeded": True}
            )

        # Evidence items
        ev_map = {}  # evidence_ref -> Evidence
        for e_spec in case_spec.get("evidence", []):
            ev_ref = e_spec["evidence_ref"]
            ev = db.query(Evidence).filter(Evidence.evidence_ref == ev_ref).first()
            canonical_path = e_spec["stored_path"].replace("\\", "/")
            if not ev:
                ev = Evidence(
                    evidence_ref=ev_ref,
                    case_id=case.id,
                    filename=e_spec["filename"],
                    stored_path=canonical_path,
                    mime_type=e_spec.get("mime_type", "image/jpeg"),
                    media_kind=e_spec.get("media_kind", "image"),
                    size_bytes=e_spec.get("size_bytes", 0),
                    sha256=e_spec.get("sha256", ""),
                    forensic_role=e_spec.get("forensic_role", "UNKNOWN"),
                    width=e_spec.get("width"),
                    height=e_spec.get("height"),
                    duration_s=e_spec.get("duration_s"),
                    fps=e_spec.get("fps"),
                    video_codec=e_spec.get("video_codec"),
                    audio_codec=e_spec.get("audio_codec"),
                    container_format=e_spec.get("container_format"),
                    encoder_tag=e_spec.get("encoder_tag"),
                    has_audio=bool(e_spec.get("has_audio")),
                    c2pa_present=bool(e_spec.get("c2pa_present")),
                    c2pa_note=e_spec.get("c2pa_note", ""),
                    probe_json=e_spec.get("probe_json"),
                    exif_json=e_spec.get("exif_json"),
                )
                db.add(ev)
                db.commit()
                db.refresh(ev)
            else:
                # Ensure canonical relative path and role
                updated = False
                if ev.stored_path != canonical_path and not ev.stored_path.startswith("evidence/"):
                    ev.stored_path = canonical_path
                    updated = True
                if ev.forensic_role != e_spec.get("forensic_role"):
                    ev.forensic_role = e_spec.get("forensic_role")
                    updated = True
                if updated:
                    db.add(ev); db.commit(); db.refresh(ev)

            ev_map[ev_ref] = ev

            # AnalysisRun & derived signals
            run_spec = e_spec.get("latest_run")
            if run_spec:
                run = db.query(AnalysisRun).filter(
                    AnalysisRun.evidence_id == ev.id,
                    AnalysisRun.status == "completed"
                ).first()
                if not run:
                    run = AnalysisRun(
                        evidence_id=ev.id,
                        status="completed",
                        stage=run_spec.get("stage", "done"),
                        stages_json=run_spec.get("stages_json"),
                        aggregate_score=run_spec.get("aggregate_score"),
                        assessment=run_spec.get("assessment"),
                        confidence_band=run_spec.get("confidence_band"),
                        detector_backend=run_spec.get("detector_backend"),
                        aggregation_formula=run_spec.get("aggregation_formula"),
                        dissent=bool(run_spec.get("dissent")),
                        frames_sampled=run_spec.get("frames_sampled", 1),
                        finished_at=_parse_dt(run_spec.get("finished_at")) or utcnow(),
                    )
                    db.add(run)
                    db.commit()
                    db.refresh(run)

                    # Signals
                    for sig in run_spec.get("signals", []):
                        db.add(Signal(
                            run_id=run.id, key=sig["key"], name=sig["name"],
                            result=sig["result"], strength=sig["strength"],
                            score=sig.get("score"), weight=sig.get("weight", 0.0),
                            direction=sig.get("direction", "supports"),
                            measurement=sig.get("measurement"), method=sig.get("method"),
                            note=sig.get("note", "")
                        ))

                    # Neural frame results
                    for nf in run_spec.get("neural_frames", []):
                        db.add(NeuralFrameResult(
                            evidence_id=ev.id, run_id=run.id,
                            frame_index=nf.get("frame_index", 0),
                            frame_number=nf.get("frame_number"),
                            timestamp_s=nf.get("timestamp_s"),
                            model_name=nf.get("model_name"),
                            model_version=nf.get("model_version"),
                            raw_output=nf.get("raw_output"),
                            normalized_score=nf.get("normalized_score"),
                            label=nf.get("label"),
                            inference_time_ms=nf.get("inference_time_ms", 0),
                            error=nf.get("error")
                        ))

                    # Recapture result
                    rc = run_spec.get("recapture")
                    if rc:
                        db.add(RecaptureResult(
                            evidence_id=ev.id, run_id=run.id,
                            likelihood=rc.get("likelihood", "INCONCLUSIVE"),
                            score=rc.get("score"),
                            letterbox_json=rc.get("letterbox_json"),
                            static_band_json=rc.get("static_band_json"),
                            fft_json=rc.get("fft_json"),
                            ui_regions_json=rc.get("ui_regions_json"),
                            recovered_handles_json=rc.get("recovered_handles_json"),
                            note=rc.get("note")
                        ))

                    # Extracted entities
                    for en in run_spec.get("entities", []):
                        db.add(ExtractedEntity(
                            evidence_id=ev.id, run_id=run.id,
                            entity_type=en.get("entity_type"),
                            value=en.get("value"),
                            raw_text=en.get("raw_text"),
                            language=en.get("language"),
                            frame_index=en.get("frame_index"),
                            frame_number=en.get("frame_number"),
                            timestamp_s=en.get("timestamp_s"),
                            bbox_json=en.get("bbox_json"),
                            ocr_confidence=en.get("ocr_confidence"),
                            method=en.get("method", "tesseract-ocr"),
                            region=en.get("region", "full-frame")
                        ))

                    # Fingerprints
                    for fp in run_spec.get("fingerprints", []):
                        db.add(Fingerprint(
                            evidence_id=ev.id,
                            hash_type=fp.get("hash_type"),
                            hash_hex=fp.get("hash_hex"),
                            frame_index=fp.get("frame_index", 0)
                        ))

                    # Stress run
                    srun_spec = run_spec.get("stress_run")
                    if srun_spec:
                        existing_srun = db.query(StressTestRun).filter(StressTestRun.evidence_id == ev.id).first()
                        if not existing_srun:
                            srun = StressTestRun(
                                evidence_id=ev.id,
                                status=srun_spec.get("status", "completed"),
                                baseline_score=srun_spec.get("baseline_score"),
                                reliability_boundary=srun_spec.get("reliability_boundary", ""),
                                recommendation=srun_spec.get("recommendation", ""),
                                finished_at=_parse_dt(srun_spec.get("finished_at")) or utcnow()
                            )
                            db.add(srun); db.commit(); db.refresh(srun)
                            for v in srun_spec.get("variants", []):
                                db.add(StressVariant(
                                    stress_id=srun.id, name=v["name"], transform=v.get("transform", ""),
                                    ffmpeg_args=v.get("ffmpeg_args", ""), path=v.get("path"),
                                    sha256=v.get("sha256"), size_bytes=v.get("size_bytes"),
                                    score=v.get("score"), delta=v.get("delta"),
                                    phash_hex=v.get("phash_hex"), phash_hamming=v.get("phash_hamming"),
                                    phash_similarity=v.get("phash_similarity"), reliable=v.get("reliable"),
                                    processing_ms=v.get("processing_ms")
                                ))

                    db.commit()

        # Link parent references
        for e_spec in case_spec.get("evidence", []):
            parent_ref = e_spec.get("reference_evidence_ref")
            if parent_ref and parent_ref in ev_map:
                ev_item = ev_map[e_spec["evidence_ref"]]
                parent_item = ev_map[parent_ref]
                if ev_item.reference_evidence_id != parent_item.id:
                    ev_item.reference_evidence_id = parent_item.id
        db.commit()

        # Comparisons
        for cmp_spec in case_spec.get("comparisons", []):
            ref_ref = cmp_spec["reference_evidence_ref"]
            deriv_ref = cmp_spec["derivative_evidence_ref"]
            if ref_ref in ev_map and deriv_ref in ev_map:
                p_ref = ev_map[ref_ref]
                p_deriv = ev_map[deriv_ref]
                existing_cmp = db.query(ForensicComparison).filter(
                    ForensicComparison.case_id == case.id,
                    ForensicComparison.reference_evidence_id == p_ref.id,
                    ForensicComparison.derivative_evidence_id == p_deriv.id
                ).first()
                if not existing_cmp:
                    db.add(ForensicComparison(
                        case_id=case.id,
                        reference_evidence_id=p_ref.id,
                        derivative_evidence_id=p_deriv.id,
                        visual_similarity=cmp_spec.get("visual_similarity"),
                        phash_distance=cmp_spec.get("phash_distance"),
                        ssim=cmp_spec.get("ssim"),
                        edge_delta=cmp_spec.get("edge_delta"),
                        noise_delta=cmp_spec.get("noise_delta"),
                        color_hist_delta=cmp_spec.get("color_hist_delta"),
                        ocr_overlap=cmp_spec.get("ocr_overlap"),
                        identifier_delta_json=cmp_spec.get("identifier_delta_json"),
                        ai_signal_delta=cmp_spec.get("ai_signal_delta"),
                        recapture_delta=cmp_spec.get("recapture_delta"),
                        c2pa_delta=cmp_spec.get("c2pa_delta"),
                        assessment=cmp_spec.get("assessment"),
                        limitations=cmp_spec.get("limitations"),
                        details_json=cmp_spec.get("details_json")
                    ))
        db.commit()

        # Graph Nodes & Edges
        if db.query(GraphNode).filter(GraphNode.case_id == case.id).count() == 0:
            for n in case_spec.get("graph_nodes", []):
                db.add(GraphNode(
                    case_id=case.id, node_key=n["node_key"], kind=n.get("kind"),
                    label=n.get("label"), sublabel=n.get("sublabel"),
                    extraction_method=n.get("extraction_method"),
                    confidence=n.get("confidence"), is_synthetic=bool(n.get("is_synthetic")),
                    attrs_json=n.get("attrs_json")
                ))
            db.commit()

        if db.query(GraphEdge).filter(GraphEdge.case_id == case.id).count() == 0:
            for ed in case_spec.get("graph_edges", []):
                db.add(GraphEdge(
                    case_id=case.id, src_key=ed["src_key"], dst_key=ed["dst_key"],
                    relation=ed.get("relation"), reason=ed.get("reason"),
                    evidence_ref=ed.get("evidence_ref"), observation=ed.get("observation"),
                    confidence=ed.get("confidence")
                ))
            db.commit()

        # Timeline Events
        if db.query(TimelineEvent).filter(TimelineEvent.case_id == case.id).count() == 0:
            for t in case_spec.get("timeline_events", []):
                db.add(TimelineEvent(
                    case_id=case.id, occurred_at=_parse_dt(t.get("occurred_at")),
                    title=t.get("title"), detail=t.get("detail"),
                    kind=t.get("kind", "evidence"), evidence_ref=t.get("evidence_ref"),
                    confidence=t.get("confidence"), is_synthetic=bool(t.get("is_synthetic"))
                ))
            db.commit()

        # Leads
        if db.query(Lead).filter(Lead.case_id == case.id).count() == 0:
            for l in case_spec.get("leads", []):
                db.add(Lead(
                    case_id=case.id, rank=l.get("rank"), priority=l.get("priority"),
                    title=l.get("title"), summary=l.get("summary"),
                    reasons_json=l.get("reasons_json"), limitation=l.get("limitation"),
                    status=l.get("status", "Potential investigative lead — human verification required.")
                ))
            db.commit()

        # Summary for case
        final_ev = db.query(Evidence).filter(Evidence.case_id == case.id).count()
        final_comp = db.query(ForensicComparison).filter(ForensicComparison.case_id == case.id).count()
        final_nodes = db.query(GraphNode).filter(GraphNode.case_id == case.id).count()
        final_tl = db.query(TimelineEvent).filter(TimelineEvent.case_id == case.id).count()
        final_leads = db.query(Lead).filter(Lead.case_id == case.id).count()

        results[case_ref] = {
            "evidence": final_ev,
            "comparisons": final_comp,
            "nodes": final_nodes,
            "timeline": final_tl,
            "leads": final_leads,
        }

    return results
