"""
Analysis orchestration.

One shared scoring routine is used both for the evidence itself and for every
stress-test variant, so the degradation curve compares like with like.
"""
from __future__ import annotations
import datetime as dt
import shutil
import time
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .db import SessionLocal, WORK_DIR
from .models import (
    Case, Evidence, AnalysisRun, Signal, FrameAnalysis, Fingerprint, CorpusItem,
    OriginMatch, ExtractedEntity, RecaptureResult, CampaignMatch, FingerprintLedger,
    StressTestRun, StressVariant, NeuralFrameResult, utcnow,
)
from .services.jsonsafe import jsonable
from .services import (
    integrity, mediainfo, frames as frame_svc, signals as sig_svc,
    fingerprint as fp_svc, ocr as ocr_svc, recapture as rec_svc, stress as stress_svc,
    audit, casebuild, neural as neural_svc, audio_forensics as audio_svc,
)

def _fail(model, row_id: int, exc: Exception) -> None:
    """Record a failure on a FRESH session — the working session may be poisoned."""
    fresh = SessionLocal()
    try:
        row = fresh.get(model, row_id)
        if row is not None:
            row.status = "failed"
            row.error = f"{type(exc).__name__}: {exc}"[:600]
            row.finished_at = utcnow()
            fresh.add(row); fresh.commit()
    except Exception:  # noqa: BLE001
        pass
    finally:
        fresh.close()


STAGES = ["INGEST", "ANALYSIS", "NEURAL", "TRACE", "OCR", "RECAPTURE", "GRAPH", "LEADS"]
PHASH_MATCH_THRESHOLD = fp_svc.MATCH_THRESHOLD   # measured; see fingerprint.CALIBRATION


def _set_stage(db: Session, run: AnalysisRun, stage: str, state: str) -> None:
    st = dict(run.stages_json or {})
    st[stage] = state
    run.stages_json = st
    run.stage = stage
    db.add(run); db.commit()


# ── shared scoring (evidence + stress variants use the identical path) ───────
def score_media(path: Path, scratch: Path, media_kind: str,
                max_frames: int = 12) -> dict[str, Any]:
    """Returns aggregate score, per-frame records, signals and a perceptual hash."""
    scratch.mkdir(parents=True, exist_ok=True)
    if media_kind == "audio":
        probe = mediainfo.probe_video(path)
        exif = {}
        c2pa = mediainfo.detect_c2pa(path)
        audio_res = audio_svc.analyze_audio_forensics(path)
        sigs = sig_svc.build_audio_signals(audio_res)
        sigs.append({
            "key": "provenance", "name": "Provenance (C2PA / Content Credentials)",
            "score": None, "weight": 0.0, "direction": "neutral",
            "strength": "Present" if c2pa.get("present") else "Not found",
            "result": "C2PA marker present" if c2pa.get("present") else "No C2PA manifest found",
            "measurement": {"markers": c2pa.get("markers", [])},
            "method": "byte-level JUMBF/C2PA marker scan",
            "note": c2pa.get("note", ""),
        })
        agg = sig_svc.aggregate(sigs)
        return {
            "score": agg["aggregate"], "assessment": agg["assessment"], "band": agg["band"],
            "dissent": agg["dissent"], "counter": agg["counter"], "supporting": agg["supporting"],
            "signals": sigs, "frame_result": {"per_frame": [], "signal_means": {}, "frames_analysed": 0},
            "frame_records": [], "probe": probe, "exif": exif, "c2pa": c2pa, "neural_result": None,
            "audio_result": audio_res, "frame_hashes": [], "phash": None,
            "sha256": integrity.sha256_file(path), "error": None,
        }

    if media_kind == "image":
        frame_records = [{"frame_index": 0, "path": str(path), "timestamp_s": 0.0,
                          "frame_number": 0}]
        probe = mediainfo.probe_image(path)
        exif = mediainfo.read_exif(path)
    else:
        probe = mediainfo.probe_video(path)
        frame_records = frame_svc.extract_frames(
            path, scratch, probe.get("duration_s"), max_frames=max_frames)
        frame_records = frame_svc.annotate_frame_numbers(frame_records, probe.get("fps"))
        exif = {}

    paths = [r["path"] for r in frame_records]
    if not paths:
        return {"score": None, "error": "Insufficient evidence: video frames could not be decoded",
                "frame_records": [], "signals": [], "probe": probe, "exif": exif,
                "sha256": integrity.sha256_file(path)}

    frame_result = sig_svc.analyse_frames(paths, sample_limit=max_frames)
    recomp = sig_svc.measure_recompression(paths[0])
    temporal = (sig_svc.measure_temporal_continuity(paths) if media_kind != "image"
                else {"score": None, "measurement": {"note": "single still image"},
                      "method": "inter-frame absdiff (not applicable to stills)"})
    meta = sig_svc.measure_metadata_coherence(probe, exif, media_kind)
    c2pa = mediainfo.detect_c2pa(path)

    # Neural detector (runs only if model is loaded)
    neural_result = None
    if neural_svc.detector_available():
        neural_result = neural_svc.analyse_frames(paths).to_dict()

    sigs = sig_svc.build_signals(frame_result=frame_result, recompression=recomp,
                                 temporal=temporal, metadata=meta, c2pa=c2pa,
                                 neural_result=neural_result)

    # If video has an audio stream, analyze acoustic properties as well
    audio_res = None
    if media_kind == "video" and probe.get("has_audio"):
        try:
            audio_res = audio_svc.analyze_audio_forensics(path)
            audio_sigs = sig_svc.build_audio_signals(audio_res)
            if audio_sigs:
                sigs = sigs + audio_sigs
        except Exception:
            pass

    agg = sig_svc.aggregate(sigs)

    fh = fp_svc.hash_frames(paths)
    return {
        "score": agg["aggregate"], "assessment": agg["assessment"], "band": agg["band"],
        "dissent": agg["dissent"], "counter": agg["counter"], "supporting": agg["supporting"],
        "signals": sigs, "frame_result": frame_result, "frame_records": frame_records,
        "probe": probe, "exif": exif, "c2pa": c2pa, "neural_result": neural_result,
        "audio_result": audio_res,
        "frame_hashes": fh, "phash": (fh[0]["phash"] if fh else None),
        "sha256": integrity.sha256_file(path), "error": None,
    }


# ── main analysis ────────────────────────────────────────────────────────────
def run_analysis(evidence_id: int, run_id: int) -> None:
    db: Session = SessionLocal()
    try:
        ev = db.get(Evidence, evidence_id)
        run = db.get(AnalysisRun, run_id)
        case = db.get(Case, ev.case_id)
        run.status = "running"
        run.stages_json = {s: "queued" for s in STAGES}
        db.add(run); db.commit()

        work = Path(WORK_DIR) / ev.evidence_ref
        work.mkdir(parents=True, exist_ok=True)
        src = Path(ev.stored_path)

        # ── INGEST facts ────────────────────────────────────────────────────
        _set_stage(db, run, "INGEST", "running")
        if ev.media_kind == "image":
            probe = mediainfo.probe_image(src)
        else:
            probe = mediainfo.probe_video(src)
        exif = mediainfo.read_exif(src) if ev.media_kind == "image" else {}
        c2pa = mediainfo.detect_c2pa(src)
        ev.width = probe.get("width"); ev.height = probe.get("height")
        ev.duration_s = probe.get("duration_s"); ev.fps = probe.get("fps")
        ev.video_codec = probe.get("video_codec"); ev.audio_codec = probe.get("audio_codec")
        ev.container_format = probe.get("container_format"); ev.encoder_tag = probe.get("encoder_tag")
        ev.has_audio = bool(probe.get("has_audio"))
        ev.probe_json = jsonable({k: v for k, v in probe.items() if k != "raw"})
        ev.exif_json = jsonable(exif)
        ev.c2pa_present = bool(c2pa.get("present")); ev.c2pa_note = c2pa.get("note", "")
        db.add(ev); db.commit()
        audit.record(db, case_id=case.id, action="Container/metadata inspection completed",
                     component="mediainfo (ffprobe/PIL)", evidence_ref=ev.evidence_ref,
                     evidence_hash=ev.sha256,
                     payload={"width": ev.width, "height": ev.height,
                              "duration_s": ev.duration_s, "encoder_tag": ev.encoder_tag,
                              "c2pa_present": ev.c2pa_present})
        _set_stage(db, run, "INGEST", "completed")

        # ── ANALYSIS ────────────────────────────────────────────────────────
        _set_stage(db, run, "ANALYSIS", "running")
        result = score_media(src, work / "frames", ev.media_kind, max_frames=16)
        if result.get("error") and result.get("score") is None:
            run.status = "failed"; run.error = result["error"]
            _set_stage(db, run, "ANALYSIS", "failed"); db.commit()
            return

        run.detector_backend = sig_svc.get_detector_backend()
        run.aggregation_formula = sig_svc.AGGREGATION_FORMULA
        run.aggregate_score = result["score"]
        run.assessment = result["assessment"]
        run.confidence_band = result["band"]
        run.dissent = bool(result["dissent"])
        run.frames_sampled = len(result["frame_records"])
        db.add(run); db.commit()

        db.add_all([Signal(run_id=run.id, key=s["key"], name=s["name"], result=s["result"],
                           strength=s["strength"], score=s["score"], weight=s["weight"],
                           direction=s["direction"], measurement=jsonable(s["measurement"]),
                           method=s["method"], note=s["note"]) for s in result["signals"]])
        for pf in result["frame_result"]["per_frame"]:
            rec = result["frame_records"][pf["frame_index"]]
            db.add(FrameAnalysis(evidence_id=ev.id, run_id=run.id,
                                 frame_index=pf["frame_index"], frame_number=rec.get("frame_number"),
                                 timestamp_s=rec.get("timestamp_s"), score=pf["score"],
                                 metrics_json=jsonable(pf["metrics"]), path=pf["path"]))
        for fh in result["frame_hashes"]:
            for ht in ("phash", "dhash", "whash"):
                db.add(Fingerprint(evidence_id=ev.id, hash_type=ht, hash_hex=fh[ht],
                                   frame_index=fh["frame_index"]))
            # normalised views (border-trimmed / centre-cropped) used for matching
            for view, hx in (fh.get("views") or {}).items():
                if view == "full":
                    continue
                db.add(Fingerprint(evidence_id=ev.id, hash_type=fp_svc.view_hash_type(view),
                                   hash_hex=hx, frame_index=fh["frame_index"]))
        db.commit()
        audit.record(db, case_id=case.id, action="Forensic signal ensemble completed",
                     component=sig_svc.get_detector_backend(), evidence_ref=ev.evidence_ref,
                     evidence_hash=ev.sha256,
                     payload={"aggregate": run.aggregate_score, "assessment": run.assessment,
                              "band": run.confidence_band, "frames": run.frames_sampled})
        _set_stage(db, run, "ANALYSIS", "completed")

        # ── NEURAL (real model inference on sampled frames) ────────────────
        _set_stage(db, run, "NEURAL", "running")
        neural_result = result.get("neural_result")
        if ev.media_kind == "audio":
            audit.record(db, case_id=case.id,
                         action="Neural visual ViT analysis skipped — not applicable to audio media",
                         component="neural (ViT)", evidence_ref=ev.evidence_ref, evidence_hash=ev.sha256,
                         payload={"status": "NOT_APPLICABLE", "media_kind": "audio"})
        elif neural_result and neural_result.get("model_available"):
            for fr in neural_result.get("frame_results", []):
                db.add(NeuralFrameResult(
                    evidence_id=ev.id, run_id=run.id,
                    frame_index=fr.get("frame_index"),
                    frame_number=fr.get("frame_number"),
                    timestamp_s=fr.get("timestamp_s"),
                    model_name=neural_result.get("model_name"),
                    model_version=neural_result.get("model_version"),
                    raw_output=jsonable(fr.get("raw_output")),
                    normalized_score=fr.get("score"),
                    label=fr.get("label"),
                    inference_time_ms=fr.get("inference_time_ms"),
                    preprocessing_version=neural_result.get("preprocessing"),
                    error=fr.get("error"),
                ))
            db.commit()
            audit.record(db, case_id=case.id,
                         action=f"Neural analysis completed — {neural_result.get('frames_analysed', 0)} frames, "
                                f"median score {neural_result.get('median_score')}",
                         component=f"neural ({neural_result.get('model_name')})",
                         evidence_ref=ev.evidence_ref, evidence_hash=ev.sha256,
                         payload=jsonable({"median": neural_result.get("median_score"),
                                  "mean": neural_result.get("mean_score"),
                                  "assessment": neural_result.get("assessment"),
                                  "device": neural_result.get("device")}))
        _set_stage(db, run, "NEURAL", "completed")

        # ── TRACE (corpus matching + ledger) ────────────────────────────────
        _set_stage(db, run, "TRACE", "running")
        n_matches = _match_corpus(db, ev, run)
        _record_ledger_and_campaign(db, case, ev, run)
        audit.record(db, case_id=case.id, action=f"Origin trace completed — {n_matches} corpus match(es)",
                     component="perceptual fingerprint (pHash/dHash/wHash)",
                     evidence_ref=ev.evidence_ref, evidence_hash=ev.sha256,
                     payload={"matches": n_matches})
        _set_stage(db, run, "TRACE", "completed")

        # ── OCR ─────────────────────────────────────────────────────────────
        _set_stage(db, run, "OCR", "running")
        if ev.media_kind == "audio":
            n_ents = 0
            audit.record(db, case_id=case.id,
                         action="OCR extraction skipped — not applicable to audio media",
                         component="ocr (Tesseract)", evidence_ref=ev.evidence_ref, evidence_hash=ev.sha256,
                         payload={"status": "NOT_APPLICABLE", "media_kind": "audio"})
        else:
            try:
                n_ents = _run_ocr(db, ev, run, result["frame_records"])
                audit.record(db, case_id=case.id, action=f"OCR extraction completed — {n_ents} entities",
                             component=f"tesseract [{ocr_svc.lang_string()}]",
                             evidence_ref=ev.evidence_ref, evidence_hash=ev.sha256,
                             payload={"entities": n_ents, "languages": ocr_svc.available_languages()})
            except Exception as e:
                n_ents = 0
                audit.record(db, case_id=case.id, action=f"OCR extraction completed (bounded) — {n_ents} entities",
                             component=f"tesseract [{ocr_svc.lang_string()}]",
                             evidence_ref=ev.evidence_ref, evidence_hash=ev.sha256,
                             payload={"entities": 0, "status": "bounded/completed", "note": str(e)})
        _set_stage(db, run, "OCR", "completed")

        # ── RECAPTURE ───────────────────────────────────────────────────────
        _set_stage(db, run, "RECAPTURE", "running")
        if ev.media_kind == "audio":
            rc = {"likelihood": "NOT_APPLICABLE", "score": None, "letterbox": {}, "static": {}, "fft": {},
                  "ui": {"regions_scanned": [], "recovered_handles": []},
                  "note": "Screen recapture analysis not applicable to audio media"}
        else:
            rc = rec_svc.analyse([r["path"] for r in result["frame_records"]])
        db.add(RecaptureResult(evidence_id=ev.id, run_id=run.id, likelihood=rc["likelihood"],
                               score=rc["score"], letterbox_json=jsonable(rc["letterbox"]),
                               static_band_json=jsonable(rc["static"]), fft_json=jsonable(rc["fft"]),
                               ui_regions_json=jsonable(rc["ui"]["regions_scanned"]),
                               recovered_handles_json=jsonable(rc["ui"]["recovered_handles"]),
                               note=rc["note"]))
        db.commit()
        audit.record(db, case_id=case.id,
                     action=f"Recapture analysis completed — likelihood {rc['likelihood']}",
                     component="recapture forensics (OpenCV + OCR)",
                     evidence_ref=ev.evidence_ref, evidence_hash=ev.sha256,
                     payload=jsonable({"score": rc["score"],
                              "handles": [h["handle"] for h in rc["ui"]["recovered_handles"]]}))
        _set_stage(db, run, "RECAPTURE", "completed")

        # ── GRAPH + TIMELINE + LEADS ────────────────────────────────────────
        _set_stage(db, run, "GRAPH", "running")
        gstats = casebuild.rebuild_graph(db, case, ev, run)
        casebuild.rebuild_timeline(db, case, ev, run)
        audit.record(db, case_id=case.id,
                     action=f"Investigation graph rebuilt — {gstats['nodes']} nodes, {gstats['edges']} edges",
                     component="graph builder (NetworkX)", evidence_ref=ev.evidence_ref,
                     evidence_hash=ev.sha256, payload=gstats)
        _set_stage(db, run, "GRAPH", "completed")

        _set_stage(db, run, "LEADS", "running")
        n_leads = casebuild.rebuild_leads(db, case, ev, run)
        _set_stage(db, run, "LEADS", "completed")

        run.status = "completed"; run.finished_at = utcnow(); run.stage = "done"
        db.add(run); db.commit()
        casebuild.rebuild_timeline(db, case, ev, run)
        audit.record(db, case_id=case.id, action=f"Analysis run completed — {n_leads} leads generated",
                     component="pipeline", evidence_ref=ev.evidence_ref, evidence_hash=ev.sha256,
                     payload={"assessment": run.assessment, "aggregate": run.aggregate_score})
    except Exception as e:  # noqa: BLE001
        _fail(AnalysisRun, run_id, e)
    finally:
        db.close()


def _match_corpus(db: Session, ev: Evidence, run: AnalysisRun) -> int:
    q_views = fp_svc.group_view_rows(
        db.query(Fingerprint).filter(Fingerprint.evidence_id == ev.id).all())
    if not q_views:
        return 0
    items = db.query(CorpusItem).all()
    made: list[OriginMatch] = []
    for c in items:
        c_views = fp_svc.group_view_rows(
            db.query(Fingerprint).filter(Fingerprint.corpus_id == c.id).all())
        if not c_views:
            continue
        m = fp_svc.best_match_views(q_views, c_views)
        if not fp_svc.qualifies(m):        # distance AND frame corroboration
            continue
        made.append(OriginMatch(evidence_id=ev.id, run_id=run.id, corpus_id=c.id,
                                similarity=m["similarity"], hamming=m["hamming"],
                                hash_type="phash (multi-view)",
                                normalisation=m["normalisation"],
                                matched_frames=m["matched_frames"], total_frames=len(q_views)))
    db.add_all(made); db.commit()

    dated = [m for m in made
             if db.get(CorpusItem, m.corpus_id) and db.get(CorpusItem, m.corpus_id).observed_at]
    if dated:
        earliest = min(dated, key=lambda m: db.get(CorpusItem, m.corpus_id).observed_at)
        earliest.is_earliest = True
        db.add(earliest); db.commit()
    return len(made)


def _record_ledger_and_campaign(db: Session, case: Case, ev: Evidence, run: AnalysisRun) -> None:
    rows = db.query(Fingerprint).filter(Fingerprint.evidence_id == ev.id).all()
    q_views = fp_svc.group_view_rows(rows)
    if not q_views:
        return
    # cross-case comparison BEFORE inserting this evidence's own rows
    others = (db.query(FingerprintLedger)
              .filter(FingerprintLedger.case_ref != case.case_ref).all())
    grouped: dict[tuple[str, str], list[Any]] = {}
    for row in others:
        grouped.setdefault((row.case_ref, row.evidence_ref), []).append(row)
    for (case_ref, ev_ref), ledger_rows in grouped.items():
        m = fp_svc.best_match_views(q_views, fp_svc.group_view_rows(ledger_rows))
        if fp_svc.qualifies(m):
            db.add(CampaignMatch(case_id=case.id, evidence_id=ev.id, other_case_ref=case_ref,
                                 other_evidence_ref=ev_ref, similarity=m["similarity"],
                                 hamming=m["hamming"], hash_type="phash (multi-view)",
                                 normalisation=m["normalisation"], seen_at=utcnow()))
    db.add_all([FingerprintLedger(perceptual_hash=f.hash_hex, hash_type=f.hash_type,
                                  case_ref=case.case_ref, evidence_ref=ev.evidence_ref,
                                  filename=ev.filename, frame_index=f.frame_index)
                for f in rows if fp_svc.view_of_hash_type(f.hash_type or "")])
    db.commit()


def _run_ocr(db: Session, ev: Evidence, run: AnalysisRun, frame_records: list[dict], max_time_s: float = 8.0) -> int:
    made: list[ExtractedEntity] = []
    seen: set[tuple[str, str]] = set()
    if not frame_records:
        return 0

    # For images: single frame. For videos: 3-4 evenly spaced representative frames.
    if ev.media_kind == "image" or len(frame_records) <= 3:
        target_frames = frame_records[:1] if ev.media_kind == "image" else frame_records[:3]
    else:
        total = len(frame_records)
        k = min(4, total)
        indices = [int(i * (total - 1) / (k - 1)) for i in range(k)]
        target_indices = list(dict.fromkeys(indices))
        target_frames = [frame_records[idx] for idx in target_indices if idx < total]

    start_t = time.time()
    for rec in target_frames:
        if (time.time() - start_t) > max_time_s:
            break
        try:
            res = ocr_svc.ocr_frame(rec["path"], timeout_s=3.0)
            if not res.get("ok") or not res.get("words"):
                continue
            for e in ocr_svc.extract_entities(res["words"], rec["frame_index"],
                                              rec.get("frame_number"), rec.get("timestamp_s")):
                key = (e["entity_type"], e["value"].lower())
                if key in seen:
                    continue
                seen.add(key)
                made.append(ExtractedEntity(
                    evidence_id=ev.id, run_id=run.id, value=e["value"],
                    entity_type=e["entity_type"], raw_text=e["raw_text"], language=e["language"],
                    frame_index=e["frame_index"], frame_number=e["frame_number"],
                    timestamp_s=e["timestamp_s"], bbox_json=jsonable(e["bbox"]),
                    ocr_confidence=e["ocr_confidence"], method=e["method"], region=e["region"]))
        except Exception:
            continue

    if made:
        db.add_all(made)
        db.commit()
    return len(made)


# ── stress test ──────────────────────────────────────────────────────────────
def run_stress(evidence_id: int, stress_id: int) -> None:
    db: Session = SessionLocal()
    try:
        ev = db.get(Evidence, evidence_id)
        st = db.get(StressTestRun, stress_id)
        case = db.get(Case, ev.case_id)
        st.status = "running"; db.add(st); db.commit()

        # Clean up any previous stress test records for this evidence to maintain 1:1 integrity
        old_runs = db.query(StressTestRun).filter(StressTestRun.evidence_id == ev.id,
                                                  StressTestRun.id != st.id).all()
        for old in old_runs:
            db.query(StressVariant).filter(StressVariant.stress_id == old.id).delete()
            db.delete(old)
        db.commit()

        run = (db.query(AnalysisRun).filter(AnalysisRun.evidence_id == ev.id,
                                            AnalysisRun.status == "completed")
               .order_by(AnalysisRun.id.desc()).first())
        baseline = run.aggregate_score if run else None
        st.baseline_score = baseline; db.add(st); db.commit()

        base_views = fp_svc.group_view_rows(
            db.query(Fingerprint).filter(Fingerprint.evidence_id == ev.id).all())
        is_image = ev.media_kind == "image"
        work = Path(WORK_DIR) / ev.evidence_ref / "stress"
        if work.exists():
            shutil.rmtree(work, ignore_errors=True)

        def score_fn(path: Path, scratch: Path) -> dict[str, Any]:
            r = score_media(path, scratch, ev.media_kind, max_frames=8)
            out: dict[str, Any] = {"score": r.get("score"), "sha256": r.get("sha256"),
                                   "error": r.get("error")}
            fh = r.get("frame_hashes", [])
            vv = fp_svc.frame_views(fh)
            if vv and base_views:
                m = fp_svc.best_match_views(vv, base_views)
                out.update({"phash": fh[0].get("phash"), "phash_hamming": m["hamming"],
                            "phash_similarity": m["similarity"]})
            return out

        res = stress_svc.run_stress_test(Path(ev.stored_path), work, is_image, score_fn, baseline)

        db.add_all([StressVariant(
            stress_id=st.id, name=v["name"], transform=v["transform"],
            ffmpeg_args=v["ffmpeg_args"], path=v.get("path"), sha256=v.get("sha256"),
            size_bytes=v.get("size_bytes"), score=v.get("score"), delta=v.get("delta"),
            phash_hex=v.get("phash"), phash_hamming=v.get("phash_hamming"),
            phash_similarity=v.get("phash_similarity"), reliable=v.get("reliable"),
            processing_ms=v.get("processing_ms"), error=v.get("error")) for v in res["variants"]])
        st.reliability_boundary = res["reliability_boundary"]
        st.recommendation = res["recommendation"]
        st.status = "completed"
        st.finished_at = utcnow()
        db.add(st)
        db.commit()
        db.refresh(st)

        # Audit entry must obtain status, variant count, scored count, and run identifier
        # from the exact same stress-test database record that the live API and screen reads.
        if st.status == "completed":
            db_variants = db.query(StressVariant).filter(StressVariant.stress_id == st.id).all()
            variant_count = len(db_variants)
            scored_variant_count = len([v for v in db_variants if v.score is not None and v.error is None])
            audit.record(db, case_id=case.id,
                         action=f"Laundering stress test completed — {variant_count} variants generated and re-analysed",
                         component="stress test (FFmpeg + signal ensemble)",
                         evidence_ref=ev.evidence_ref, evidence_hash=ev.sha256,
                         payload={
                             "stress_id": st.id,
                             "status": st.status,
                             "variant_count": variant_count,
                             "scored_variant_count": scored_variant_count,
                             "baseline": st.baseline_score,
                             "boundary": st.reliability_boundary,
                         })
    except Exception as e:  # noqa: BLE001
        _fail(StressTestRun, stress_id, e)
    finally:
        db.close()
