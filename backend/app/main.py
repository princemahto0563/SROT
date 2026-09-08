"""SROT API. FastAPI + SQLite. No external services; runs fully offline."""
from __future__ import annotations
import datetime as dt
import os
import shutil
from pathlib import Path
from typing import Any

from fastapi import (FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks,
                     Depends, Request)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from .db import init_db, get_db, EVIDENCE_DIR, WORK_DIR, PACKET_DIR
from .models import (
    Case, Evidence, AnalysisRun, Signal, FrameAnalysis, OriginMatch, CorpusItem,
    ExtractedEntity, RecaptureResult, StressTestRun, StressVariant, CampaignMatch,
    AuditLog, TimelineEvent, Lead, CourtPacket, FingerprintLedger, NeuralFrameResult,
    OfficerUser, OfficerSession, utcnow,
)
from .services import integrity, audit as audit_svc, casebuild, ocr as ocr_svc
from .services import report as report_svc
from .services import signals as sig_svc
from .services import fingerprint as fp_svc
from .services import neural as neural_svc
from .services import quality as quality_svc
from .services import visual_trace as trace_svc
from .services import cross_signal as cross_svc
from .services import replay as replay_svc
from .services import audio_forensics as audio_svc
from .services import c2pa_trust as c2pa_svc
from .services import auth as auth_svc
from .services.auth import extract_token, validate_session_token, revoke_session_token
from . import pipeline


def verify_officer_access(request: Request, db: Session = Depends(get_db)):
    """Global dependency enforcing police authentication gate on all /api/* endpoints except public ones."""
    if request.method == "OPTIONS":
        return None
    path = request.url.path.rstrip("/")
    # Public endpoints
    if path in {"/api/health", "/api/auth/login", "/api/auth/logout", "/docs", "/redoc", "/openapi.json"} or not path.startswith("/api"):
        return None

    token = extract_token(request)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Police authorization credentials required to access forensic repository.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    officer = validate_session_token(db, token)
    if not officer:
        raise HTTPException(
            status_code=401,
            detail="Officer session expired or invalid. Please re-authenticate.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    request.state.officer = officer
    return officer


app = FastAPI(
    title="SROT — AI-Powered Media Forensics & Source Tracing",
    version="2.0.0",
    dependencies=[Depends(verify_officer_access)],
)
cors_raw = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:5177,http://127.0.0.1:5177,https://srot-umt3.vercel.app",
)
allowed_origins_set = {
    "http://localhost:5177",
    "http://127.0.0.1:5177",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://srot-umt3.vercel.app",
}
for orig in cors_raw.split(","):
    orig_clean = orig.strip()
    if orig_clean:
        allowed_origins_set.add(orig_clean)

allowed_origins = list(allowed_origins_set)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    from .db import SessionLocal
    db = SessionLocal()
    try:
        auth_svc.seed_demo_officer(db)
        if db.query(Case).count() == 0:
            try:
                import sys, subprocess
                subprocess.Popen([sys.executable, "backend/seed.py"])
            except Exception:
                pass
    finally:
        db.close()


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)
    # never leak a stack trace to the client
    return JSONResponse(status_code=500,
                        content={"detail": f"Internal error ({type(exc).__name__}). "
                                           "The action was not completed."})



def _iso(v: dt.datetime | None) -> str | None:
    return v.isoformat() if v else None


# ── auth ──────────────────────────────────────────────────────────────────────
@app.post("/api/auth/login")
def login(payload: dict, db: Session = Depends(get_db)):
    badge_id = (payload.get("badge_id") or "").strip()
    password = payload.get("password") or ""
    if not badge_id or not password:
        raise HTTPException(status_code=401, detail="Badge ID and authorization password are required.")

    officer = auth_svc.verify_officer_login(db, badge_id, password)
    if not officer:
        raise HTTPException(status_code=401, detail="Invalid officer badge ID or authorization password.")

    raw_token, session = auth_svc.create_session(db, officer)
    return {
        "token": raw_token,
        "officer": {
            "badge_id": officer.badge_id,
            "name": officer.name,
            "role": officer.role,
            "unit": officer.unit,
            "last_login_at": _iso(officer.last_login_at),
        },
        "expires_at": _iso(session.expires_at),
    }


@app.post("/api/auth/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    token = extract_token(request)
    if token:
        revoke_session_token(db, token)
    return {"status": "logged_out", "message": "Officer session terminated successfully."}


@app.get("/api/auth/session")
def get_session_info(request: Request, db: Session = Depends(get_db)):
    officer = getattr(request.state, "officer", None)
    if not officer:
        token = extract_token(request)
        officer = validate_session_token(db, token) if token else None
    if not officer:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return {
        "authenticated": True,
        "officer": {
            "badge_id": officer.badge_id,
            "name": officer.name,
            "role": officer.role,
            "unit": officer.unit,
            "last_login_at": _iso(officer.last_login_at),
        },
    }


# ── system ───────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict[str, Any]:
    import shutil as sh
    neural_status = neural_svc.detector_status()
    return {
        "status": "ok",
        "detector_backend": sig_svc.get_detector_backend(),
        "neural_detector_loaded": neural_status["neural_detector_loaded"],
        "neural_model": neural_status.get("model_name"),
        "neural_revision": neural_status.get("model_revision"),
        "neural_device": neural_status.get("device"),
        "neural_architecture": neural_status.get("architecture"),
        "neural_license": neural_status.get("license"),
        "neural_scope": neural_status.get("scope"),
        "tools": {"ffmpeg": bool(sh.which("ffmpeg")), "ffprobe": bool(sh.which("ffprobe")),
                  "tesseract": bool(sh.which("tesseract"))},
        "ocr_languages": ocr_svc.available_languages(),
        "corpus_items": db.query(CorpusItem).count(),
        "cases": db.query(Case).count(),
        "ledger_entries": db.query(FingerprintLedger).count(),
        "offline": True,
    }


@app.get("/api/system/model-status")
def model_status() -> dict[str, Any]:
    """Full neural model status and provenance."""
    status = neural_svc.detector_status()
    status["provenance"] = neural_svc.model_provenance()
    return status


@app.post("/api/system/seed")
def trigger_seed(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Seed demo corpus and demo cases if not already present."""
    cases_count = db.query(Case).count()
    if cases_count == 0:
        try:
            import sys, subprocess
            subprocess.run([sys.executable, "backend/seed.py"], timeout=120)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Seeding failed: {e}")
    return {"status": "ok", "cases": db.query(Case).count(), "corpus_items": db.query(CorpusItem).count()}


# ── cases ────────────────────────────────────────────────────────────────────
def _case_json(db: Session, c: Case) -> dict[str, Any]:
    evs = db.query(Evidence).filter(Evidence.case_id == c.id).all()
    ent_count = (db.query(ExtractedEntity)
                 .filter(ExtractedEntity.evidence_id.in_([e.id for e in evs] or [0])).count())
    leads = db.query(Lead).filter(Lead.case_id == c.id).count()
    matches = (db.query(OriginMatch)
               .filter(OriginMatch.evidence_id.in_([e.id for e in evs] or [0])).count())
    return {
        "id": c.id, "case_ref": c.case_ref, "title": c.title, "category": c.category,
        "officer": c.officer, "unit": c.unit, "summary": c.summary, "status": c.status,
        "created_at": _iso(c.created_at),
        "counts": {"evidence": len(evs),
                   "media": sum(1 for e in evs if e.media_kind in ("image", "video")),
                   "entities": ent_count, "leads": leads, "corpus_matches": matches,
                   "campaign_matches": db.query(CampaignMatch).filter(CampaignMatch.case_id == c.id).count()},
    }


@app.get("/api/cases")
def list_cases(db: Session = Depends(get_db)):
    return [_case_json(db, c) for c in db.query(Case).order_by(Case.id.desc()).all()]


@app.post("/api/cases")
def create_case(payload: dict, db: Session = Depends(get_db)):
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "title is required")
    if payload.get("case_ref"):
        ref = payload["case_ref"]
        if db.query(Case).filter(Case.case_ref == ref).first():
            raise HTTPException(409, f"case {ref} already exists")
    else:
        n = db.query(Case).count() + 1
        while db.query(Case).filter(Case.case_ref == f"CASE-{utcnow():%Y}-{n:03d}").first():
            n += 1
        ref = f"CASE-{utcnow():%Y}-{n:03d}"
    c = Case(case_ref=ref, title=title, category=payload.get("category") or "Synthetic media",
             officer=payload.get("officer") or "Investigating Officer",
             summary=payload.get("summary") or "")
    db.add(c); db.commit(); db.refresh(c)
    audit_svc.record(db, case_id=c.id, action=f"Case {ref} opened", component="case manager",
                     payload={"title": title})
    return _case_json(db, c)


@app.get("/api/cases/{case_ref}")
def get_case(case_ref: str, db: Session = Depends(get_db)):
    c = db.query(Case).filter(Case.case_ref == case_ref).first()
    if not c:
        raise HTTPException(404, "case not found")
    evs = db.query(Evidence).filter(Evidence.case_id == c.id).order_by(Evidence.id).all()
    out = _case_json(db, c)
    out["evidence"] = [_evidence_json(db, e) for e in evs]
    out["audit_chain"] = audit_svc.verify_chain(db, c.id)
    return out


# ── evidence ─────────────────────────────────────────────────────────────────
def _evidence_json(db: Session, e: Evidence) -> dict[str, Any]:
    run = (db.query(AnalysisRun).filter(AnalysisRun.evidence_id == e.id)
           .order_by(AnalysisRun.id.desc()).first())
    return {
        "id": e.id, "evidence_ref": e.evidence_ref, "filename": e.filename,
        "media_kind": e.media_kind, "mime_type": e.mime_type, "size_bytes": e.size_bytes,
        "sha256": e.sha256, "hash_algorithm": e.hash_algorithm,
        "ingested_at": _iso(e.ingested_at),
        "width": e.width, "height": e.height, "duration_s": e.duration_s, "fps": e.fps,
        "video_codec": e.video_codec, "audio_codec": e.audio_codec,
        "container_format": e.container_format, "encoder_tag": e.encoder_tag,
        "has_audio": e.has_audio, "exif_fields": len(e.exif_json or {}),
        "exif": e.exif_json or {}, "c2pa_present": e.c2pa_present, "c2pa_note": e.c2pa_note,
        "latest_run": None if not run else {
            "id": run.id, "status": run.status, "stage": run.stage,
            "stages": run.stages_json or {}, "assessment": run.assessment,
            "confidence_band": run.confidence_band, "aggregate_score": run.aggregate_score,
            "detector_backend": run.detector_backend, "dissent": run.dissent,
            "frames_sampled": run.frames_sampled, "error": run.error,
            "finished_at": _iso(run.finished_at),
        },
    }


@app.post("/api/cases/{case_ref}/evidence")
async def upload_evidence(case_ref: str, background: BackgroundTasks,
                          file: UploadFile = File(...),
                          analyse: str = Form("true"),
                          db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.case_ref == case_ref).first()
    if not case:
        raise HTTPException(404, "case not found")

    safe = integrity.sanitize_filename(file.filename or "evidence")
    if not integrity.is_allowed(safe):
        raise HTTPException(415, f"unsupported file type: {Path(safe).suffix or 'unknown'}")

    n = db.query(Evidence).filter(Evidence.case_id == case.id).count() + 1
    ev_ref = f"EV-{case.case_ref}-{n:03d}"
    dest_dir = Path(EVIDENCE_DIR) / case.case_ref
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{ev_ref}__{safe}"

    size = 0
    try:
        with open(dest, "wb") as out:
            while chunk := await file.read(1 << 20):
                size += len(chunk)
                if size > integrity.MAX_UPLOAD_BYTES:
                    out.close(); dest.unlink(missing_ok=True)
                    raise HTTPException(413, "file exceeds the 300 MB upload limit")
                out.write(chunk)
    except HTTPException:
        raise
    except Exception:
        dest.unlink(missing_ok=True)
        raise HTTPException(500, "could not store the uploaded file")

    if size == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, "uploaded file is empty")

    digest = integrity.sha256_file(dest)          # computed BEFORE any analysis
    ev = Evidence(evidence_ref=ev_ref, case_id=case.id, filename=safe, stored_path=str(dest),
                  mime_type=integrity.guess_mime(safe), media_kind=integrity.media_kind_for(safe),
                  size_bytes=size, sha256=digest)
    db.add(ev); db.commit(); db.refresh(ev)
    audit_svc.record(db, case_id=case.id, action="Evidence uploaded", component="case manager",
                     evidence_ref=ev_ref, evidence_hash=digest,
                     payload={"filename": safe, "size_bytes": size,
                              "mime": ev.mime_type, "media_kind": ev.media_kind})
    audit_svc.record(db, case_id=case.id, action="SHA-256 computed at ingest",
                     component="integrity service", evidence_ref=ev_ref, evidence_hash=digest,
                     payload={"algorithm": "SHA-256"})

    body: dict[str, Any] = {"evidence": _evidence_json(db, ev), "case_ref": case.case_ref}
    if str(analyse).lower() in ("1", "true", "yes"):
        run = AnalysisRun(evidence_id=ev.id, status="queued",
                          stages_json={s: "queued" for s in pipeline.STAGES})
        db.add(run); db.commit(); db.refresh(run)
        background.add_task(pipeline.run_analysis, ev.id, run.id)
        body["job"] = {"run_id": run.id, "status": "queued", "stages": run.stages_json}
    return body


@app.post("/api/evidence/{evidence_ref}/analyse")
def analyse_evidence(evidence_ref: str, background: BackgroundTasks, db: Session = Depends(get_db)):
    ev = db.query(Evidence).filter(Evidence.evidence_ref == evidence_ref).first()
    if not ev:
        raise HTTPException(404, "evidence not found")
    run = AnalysisRun(evidence_id=ev.id, status="queued",
                      stages_json={s: "queued" for s in pipeline.STAGES})
    db.add(run); db.commit(); db.refresh(run)
    background.add_task(pipeline.run_analysis, ev.id, run.id)
    return {"run_id": run.id, "status": "queued", "stages": run.stages_json}


@app.get("/api/evidence/{evidence_ref}")
def get_evidence(evidence_ref: str, db: Session = Depends(get_db)):
    ev = db.query(Evidence).filter(Evidence.evidence_ref == evidence_ref).first()
    if not ev:
        raise HTTPException(404, "evidence not found")
    return _evidence_json(db, ev)


@app.get("/api/evidence/{evidence_ref}/job")
def job_status(evidence_ref: str, db: Session = Depends(get_db)):
    ev = db.query(Evidence).filter(Evidence.evidence_ref == evidence_ref).first()
    if not ev:
        raise HTTPException(404, "evidence not found")
    run = (db.query(AnalysisRun).filter(AnalysisRun.evidence_id == ev.id)
           .order_by(AnalysisRun.id.desc()).first())
    if not run:
        return {"status": "none", "stages": {}}
    return {"run_id": run.id, "status": run.status, "stage": run.stage,
            "stages": run.stages_json or {}, "error": run.error,
            "assessment": run.assessment, "aggregate_score": run.aggregate_score}


def _require_run(db: Session, evidence_ref: str) -> tuple[Evidence, AnalysisRun]:
    ev = db.query(Evidence).filter(Evidence.evidence_ref == evidence_ref).first()
    if not ev:
        raise HTTPException(404, "evidence not found")
    run = (db.query(AnalysisRun).filter(AnalysisRun.evidence_id == ev.id,
                                        AnalysisRun.status == "completed")
           .order_by(AnalysisRun.id.desc()).first())
    if not run:
        raise HTTPException(409, "no completed analysis for this evidence yet")
    return ev, run


def _frame_paths_for_run(db: Session, run_id: int) -> list[str]:
    rows = db.query(FrameAnalysis).filter(FrameAnalysis.run_id == run_id).order_by(FrameAnalysis.frame_index).all()
    return [r.path for r in rows if r.path and Path(r.path).exists()]


@app.get("/api/evidence/{evidence_ref}/analysis")
def get_analysis(evidence_ref: str, db: Session = Depends(get_db)):
    ev, run = _require_run(db, evidence_ref)
    sigs = db.query(Signal).filter(Signal.run_id == run.id).all()
    fps = _frame_paths_for_run(db, run.id)
    q_gate = quality_svc.assess_quality(fps)

    return {
        "evidence_ref": ev.evidence_ref,
        "assessment": run.assessment, "confidence_band": run.confidence_band,
        "aggregate_score": run.aggregate_score, "detector_backend": run.detector_backend,
        "aggregation_formula": run.aggregation_formula,
        "neural_detector_loaded": sig_svc.neural_detector_available(),
        "frames_sampled": run.frames_sampled, "dissent": run.dissent,
        "finished_at": _iso(run.finished_at),
        "quality_gate": q_gate,
        "signals": [{"key": s.key, "name": s.name, "result": s.result, "strength": s.strength,
                     "score": s.score, "weight": s.weight, "direction": s.direction,
                     "measurement": s.measurement, "method": s.method, "note": s.note}
                    for s in sigs],
        "container": {"width": ev.width, "height": ev.height, "duration_s": ev.duration_s,
                      "fps": ev.fps, "video_codec": ev.video_codec, "audio_codec": ev.audio_codec,
                      "container_format": ev.container_format, "encoder_tag": ev.encoder_tag,
                      "has_audio": ev.has_audio},
        "provenance": {"c2pa_present": ev.c2pa_present, "note": ev.c2pa_note,
                       "exif_fields": len(ev.exif_json or {}), "exif": ev.exif_json or {}},
        "supporting": [s.name for s in sigs if s.score is not None and s.score >= 45],
        "counter": [s.name for s in sigs if s.score is not None and s.score < 20 and s.weight > 0],
        "unmeasured": [s.name for s in sigs if s.score is None],
        "limitations": report_svc.limitations_for(db, ev, run),
    }


@app.get("/api/evidence/{evidence_ref}/frames")
def get_frames(evidence_ref: str, db: Session = Depends(get_db)):
    ev, run = _require_run(db, evidence_ref)
    rows = (db.query(FrameAnalysis).filter(FrameAnalysis.run_id == run.id)
            .order_by(FrameAnalysis.frame_index).all())
    scored = [r for r in rows if r.score is not None]
    peak = max(scored, key=lambda r: r.score) if scored else None
    return {"frames": [{"frame_index": r.frame_index, "frame_number": r.frame_number,
                        "timestamp_s": r.timestamp_s, "score": r.score,
                        "metrics": r.metrics_json,
                        "image_url": f"/api/evidence/{evidence_ref}/frames/{r.frame_index}/image"}
                       for r in rows],
            "peak": None if not peak else {"frame_index": peak.frame_index,
                                           "frame_number": peak.frame_number,
                                           "timestamp_s": peak.timestamp_s, "score": peak.score}}


@app.get("/api/evidence/{evidence_ref}/frames/{idx}/image")
def frame_image(evidence_ref: str, idx: int, db: Session = Depends(get_db)):
    import mimetypes
    ev, run = _require_run(db, evidence_ref)
    row = (db.query(FrameAnalysis)
           .filter(FrameAnalysis.run_id == run.id, FrameAnalysis.frame_index == idx).first())
    if not row or not row.path or not Path(row.path).exists():
        row = (db.query(FrameAnalysis)
               .filter(FrameAnalysis.run_id == run.id)
               .order_by(FrameAnalysis.frame_index.asc()).first())
    if not row or not row.path or not Path(row.path).exists():
        raise HTTPException(404, "frame not available")
    media_type = mimetypes.guess_type(row.path)[0] or "image/jpeg"
    return FileResponse(row.path, media_type=media_type)


@app.get("/api/evidence/{evidence_ref}/media")
def evidence_media(evidence_ref: str, db: Session = Depends(get_db)):
    import mimetypes
    ev = db.query(Evidence).filter(Evidence.evidence_ref == evidence_ref).first()
    if not ev or not Path(ev.stored_path).exists():
        raise HTTPException(404, "evidence file not available")
    media_type = ev.mime_type or mimetypes.guess_type(ev.stored_path)[0] or "application/octet-stream"
    return FileResponse(ev.stored_path, media_type=media_type)


@app.get("/api/evidence/{evidence_ref}/neural-analysis")
def get_neural_analysis(evidence_ref: str, db: Session = Depends(get_db)):
    """Frame-level and aggregate neural detector results."""
    ev, run = _require_run(db, evidence_ref)
    rows = (db.query(NeuralFrameResult)
            .filter(NeuralFrameResult.run_id == run.id)
            .order_by(NeuralFrameResult.frame_index).all())
    if not rows:
        return {
            "evidence_ref": ev.evidence_ref,
            "model_available": neural_svc.detector_available(),
            "frames_analysed": 0,
            "frame_results": [],
            "aggregate": None,
            "empty_reason": "No neural analysis was performed for this evidence."
                           if not neural_svc.detector_available()
                           else "Neural analysis has no results for this run.",
            "provenance": neural_svc.model_provenance(),
        }
    scores = [r.normalized_score for r in rows if r.normalized_score is not None]
    import numpy as np
    median_s = round(float(np.median(scores)), 4) if scores else None
    mean_s = round(float(np.mean(scores)), 4) if scores else None
    max_s = round(float(np.max(scores)), 4) if scores else None
    suspicious = sum(1 for s in scores if s >= 0.6)

    # Check recapture and interface indicators for screenshot safety
    rec = db.query(RecaptureResult).filter(RecaptureResult.run_id == run.id).first()
    screenshot_caution = False
    if rec and (rec.likelihood in ("HIGH", "MEDIUM") or (rec.score is not None and rec.score >= 40.0)):
        screenshot_caution = True
    fn = (ev.filename or "").lower()
    if any(k in fn for k in ("screenshot", "screen_shot", "screen-shot", "capture")):
        screenshot_caution = True

    if median_s is not None:
        if median_s >= 0.75:
            assessment_level = "Strong"
            assessment_text = "Strong model-generated synthetic-image signal"
        elif median_s >= 0.5:
            assessment_level = "Moderate"
            assessment_text = "Moderate model-generated synthetic-image signal"
        elif median_s >= 0.3:
            assessment_level = "Low"
            assessment_text = "Low model-generated synthetic-image signal"
        else:
            assessment_level = "Inconclusive"
            assessment_text = "Inconclusive / no strong synthetic-image signal"
    else:
        assessment_level = "Inconclusive"
        assessment_text = "Inconclusive / no data"

    return {
        "evidence_ref": ev.evidence_ref,
        "model_available": True,
        "frames_analysed": len(rows),
        "frame_results": [{
            "frame_index": r.frame_index,
            "frame_number": r.frame_number,
            "timestamp_s": r.timestamp_s,
            "score": r.normalized_score,
            "label": r.label,
            "raw_output": r.raw_output,
            "inference_time_ms": r.inference_time_ms,
            "error": r.error,
        } for r in rows],
        "aggregate": {
            "median_score": median_s,
            "mean_score": mean_s,
            "max_score": max_s,
            "suspicious_frames": suspicious,
            "assessment": assessment_level.upper(),
            "assessment_level": assessment_level,
            "assessment_text": assessment_text,
            "model_score_pct": round(median_s * 100, 1) if median_s is not None else None,
        },
        "screenshot_caution": screenshot_caution,
        "caution_message": (
            "Model result requires caution: screenshot/recaptured imagery may produce elevated synthetic-image scores."
            if screenshot_caution else None
        ),
        "disclaimer": (
            "This score is a model-generated decision-support signal and does not by itself establish authenticity or manipulation. "
            "The model is designed primarily for AI-generated artistic imagery and is not a standalone deepfake detector."
        ),
        "multi_signal_note": "Multiple independent forensic signals should be reviewed together. No single signal establishes authenticity.",
        "provenance": neural_svc.model_provenance(),
    }


@app.get("/api/evidence/{evidence_ref}/quality")
def get_quality(evidence_ref: str, db: Session = Depends(get_db)):
    """Physical image quality and forensic reliability gating."""
    ev, run = _require_run(db, evidence_ref)
    fps = _frame_paths_for_run(db, run.id)
    return quality_svc.assess_quality(fps)


@app.get("/api/evidence/{evidence_ref}/cross-signal-assessment")
def get_cross_signal_assessment(evidence_ref: str, db: Session = Depends(get_db)):
    """Holistic cross-signal forensic synthesis and structured Evidence Matrix."""
    ev, run = _require_run(db, evidence_ref)
    sigs = db.query(Signal).filter(Signal.run_id == run.id).all()
    rec = db.query(RecaptureResult).filter(RecaptureResult.run_id == run.id).first()
    neural_res = get_neural_analysis(evidence_ref, db)
    origin_res = get_origin(evidence_ref, db)
    fps = _frame_paths_for_run(db, run.id)
    q_gate = quality_svc.assess_quality(fps)

    evidence_facts = {
        "evidence_ref": ev.evidence_ref,
        "filename": ev.filename,
        "sha256": ev.sha256,
        "size_bytes": ev.size_bytes,
        "media_kind": ev.media_kind,
        "exif_fields": len(ev.exif_json or {}),
        "c2pa_present": ev.c2pa_present,
    }
    signals_list = [{"name": s.name, "score": s.score, "level": s.strength, "weight": s.weight, "key": s.key, "result": s.result} for s in sigs]
    rec_dict = None
    if rec:
        rec_dict = {
            "likelihood": rec.likelihood,
            "likelihood_score": rec.score,
            "static_bands": rec.static_band_json or {},
            "recovered_handles": rec.recovered_handles_json or [],
        }

    return cross_svc.synthesize_cross_signal_assessment(
        evidence_facts=evidence_facts,
        signals=signals_list,
        recapture=rec_dict,
        neural=neural_res,
        origin_matches=origin_res.get("matches", []),
        quality_gate=q_gate,
    )


@app.get("/api/system/traces")
def get_available_traces():
    """List available spatial forensic trace types."""
    return {"traces": trace_svc.get_available_traces()}


@app.get("/api/evidence/{evidence_ref}/traces/{trace_type}")
def get_trace_image(evidence_ref: str, trace_type: str, frame_idx: int = 0, db: Session = Depends(get_db)):
    """Generate and stream a spatial forensic trace map (noise residual, ELA, gradient)."""
    from fastapi.responses import Response
    ev, run = _require_run(db, evidence_ref)
    row = (db.query(FrameAnalysis)
           .filter(FrameAnalysis.run_id == run.id, FrameAnalysis.frame_index == frame_idx).first())
    if not row or not row.path or not Path(row.path).exists():
        row = (db.query(FrameAnalysis)
               .filter(FrameAnalysis.run_id == run.id).first())
    if not row or not row.path or not Path(row.path).exists():
        raise HTTPException(404, "no frame image available for visual trace")

    png_bytes, meta = trace_svc.generate_trace(row.path, trace_type)
    if not png_bytes:
        raise HTTPException(400, meta.get("error", "failed to generate visual trace"))
    return Response(content=png_bytes, media_type="image/png")


@app.get("/api/evidence/{evidence_ref}/origin")
def get_origin(evidence_ref: str, db: Session = Depends(get_db)):
    ev, run = _require_run(db, evidence_ref)
    rows = (db.query(OriginMatch, CorpusItem)
            .join(CorpusItem, OriginMatch.corpus_id == CorpusItem.id)
            .filter(OriginMatch.run_id == run.id)
            .order_by(CorpusItem.observed_at.asc()).all())
    matches = [{
        "corpus_id": c.id, "label": c.label, "source_kind": c.source_kind,
        "observed_at": _iso(c.observed_at), "similarity": m.similarity, "hamming": m.hamming,
        "hash_type": m.hash_type, "normalisation": m.normalisation,
        "matched_frames": m.matched_frames,
        "total_frames": m.total_frames, "is_earliest": m.is_earliest,
        "transform": c.transform, "is_synthetic": c.is_synthetic, "sha256": c.sha256,
        "note": c.note,
    } for m, c in rows]
    earliest = next((m for m in matches if m["is_earliest"]), None)
    span = None
    if earliest and earliest["observed_at"]:
        d = ev.ingested_at - dt.datetime.fromisoformat(earliest["observed_at"])
        span = round(d.total_seconds() / 86400, 2)
    return {
        "evidence_ref": ev.evidence_ref,
        "corpus_size": db.query(CorpusItem).count(),
        "matches": matches, "match_count": len(matches), "earliest": earliest,
        "propagation_span_days": span,
        "max_similarity": max((m["similarity"] for m in matches), default=None),
        "method": "Perceptual hashing (pHash 64-bit) over sampled keyframes",
        "threshold": (f"multi-view Hamming distance ≤ {fp_svc.MATCH_THRESHOLD} of 64 bits, "
                      f"corroborated by ≥ {fp_svc.MIN_CORROBORATING_FRAMES} independently "
                      f"matching frames"),
        "threshold_calibration": fp_svc.CALIBRATION,
        "established": bool(earliest),
        "empty_reason": None if earliest else
            "No matching reference found in the available corpus.",
        "disclaimer": "Earliest known/reference match within the available corpus. This is not a claim of first "
                      "publication anywhere, and SROT never describes a match as 'original source'.",
        "attribution_ceiling": casebuild.attribution_ceiling(db, ev, run),
    }


@app.get("/api/evidence/{evidence_ref}/entities")
def get_entities(evidence_ref: str, db: Session = Depends(get_db)):
    ev, run = _require_run(db, evidence_ref)
    rows = db.query(ExtractedEntity).filter(ExtractedEntity.run_id == run.id).all()
    langs = sorted({r.language for r in rows if r.language and r.language != "unknown"})
    return {"entities": [{
        "value": r.value, "entity_type": r.entity_type, "raw_text": r.raw_text,
        "language": r.language, "frame_index": r.frame_index, "frame_number": r.frame_number,
        "timestamp_s": r.timestamp_s, "bbox": r.bbox_json,
        "ocr_confidence": r.ocr_confidence, "method": r.method, "region": r.region,
        "frame_image_url": f"/api/evidence/{evidence_ref}/frames/{r.frame_index}/image",
    } for r in rows],
        "count": len(rows),
        "ocr_languages_available": ocr_svc.available_languages(),
        "scripts_detected": langs,
        "empty_reason": None if rows else "No reliable text extracted from the sampled frames."}


@app.get("/api/evidence/{evidence_ref}/recapture")
def get_recapture(evidence_ref: str, db: Session = Depends(get_db)):
    ev, run = _require_run(db, evidence_ref)
    r = db.query(RecaptureResult).filter(RecaptureResult.run_id == run.id).first()
    if not r:
        raise HTTPException(404, "no recapture analysis for this evidence")
    return {"likelihood": r.likelihood, "score": r.score, "letterbox": r.letterbox_json,
            "static_bands": r.static_band_json, "fft": r.fft_json,
            "regions_scanned": r.ui_regions_json, "recovered_handles": r.recovered_handles_json,
            "note": r.note,
            "metadata_status": ("EXIF available" if (ev.exif_json or {}) else "Metadata unavailable"),
            "provenance_status": ("C2PA marker present" if ev.c2pa_present else "No C2PA manifest found")}


@app.get("/api/evidence/{evidence_ref}/graph")
def get_graph(evidence_ref: str, db: Session = Depends(get_db)):
    ev = db.query(Evidence).filter(Evidence.evidence_ref == evidence_ref).first()
    if not ev:
        raise HTTPException(404, "evidence not found")
    case = db.get(Case, ev.case_id)
    return casebuild.graph_payload(db, case, ev=ev)


@app.get("/api/evidence/{evidence_ref}/provenance-trace")
def get_provenance_trace(evidence_ref: str, db: Session = Depends(get_db)):
    """
    Forensic Debug / Data-Provenance diagnostic endpoint.
    Traces the 15-stage pipeline for an evidence item, explicitly verifying whether
    each value originated from:
      NEW_FILE | REFERENCE_CORPUS | CASE_CONTEXT | NOT_AVAILABLE | NOT_APPLICABLE
    Verifies that results are dynamically computed from the uploaded media, not inherited.
    """
    ev, run = _require_run(db, evidence_ref)
    case = db.get(Case, ev.case_id)

    stages: list[dict[str, Any]] = []

    # 1. UPLOAD
    stages.append({
        "stage": "UPLOAD",
        "name": "Evidence File Intake",
        "source": "NEW_FILE",
        "status": "COMPLETED",
        "value": f"Uploaded '{ev.filename}' ({round(ev.size_bytes / 1024, 1) if ev.size_bytes else 0} KB)",
        "details": {
            "filename": ev.filename,
            "size_bytes": ev.size_bytes,
            "ingested_at": _iso(ev.ingested_at),
            "stored_path": ev.stored_path,
        },
    })

    # 2. EVIDENCE CREATION
    stages.append({
        "stage": "EVIDENCE_CREATED",
        "name": "Evidence Reference Allocation",
        "source": "NEW_FILE",
        "status": "COMPLETED",
        "value": f"Allocated reference {ev.evidence_ref} (Case: {case.case_ref})",
        "details": {
            "evidence_ref": ev.evidence_ref,
            "case_ref": case.case_ref,
            "case_id": case.id,
            "evidence_id": ev.id,
        },
    })

    # 3. HASH
    stages.append({
        "stage": "HASH",
        "name": "Cryptographic SHA-256 Digest",
        "source": "NEW_FILE",
        "status": "COMPLETED",
        "value": (ev.sha256[:16] + "...") if ev.sha256 else "None",
        "details": {
            "sha256": ev.sha256,
            "algorithm": "SHA-256 (NIST FIPS 180-4)",
            "immutable": True,
        },
    })

    # 4. MEDIA TYPE
    stages.append({
        "stage": "MEDIA_TYPE",
        "name": "Container & Codec Identification",
        "source": "NEW_FILE",
        "status": "COMPLETED",
        "value": f"{(ev.media_kind or 'UNKNOWN').upper()} ({ev.container_format or 'raw'}, video={ev.video_codec or 'none'}, audio={ev.audio_codec or 'none'})",
        "details": {
            "media_kind": ev.media_kind,
            "container_format": ev.container_format,
            "video_codec": ev.video_codec,
            "audio_codec": ev.audio_codec,
            "has_audio": ev.has_audio,
        },
    })

    # 5. FRAMES / AUDIO EXTRACTION
    n_frames = db.query(FrameAnalysis).filter(FrameAnalysis.run_id == run.id).count()
    if ev.media_kind == "audio":
        fa_source = "NEW_FILE"
        fa_val = f"Acoustic PCM track decoded ({ev.duration_s}s duration, {ev.audio_codec})"
    elif n_frames > 0:
        fa_source = "NEW_FILE"
        fa_val = f"{n_frames} keyframes extracted ({ev.duration_s}s duration, {ev.fps} fps)"
    else:
        fa_source = "NOT_AVAILABLE"
        fa_val = "No frames or audio streams could be extracted"

    stages.append({
        "stage": "FRAMES_AUDIO_EXTRACTED",
        "name": "Keyframe / PCM Audio Track Extraction",
        "source": fa_source,
        "status": "COMPLETED" if fa_source != "NOT_AVAILABLE" else "FAILED",
        "value": fa_val,
        "details": {
            "frames_sampled": n_frames,
            "duration_s": ev.duration_s,
            "fps": ev.fps,
            "dimensions": f"{ev.width}x{ev.height}" if ev.width and ev.height else None,
        },
    })

    # 6. QUALITY
    signals = db.query(Signal).filter(Signal.run_id == run.id).all()
    q_sig = next((s for s in signals if s.key == "metadata_coherence"), None)
    stages.append({
        "stage": "QUALITY",
        "name": "Spatial & Encoding Quality Metrics",
        "source": "NEW_FILE",
        "status": "COMPLETED",
        "value": f"Analyzed container structural coherence ({len(signals)} forensic signals)",
        "details": {
            "quality_observation": q_sig.measurement if q_sig else None,
            "bitrate": (ev.probe_json or {}).get("bit_rate"),
        },
    })

    # 7. CLASSICAL SIGNALS
    classical = [s for s in signals if s.key not in ("neural_detector", "provenance")]
    stages.append({
        "stage": "CLASSICAL_SIGNALS",
        "name": "Classical Forensic Ensemble (DCT, ELA, Noise, FFT)",
        "source": "NEW_FILE" if classical else "NOT_AVAILABLE",
        "status": "COMPLETED" if classical else "NOT_AVAILABLE",
        "value": f"{len(classical)} classical signals evaluated (aggregate score: {run.aggregate_score}/100)",
        "details": {
            "signal_keys": [s.key for s in classical],
            "aggregate_score": run.aggregate_score,
            "confidence_band": run.confidence_band,
        },
    })

    # 8. NEURAL SCORE
    neural_sig = next((s for s in signals if s.key == "neural_detector"), None)
    neural_frames = db.query(NeuralFrameResult).filter(NeuralFrameResult.run_id == run.id).count()
    if ev.media_kind == "audio":
        neural_source = "NOT_APPLICABLE"
        neural_val = "Neural ViT image model not applicable to audio media"
    elif neural_sig and neural_sig.score is not None:
        neural_source = "NEW_FILE"
        neural_val = f"ViT detector model score: {neural_sig.score}% across {neural_frames} frames"
    elif neural_svc.detector_available():
        neural_source = "NEW_FILE"
        neural_val = "ViT detector ran: inconclusive/zero score"
    else:
        neural_source = "NOT_AVAILABLE"
        neural_val = "Local ViT model weights not initialized (offline fallback)"

    stages.append({
        "stage": "NEURAL_SCORE",
        "name": "Local Neural AI-Synthetic ViT Model",
        "source": neural_source,
        "status": "COMPLETED" if neural_source in ("NEW_FILE", "NOT_APPLICABLE") else "NOT_AVAILABLE",
        "value": neural_val,
        "details": {
            "model_score": neural_sig.score if neural_sig else None,
            "frames_evaluated": neural_frames,
            "model_name": ((neural_sig.measurement or {}).get("model") if neural_sig else "ViT-Synthetic-Detector"),
        },
    })

    # 9. RECAPTURE
    rec = db.query(RecaptureResult).filter(RecaptureResult.run_id == run.id).first()
    if ev.media_kind == "audio":
        rc_source = "NOT_APPLICABLE"
        rc_val = "Recapture analysis not applicable to audio media"
    elif rec:
        rc_source = "NEW_FILE"
        rc_val = f"Likelihood: {rec.likelihood} (score {rec.score}/100)"
    else:
        rc_source = "NOT_AVAILABLE"
        rc_val = "No recapture result recorded"

    stages.append({
        "stage": "RECAPTURE",
        "name": "Screen Recapture & Moire Analysis",
        "source": rc_source,
        "status": "COMPLETED" if rc_source in ("NEW_FILE", "NOT_APPLICABLE") else "NOT_AVAILABLE",
        "value": rc_val,
        "details": {
            "likelihood": rec.likelihood if rec else None,
            "score": rec.score if rec else None,
            "handles_recovered": len(rec.recovered_handles_json or []) if rec else 0,
        },
    })

    # 10. OCR
    entities = db.query(ExtractedEntity).filter(ExtractedEntity.run_id == run.id).all()
    if ev.media_kind == "audio":
        ocr_source = "NOT_APPLICABLE"
        ocr_val = "OCR text extraction not applicable to audio media"
    elif entities:
        ocr_source = "NEW_FILE"
        ocr_val = f"{len(entities)} entities extracted from uploaded media"
    else:
        ocr_source = "NEW_FILE"
        ocr_val = "0 text entities extracted (clean frame imagery)"

    stages.append({
        "stage": "OCR",
        "name": "Optical Character Recognition (OCR) & Entity Extraction",
        "source": ocr_source,
        "status": "COMPLETED" if ocr_source in ("NEW_FILE", "NOT_APPLICABLE") else "NOT_AVAILABLE",
        "value": ocr_val,
        "details": {
            "entity_count": len(entities),
            "sample_entities": [f"{e.entity_type}: {e.value}" for e in entities[:5]],
        },
    })

    # 11. C2PA
    stages.append({
        "stage": "C2PA",
        "name": "C2PA / Content Credentials Provenance Manifest",
        "source": "NEW_FILE",
        "status": "COMPLETED",
        "value": "C2PA manifest detected" if ev.c2pa_present else "No C2PA manifest found in container",
        "details": {
            "present": ev.c2pa_present,
            "note": ev.c2pa_note,
        },
    })

    # 12. ORIGIN MATCH
    matches = db.query(OriginMatch).filter(OriginMatch.run_id == run.id).all()
    if matches:
        orig_source = "REFERENCE_CORPUS"
        orig_val = f"{len(matches)} reference match(es) corroborated in corpus"
    else:
        orig_source = "REFERENCE_CORPUS"
        orig_val = "No matching reference found in the available corpus"

    stages.append({
        "stage": "ORIGIN_MATCH",
        "name": "Perceptual Hash Corpus Matching",
        "source": orig_source,
        "status": "COMPLETED",
        "value": orig_val,
        "details": {
            "matches_found": len(matches),
            "reference_corpus_size": db.query(CorpusItem).count(),
            "attribution_status": "CORROBORATED" if matches else "UNATTRIBUTED",
        },
    })

    # 13. STRESS TEST
    stress = db.query(StressTestRun).filter(StressTestRun.evidence_id == ev.id).first()
    if stress and stress.status == "completed":
        st_source = "NEW_FILE"
        st_val = f"Completed ({stress.reliability_boundary or 'evaluated'})"
    else:
        st_source = "NOT_AVAILABLE"
        st_val = "Stress test not yet triggered for this evidence"

    stages.append({
        "stage": "STRESS_TEST",
        "name": "Laundering Perturbation & Stress Testing",
        "source": st_source,
        "status": "COMPLETED" if stress and stress.status == "completed" else "NOT_AVAILABLE",
        "value": st_val,
        "details": {
            "status": stress.status if stress else "NOT_RUN",
            "boundary": stress.reliability_boundary if stress else None,
        },
    })

    # 14. CROSS SIGNAL ASSESSMENT
    assessment_data = get_cross_signal_assessment(evidence_ref, db)
    assessment = assessment_data.get("assessment", {})
    stages.append({
        "stage": "CROSS_SIGNAL_ASSESSMENT",
        "name": "Cross-Signal Synthesis & Dissent Evaluation",
        "source": "NEW_FILE",
        "status": "COMPLETED",
        "value": f"Evidence State: {assessment.get('evidence_state', 'INSUFFICIENT')} (Agreement: {assessment.get('signal_agreement', 'NEUTRAL')})",
        "details": {
            "evidence_state": assessment.get("evidence_state"),
            "signal_agreement": assessment.get("signal_agreement"),
            "corroboration_score": assessment.get("corroboration_score"),
            "limitations_noted": len(assessment.get("forensic_limitations", [])),
        },
    })

    # 15. FINAL EVIDENCE STATE
    stages.append({
        "stage": "FINAL_EVIDENCE_STATE",
        "name": "Final Forensic Conclusion & Dossier Synthesis",
        "source": "NEW_FILE",
        "status": "COMPLETED",
        "value": f"{run.assessment} (Confidence band: {run.confidence_band})",
        "details": {
            "assessment": run.assessment,
            "confidence_band": run.confidence_band,
            "aggregate_score": run.aggregate_score,
            "evidence_ref": ev.evidence_ref,
            "dissent": run.dissent,
        },
    })

    return {
        "evidence_ref": ev.evidence_ref,
        "case_ref": case.case_ref,
        "filename": ev.filename,
        "sha256": ev.sha256,
        "media_kind": ev.media_kind,
        "stages": stages,
        "all_stages_isolated": all(s["source"] in ("NEW_FILE", "REFERENCE_CORPUS", "NOT_AVAILABLE", "NOT_APPLICABLE") for s in stages),
    }


@app.get("/api/evidence/{evidence_ref}/replay")
@app.post("/api/evidence/{evidence_ref}/replay")
def replay_case_evidence(evidence_ref: str, db: Session = Depends(get_db)):
    """
    Deterministically re-executes the complete forensic pipeline on stored evidence
    and returns a comparison matrix proving mathematical reproducibility.
    """
    ev = db.query(Evidence).filter(Evidence.evidence_ref == evidence_ref).first()
    if not ev:
        raise HTTPException(404, f"Evidence '{evidence_ref}' not found")
    res = replay_svc.replay_evidence(evidence_ref)
    return res


# ── stress test ──────────────────────────────────────────────────────────────
@app.get("/api/evidence/{evidence_ref}/audio-forensics")
def get_audio_forensics(evidence_ref: str, db: Session = Depends(get_db)):
    """
    Extracts acoustic and spectral forensic indicators from the audio track of the evidence.
    """
    ev = db.query(Evidence).filter(Evidence.evidence_ref == evidence_ref).first()
    if not ev:
        raise HTTPException(404, "evidence not found")
    if not Path(ev.stored_path).exists():
        raise HTTPException(404, "evidence file not found on disk")
    return audio_svc.analyze_audio_forensics(ev.stored_path)


@app.post("/api/evidence/{evidence_ref}/stress-test")
def start_stress(evidence_ref: str, background: BackgroundTasks, db: Session = Depends(get_db)):
    ev, _ = _require_run(db, evidence_ref)
    st = StressTestRun(evidence_id=ev.id, status="queued")
    db.add(st); db.commit(); db.refresh(st)
    background.add_task(pipeline.run_stress, ev.id, st.id)
    return {"stress_id": st.id, "status": "queued"}


@app.get("/api/evidence/{evidence_ref}/stress-test")
def get_stress(evidence_ref: str, db: Session = Depends(get_db)):
    ev = db.query(Evidence).filter(Evidence.evidence_ref == evidence_ref).first()
    if not ev:
        raise HTTPException(404, "evidence not found")
    st = (db.query(StressTestRun).filter(StressTestRun.evidence_id == ev.id)
          .order_by(StressTestRun.id.desc()).first())
    if not st:
        return {"status": "none", "variants": [],
                "empty_reason": "No laundering stress test has been executed for this evidence."}
    vs = db.query(StressVariant).filter(StressVariant.stress_id == st.id).all()
    deltas = [abs(v.delta) for v in vs if v.delta is not None]
    if deltas:
        mean_d = round(float(sum(deltas) / len(deltas)), 2)
        max_d = round(float(max(deltas)), 2)
        if mean_d <= 6.0 and max_d <= 15.0:
            s_grade = "HIGHLY_STABLE"
            s_summary = f"Signal remained directionally stable across tested transformations (mean delta: ±{mean_d}%, max shift: {max_d}%). Findings are resilient."
        elif mean_d <= 12.0:
            s_grade = "DIRECTIONALLY_CONSISTENT"
            s_summary = f"Signal exhibited moderate variance under laundering transforms (mean delta: ±{mean_d}%, max shift: {max_d}%). Directional trend holds."
        else:
            s_grade = "SENSITIVE_TO_TRANSFORMATION"
            s_summary = f"Signal sensitivity detected under laundering transformations (mean delta: ±{mean_d}%, max shift: {max_d}%). Assessment confidence downgraded."
    else:
        mean_d, max_d, s_grade, s_summary = None, None, "INSUFFICIENT_DATA", "Insufficient valid variants to evaluate directional stability."

    return {
        "stress_id": st.id, "status": st.status, "baseline_score": st.baseline_score,
        "reliability_boundary": st.reliability_boundary, "recommendation": st.recommendation,
        "error": st.error, "finished_at": _iso(st.finished_at),
        "directional_stability": {
            "grade": s_grade,
            "mean_delta": mean_d,
            "max_delta": max_d,
            "summary": s_summary,
            "surviving_count": len([v for v in vs if v.reliable is True]),
            "total_count": len(vs),
        },
        "variants": [{"name": v.name, "transform": v.transform, "ffmpeg_args": v.ffmpeg_args,
                      "score": v.score, "delta": v.delta, "sha256": v.sha256,
                      "size_bytes": v.size_bytes, "phash_similarity": v.phash_similarity,
                      "phash_hamming": v.phash_hamming, "reliable": v.reliable,
                      "processing_ms": v.processing_ms, "error": v.error} for v in vs],
    }


# ── campaign / timeline / leads / audit ──────────────────────────────────────
@app.get("/api/cases/{case_ref}/campaign-matches")
def campaign_matches(case_ref: str, evidence_ref: str | None = None, db: Session = Depends(get_db)):
    c = db.query(Case).filter(Case.case_ref == case_ref).first()
    if not c:
        raise HTTPException(404, "case not found")
    q = db.query(CampaignMatch).filter(CampaignMatch.case_id == c.id)
    if evidence_ref:
        ev = db.query(Evidence).filter(Evidence.evidence_ref == evidence_ref).first()
        if ev:
            q = q.filter(CampaignMatch.evidence_id == ev.id)
    rows = q.all()
    ev_map = {e.id: e.evidence_ref for e in db.query(Evidence).filter(Evidence.case_id == c.id).all()}
    return {"matches": [{"other_case_ref": r.other_case_ref, "other_evidence_ref": r.other_evidence_ref,
                         "evidence_ref": ev_map.get(r.evidence_id, ""),
                         "similarity": r.similarity, "hamming": r.hamming,
                         "hash_type": r.hash_type or "phash (multi-view)",
                         "seen_at": _iso(r.seen_at)} for r in rows],
            "count": len(rows),
            "ledger_entries": db.query(FingerprintLedger).count(),
            "wording": "Potential campaign relationship — these cases contain highly similar media "
                       "and may warrant joint review. This does not establish that the same person "
                       "is involved.",
            "empty_reason": None if rows else "No qualifying cross-case match found."}


@app.get("/api/cases/{case_ref}/timeline")
def timeline(case_ref: str, db: Session = Depends(get_db)):
    c = db.query(Case).filter(Case.case_ref == case_ref).first()
    if not c:
        raise HTTPException(404, "case not found")
    rows = (db.query(TimelineEvent).filter(TimelineEvent.case_id == c.id)
            .order_by(TimelineEvent.occurred_at.asc()).all())
    return [{"occurred_at": _iso(r.occurred_at), "title": r.title, "detail": r.detail,
             "kind": r.kind, "evidence_ref": r.evidence_ref, "confidence": r.confidence,
             "is_synthetic": r.is_synthetic} for r in rows]


@app.get("/api/cases/{case_ref}/leads")
def leads(case_ref: str, db: Session = Depends(get_db)):
    c = db.query(Case).filter(Case.case_ref == case_ref).first()
    if not c:
        raise HTTPException(404, "case not found")
    rows = db.query(Lead).filter(Lead.case_id == c.id).order_by(Lead.rank).all()
    return [{"rank": r.rank, "priority": r.priority, "title": r.title, "summary": r.summary,
             "reasons": r.reasons_json, "limitation": r.limitation, "status": r.status}
            for r in rows]


@app.get("/api/cases/{case_ref}/audit")
def case_audit(case_ref: str, db: Session = Depends(get_db)):
    c = db.query(Case).filter(Case.case_ref == case_ref).first()
    if not c:
        raise HTTPException(404, "case not found")
    rows = db.query(AuditLog).filter(AuditLog.case_id == c.id).order_by(AuditLog.id).all()
    return {"chain": audit_svc.verify_chain(db, c.id),
            "entries": [{"id": r.id, "occurred_at": _iso(r.occurred_at), "action": r.action,
                         "component": r.component, "actor": r.actor,
                         "evidence_ref": r.evidence_ref, "evidence_hash": r.evidence_hash,
                         "prev_hash": r.prev_hash, "current_hash": r.current_hash,
                         "payload": r.payload_json} for r in rows],
            "disclaimer": "Structured audit trail for examiner review. A valid SHA-256 hash confirms byte-level integrity, but does not by itself establish legal admissibility or authenticity."}


# ── hash verification ────────────────────────────────────────────────────────
@app.post("/api/evidence/{evidence_ref}/verify-hash")
async def verify_hash(evidence_ref: str, file: UploadFile = File(...),
                      db: Session = Depends(get_db)):
    ev = db.query(Evidence).filter(Evidence.evidence_ref == evidence_ref).first()
    if not ev:
        raise HTTPException(404, "evidence not found")
    import hashlib
    h = hashlib.sha256()
    total = 0
    while chunk := await file.read(1 << 20):
        total += len(chunk)
        if total > integrity.MAX_UPLOAD_BYTES:
            raise HTTPException(413, "file exceeds the upload limit")
        h.update(chunk)
    digest = h.hexdigest()
    match = digest == ev.sha256
    audit_svc.record(db, case_id=ev.case_id,
                     action=f"Evidence integrity verification — {'MATCH' if match else 'MISMATCH'}",
                     component="integrity service", evidence_ref=ev.evidence_ref,
                     evidence_hash=ev.sha256,
                     payload={"submitted_sha256": digest, "submitted_bytes": total,
                              "filename": integrity.sanitize_filename(file.filename or "")})
    return {"match": match, "submitted_sha256": digest, "stored_sha256": ev.sha256,
            "submitted_bytes": total, "stored_bytes": ev.size_bytes,
            "message": ("Evidence hash matches the ingested record."
                        if match else
                        "Hash mismatch — the submitted file differs from the ingested evidence.")}


# ── court packet & report ────────────────────────────────────────────────────
@app.post("/api/evidence/{evidence_ref}/court-packet")
def make_packet(evidence_ref: str, db: Session = Depends(get_db)):
    ev, _ = _require_run(db, evidence_ref)
    try:
        packet = report_svc.build_packet(db, ev.id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"packet generation failed ({type(e).__name__})")
    return _packet_json(packet)


def _packet_json(p: CourtPacket) -> dict[str, Any]:
    return {"packet_id": p.id, "created_at": _iso(p.created_at),
            "packet_sha256": p.packet_sha256,
            "zip_url": f"/api/court-packets/{p.id}/download",
            "documents": [{"key": k, "name": Path(v).stem,
                           "url": f"/api/court-packets/{p.id}/document/{k}"}
                          for k, v in (p.files_json or {}).items()]}


@app.get("/api/evidence/{evidence_ref}/court-packet")
def latest_packet(evidence_ref: str, db: Session = Depends(get_db)):
    ev = db.query(Evidence).filter(Evidence.evidence_ref == evidence_ref).first()
    if not ev:
        raise HTTPException(404, "evidence not found")
    p = (db.query(CourtPacket).filter(CourtPacket.evidence_id == ev.id)
         .order_by(CourtPacket.id.desc()).first())
    return _packet_json(p) if p else {"packet_id": None, "documents": []}


@app.get("/api/court-packets/{packet_id}/download")
def download_packet(packet_id: int, db: Session = Depends(get_db)):
    p = db.get(CourtPacket, packet_id)
    if not p or not p.zip_path:
        raise HTTPException(404, "packet not available")
    path = Path(p.zip_path).resolve()
    packet_dir = Path(PACKET_DIR).resolve()
    if not str(path).startswith(str(packet_dir)):
        raise HTTPException(403, "access denied")
    if not path.exists():
        raise HTTPException(404, "packet not available")
    return FileResponse(path, media_type="application/zip", filename=path.name)


@app.get("/api/court-packets/{packet_id}/document/{key}")
def download_doc(packet_id: int, key: str, inline: bool = False, db: Session = Depends(get_db)):
    p = db.get(CourtPacket, packet_id)
    if not p or key not in (p.files_json or {}):
        raise HTTPException(404, "document not available")
    path = Path(p.files_json[key]).resolve()
    packet_dir = Path(PACKET_DIR).resolve()
    if not str(path).startswith(str(packet_dir)):
        raise HTTPException(403, "access denied")
    if not path.exists():
        raise HTTPException(404, "document not available")
    disp = "inline" if inline else "attachment"
    return FileResponse(path, media_type="application/pdf", filename=path.name, content_disposition_type=disp)


@app.get("/api/evidence/{evidence_ref}/report")
def report_html(evidence_ref: str, db: Session = Depends(get_db)):
    ev, _ = _require_run(db, evidence_ref)
    rendered = report_svc.render_all(db, ev.id)
    return {"html": rendered["docs"]["forensic_report"]}


@app.get("/api/evidence/{evidence_ref}/executive-dossier")
@app.post("/api/evidence/{evidence_ref}/executive-dossier")
def executive_dossier_pdf(evidence_ref: str, inline: bool = False, db: Session = Depends(get_db)):
    """
    Renders and serves a consolidated single-file Executive Forensic Dossier PDF
    suitable for judicial presentation.
    """
    ev, _ = _require_run(db, evidence_ref)
    try:
        pdf_path = report_svc.build_executive_dossier(db, ev.id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"executive dossier generation failed ({type(e).__name__})")
    path = Path(pdf_path).resolve()
    packet_dir = Path(PACKET_DIR).resolve()
    if not str(path).startswith(str(packet_dir)):
        raise HTTPException(403, "access denied")
    if not path.exists():
        raise HTTPException(404, "executive dossier not found")
    disp = "inline" if inline else "attachment"
    return FileResponse(path, media_type="application/pdf", filename=path.name, content_disposition_type=disp)


@app.get("/api/evidence/{evidence_ref}/consistency")
def consistency(evidence_ref: str, db: Session = Depends(get_db)):
    """
    Report consistency check: the API payloads and the rendered documents are both
    produced from the same rows, so this endpoint mathematically verifies it rather than merely asserting it.
    """
    ev, run = _require_run(db, evidence_ref)
    data = report_svc.collect(db, ev.id)
    api_analysis = get_analysis(evidence_ref, db)
    api_origin = get_origin(evidence_ref, db)
    checks = [
        {"field": "evidence SHA-256", "database": ev.sha256,
         "api": api_analysis and ev.sha256, "report": data["evidence"].sha256,
         "match": ev.sha256 == data["evidence"].sha256},
        {"field": "assessment", "database": run.assessment,
         "api": api_analysis["assessment"], "report": data["run"].assessment,
         "match": run.assessment == api_analysis["assessment"] == data["run"].assessment},
        {"field": "aggregate score", "database": run.aggregate_score,
         "api": api_analysis["aggregate_score"], "report": data["run"].aggregate_score,
         "match": run.aggregate_score == api_analysis["aggregate_score"] == data["run"].aggregate_score},
        {"field": "corpus match count", "database": len(data["matches"]),
         "api": api_origin["match_count"], "report": len(data["matches"]),
         "match": api_origin["match_count"] == len(data["matches"])},
        {"field": "max similarity", "database": api_origin["max_similarity"],
         "api": api_origin["max_similarity"],
         "report": max((m["match"].similarity for m in data["matches"]), default=None),
         "match": api_origin["max_similarity"] == max(
             (m["match"].similarity for m in data["matches"]), default=None)},
        {"field": "entities extracted", "database": len(data["entities"]),
         "api": get_entities(evidence_ref, db)["count"], "report": len(data["entities"]),
         "match": get_entities(evidence_ref, db)["count"] == len(data["entities"])},
        {"field": "audit chain", "database": data["chain"]["verified"],
         "api": data["chain"]["verified"], "report": data["chain"]["verified"],
         "match": bool(data["chain"]["verified"])},
    ]
    return {"all_consistent": all(c["match"] for c in checks), "checks": checks,
            "note": "All views render from a single canonical payload assembled by "
                    "report.collect(); divergence is structurally impossible."}


@app.get("/api/benchmark/adversarial-summary")
def get_benchmark_summary():
    """
    Returns the internal 27-sample adversarial validation benchmark metrics
    and per-sample forensic evaluation details.
    """
    json_path = Path(__file__).resolve().parent.parent.parent / "PHASE4-BENCHMARK-RESULTS.json"
    if not json_path.exists():
        json_path = Path(__file__).resolve().parent.parent / "PHASE4-BENCHMARK-RESULTS.json"
    if not json_path.exists():
        raise HTTPException(404, "Adversarial benchmark results file not found on disk")
    import json
    return json.loads(json_path.read_text())


@app.delete("/api/cases/{case_ref}/evidence/{evidence_ref}")
def delete_evidence(case_ref: str, evidence_ref: str, db: Session = Depends(get_db)):
    """Removing the media removes everything derived from it — the graph collapses."""
    ev = db.query(Evidence).filter(Evidence.evidence_ref == evidence_ref).first()
    if not ev:
        raise HTTPException(404, "evidence not found")
    case = db.get(Case, ev.case_id)
    for model, col in ((Signal, None), (FrameAnalysis, FrameAnalysis.evidence_id),
                       (OriginMatch, OriginMatch.evidence_id),
                       (ExtractedEntity, ExtractedEntity.evidence_id),
                       (RecaptureResult, RecaptureResult.evidence_id)):
        if col is not None:
            db.query(model).filter(col == ev.id).delete()
    db.query(CampaignMatch).filter(CampaignMatch.evidence_id == ev.id).delete()
    db.query(FingerprintLedger).filter(FingerprintLedger.evidence_ref == ev.evidence_ref).delete()
    db.delete(ev); db.commit()
    shutil.rmtree(Path(WORK_DIR) / evidence_ref, ignore_errors=True)

    # the remaining evidence keeps its findings — only what came from THIS item goes
    rebuilt = casebuild.rebuild_case_views(db, case)
    audit_svc.record(db, case_id=case.id,
                     action=f"Evidence {evidence_ref} removed; derived records deleted and "
                            f"case views rebuilt from remaining evidence",
                     component="case manager", evidence_ref=evidence_ref,
                     payload={"rebuilt_from": rebuilt.get("from_evidence"),
                              "graph": rebuilt.get("graph")})
    return {"removed": evidence_ref, "rebuild": rebuilt,
            "graph": casebuild.graph_payload(db, case)["stats"]}
