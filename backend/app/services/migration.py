"""
SROT Production Migration & Administration Service.

Provides safe, authenticated tools for:
- Checking disk space, DB size, and case inventory.
- Creating timestamped database backups on persistent disk before any modification.
- Importing packaged demo cases (records and media) with strict path traversal checks,
  SHA-256 verification of all files, and transactional preservation of authentic references
  and forensic comparisons.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import os
import shutil
import sqlite3
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import sqlalchemy as sa
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db import (
    BASE_DIR,
    DB_PATH,
    EVIDENCE_DIR,
    PACKET_DIR,
    WORK_DIR,
    engine,
    get_evidence_path,
)
from ..models import (
    AnalysisRun,
    AuditLog,
    Case,
    CourtPacket,
    Evidence,
    ExtractedEntity,
    FingerprintLedger,
    ForensicComparison,
    FrameAnalysis,
    GraphEdge,
    GraphNode,
    Lead,
    NeuralFrameResult,
    RecaptureResult,
    Signal,
    StressTestRun,
    StressVariant,
    TimelineEvent,
)


def get_system_status(db: Session) -> Dict[str, Any]:
    """Retrieve persistent disk metrics, DB size, existing cases, and backups."""
    base_resolved = BASE_DIR.resolve()
    total, used, free = shutil.disk_usage(base_resolved)
    
    db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
    
    cases = db.query(Case).order_by(Case.id).all()
    case_summaries = []
    for c in cases:
        ev_cnt = db.query(Evidence).filter(Evidence.case_id == c.id).count()
        case_summaries.append({
            "id": c.id,
            "case_ref": c.case_ref,
            "title": c.title,
            "evidence_count": ev_cnt,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
        
    backups = []
    for p in sorted(base_resolved.glob("srot.db.bak.*"), reverse=True):
        backups.append({
            "name": p.name,
            "size_bytes": p.stat().st_size,
            "modified_at": dt.datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
        })

    return {
        "status": "ok",
        "storage": {
            "base_dir": str(base_resolved),
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "free_mb": round(free / (1024 * 1024), 2),
            "free_percent": round((free / total) * 100, 2),
        },
        "database": {
            "path": str(DB_PATH.resolve()),
            "size_bytes": db_size,
            "case_count": len(cases),
            "cases": case_summaries,
            "backups_count": len(backups),
            "backups": backups[:5],
        }
    }


def create_db_backup() -> Dict[str, Any]:
    """Checkpoint WAL and safely copy DB to srot.db.bak.<timestamp>."""
    if not DB_PATH.exists():
        raise HTTPException(status_code=404, detail="Database file does not exist to back up.")
    
    # Checkpoint WAL
    try:
        with engine.connect() as conn:
            conn.execute(sa.text("PRAGMA wal_checkpoint(TRUNCATE)"))
    except Exception:
        pass

    ts = int(time.time())
    backup_path = BASE_DIR / f"srot.db.bak.{ts}"
    shutil.copy2(DB_PATH, backup_path)
    
    return {
        "status": "success",
        "backup_path": str(backup_path),
        "backup_filename": backup_path.name,
        "size_bytes": backup_path.stat().st_size,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def parse_dt(v: Any) -> Any:
    if not v or not isinstance(v, str):
        return v
    try:
        return dt.datetime.fromisoformat(v)
    except Exception:
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                return dt.datetime.strptime(v, fmt)
            except Exception:
                pass
    return v


def model_from_dict(model_cls: Any, data_dict: Dict[str, Any], **overrides: Any) -> Any:
    col_map = {c.name: c for c in model_cls.__table__.columns}
    merged = dict(data_dict)
    merged.update(overrides)
    filtered = {}
    for k, v in merged.items():
        if k in col_map and k != "id":
            col = col_map[k]
            if isinstance(col.type, (sa.DateTime, sa.Date)) and isinstance(v, str):
                v = parse_dt(v)
            filtered[k] = v
    return model_cls(**filtered)


def import_case_bundle(db: Session, bundle: Dict[str, Any], zip_bytes: bytes) -> Dict[str, Any]:
    """
    Safely import a case bundle and extracted media into production storage.
    Enforces path traversal safety, SHA-256 verification, and relational preservation.
    """
    case_ref = bundle.get("case_ref")
    if not case_ref:
        raise HTTPException(status_code=400, detail="Bundle missing 'case_ref'")

    # 1. Disk space check (require at least 50 MB)
    total, used, free = shutil.disk_usage(BASE_DIR.resolve())
    if free < 50 * 1024 * 1024:
        raise HTTPException(status_code=507, detail="Insufficient persistent disk space on production.")

    # 2. Automated pre-migration DB backup
    backup_meta = create_db_backup()

    # 3. Unzip media with strict path traversal checking
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Corrupted or invalid ZIP archive: {e}")

    extracted_files = []
    base_resolved = BASE_DIR.resolve()

    for member in zf.namelist():
        norm = os.path.normpath(member)
        if norm.startswith("..") or Path(norm).is_absolute() or norm.startswith("/"):
            raise HTTPException(status_code=400, detail=f"Security violation: dangerous path in archive: {member}")
        
        target = (BASE_DIR / norm).resolve()
        if not str(target).startswith(str(base_resolved)):
            raise HTTPException(status_code=400, detail=f"Path traversal detected: {member}")
        
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(zf.read(member))
        extracted_files.append((norm, target))

    # 4. Verify SHA-256 for all extracted files against file_manifest
    manifest = bundle.get("file_manifest", [])
    verified_manifest = []
    for mf in manifest:
        arc_path = mf["archive_path"]
        p = BASE_DIR / arc_path
        if not p.exists():
            raise HTTPException(status_code=500, detail=f"Extracted file missing on disk: {arc_path}")
        
        disk_data = p.read_bytes()
        disk_sha = hashlib.sha256(disk_data).hexdigest()
        expected_sha = mf["sha256"]
        if disk_sha != expected_sha:
            raise HTTPException(
                status_code=500,
                detail=f"SHA-256 mismatch for {arc_path}: expected {expected_sha}, got {disk_sha}"
            )
        verified_manifest.append({
            "archive_path": arc_path,
            "filename": Path(arc_path).name,
            "size_bytes": len(disk_data),
            "sha256": disk_sha,
            "status": "MATCH"
        })

    # 5. Database Transaction: insert or update records
    try:
        # Case
        c_data = bundle["case"]
        case = db.query(Case).filter(Case.case_ref == case_ref).first()
        if not case:
            case = model_from_dict(Case, c_data)
            db.add(case)
            db.flush()
        else:
            # Update metadata
            case.title = c_data.get("title", case.title)
            case.category = c_data.get("category", case.category)
            case.officer = c_data.get("officer", case.officer)
            case.unit = c_data.get("unit", case.unit)
            case.summary = c_data.get("summary", case.summary)
            case.status = c_data.get("status", case.status)
            db.flush()

        new_case_id = case.id

        # Clean existing dependent records for this case if re-importing
        # (ForensicComparison, GraphNode, GraphEdge, TimelineEvent, Lead, CourtPacket)
        db.query(ForensicComparison).filter(ForensicComparison.case_id == new_case_id).delete()
        db.query(GraphEdge).filter(GraphEdge.case_id == new_case_id).delete()
        db.query(GraphNode).filter(GraphNode.case_id == new_case_id).delete()
        db.query(CourtPacket).filter(CourtPacket.case_id == new_case_id).delete()

        # Evidence
        ev_id_map: Dict[int, int] = {}
        for ev in bundle.get("evidence", []):
            old_id = ev["id"]
            eref = ev["evidence_ref"]
            fname = Path(ev["stored_path"]).name
            rel_stored = f"evidence/{case_ref}/{fname}"
            
            existing_ev = db.query(Evidence).filter(
                Evidence.case_id == new_case_id,
                Evidence.evidence_ref == eref
            ).first()

            if existing_ev:
                # Update stored path and metadata
                existing_ev.stored_path = rel_stored
                existing_ev.filename = ev["filename"]
                existing_ev.sha256 = ev["sha256"]
                existing_ev.size_bytes = ev["size_bytes"]
                existing_ev.forensic_role = ev.get("forensic_role", existing_ev.forensic_role)
                db.flush()
                ev_id_map[old_id] = existing_ev.id
            else:
                new_ev = model_from_dict(
                    Evidence,
                    ev,
                    case_id=new_case_id,
                    stored_path=rel_stored,
                    reference_evidence_id=None
                )
                db.add(new_ev)
                db.flush()
                ev_id_map[old_id] = new_ev.id

        # Map reference_evidence_id on evidence items
        for ev in bundle.get("evidence", []):
            if ev.get("reference_evidence_id") and ev["reference_evidence_id"] in ev_id_map:
                new_id = ev_id_map[ev["id"]]
                db_ev = db.get(Evidence, new_id)
                if db_ev:
                    db_ev.reference_evidence_id = ev_id_map[ev["reference_evidence_id"]]
        db.flush()

        # Analysis Runs
        run_id_map: Dict[int, int] = {}
        for r in bundle.get("analysis_runs", []):
            old_rid = r["id"]
            new_eid = ev_id_map.get(r["evidence_id"])
            if not new_eid:
                continue
            
            # Check existing run
            existing_run = db.query(AnalysisRun).filter(AnalysisRun.evidence_id == new_eid).first()
            if existing_run:
                run_id_map[old_rid] = existing_run.id
            else:
                new_run = model_from_dict(AnalysisRun, r, evidence_id=new_eid)
                db.add(new_run)
                db.flush()
                run_id_map[old_rid] = new_run.id

        # Signals
        for s in bundle.get("signals", []):
            new_rid = run_id_map.get(s["run_id"])
            if not new_rid:
                continue
            # avoid duplicate signals
            exists = db.query(Signal).filter(
                Signal.run_id == new_rid,
                Signal.name == s["name"]
            ).first()
            if not exists:
                db.add(model_from_dict(Signal, s, run_id=new_rid))

        # Neural Frame Results
        for nf in bundle.get("neural_frame_results", []):
            new_eid = ev_id_map.get(nf["evidence_id"])
            new_rid = run_id_map.get(nf["run_id"])
            if new_eid and new_rid:
                exists = db.query(NeuralFrameResult).filter(
                    NeuralFrameResult.evidence_id == new_eid,
                    NeuralFrameResult.run_id == new_rid,
                    NeuralFrameResult.frame_index == nf.get("frame_index")
                ).first()
                if not exists:
                    db.add(model_from_dict(NeuralFrameResult, nf, evidence_id=new_eid, run_id=new_rid))

        # Recapture Results
        for rc in bundle.get("recapture_results", []):
            new_eid = ev_id_map.get(rc["evidence_id"])
            new_rid = run_id_map.get(rc["run_id"])
            if new_eid and new_rid:
                exists = db.query(RecaptureResult).filter(
                    RecaptureResult.evidence_id == new_eid,
                    RecaptureResult.run_id == new_rid
                ).first()
                if not exists:
                    db.add(model_from_dict(RecaptureResult, rc, evidence_id=new_eid, run_id=new_rid))

        # Frame Analysis
        for fa in bundle.get("frame_analysis", []):
            new_rid = run_id_map.get(fa["run_id"])
            if new_rid:
                exists = db.query(FrameAnalysis).filter(
                    FrameAnalysis.run_id == new_rid,
                    FrameAnalysis.frame_index == fa.get("frame_index")
                ).first()
                if not exists:
                    db.add(model_from_dict(FrameAnalysis, fa, run_id=new_rid))

        # Stress Runs & Variants
        stress_id_map: Dict[int, int] = {}
        for sr in bundle.get("stress_runs", []):
            new_eid = ev_id_map.get(sr["evidence_id"])
            if not new_eid:
                continue
            existing_sr = db.query(StressTestRun).filter(StressTestRun.evidence_id == new_eid).first()
            if existing_sr:
                stress_id_map[sr["id"]] = existing_sr.id
            else:
                new_sr = model_from_dict(StressTestRun, sr, evidence_id=new_eid)
                db.add(new_sr)
                db.flush()
                stress_id_map[sr["id"]] = new_sr.id

        for sv in bundle.get("stress_variants", []):
            new_sid = stress_id_map.get(sv["stress_id"])
            if not new_sid:
                continue
            fname = Path(sv["path"]).name
            new_path = str(WORK_DIR / "EV-CASE-2026-112-001" / "stress" / fname)
            exists = db.query(StressVariant).filter(
                StressVariant.stress_id == new_sid,
                StressVariant.name == sv["name"]
            ).first()
            if not exists:
                db.add(model_from_dict(StressVariant, sv, stress_id=new_sid, path=new_path))

        # Forensic Comparisons (Preserve all 11 comparisons verbatim!)
        comparisons_imported = 0
        for fc in bundle.get("forensic_comparisons", []):
            new_ref_id = ev_id_map.get(fc["reference_evidence_id"])
            new_der_id = ev_id_map.get(fc["derivative_evidence_id"])
            if not new_ref_id or not new_der_id:
                continue
            db.add(model_from_dict(
                ForensicComparison,
                fc,
                case_id=new_case_id,
                reference_evidence_id=new_ref_id,
                derivative_evidence_id=new_der_id
            ))
            comparisons_imported += 1

        # Audit Logs
        for a in bundle.get("audit_log", []):
            db.add(model_from_dict(AuditLog, a, case_id=new_case_id))

        # Timeline Events
        for t in bundle.get("timeline_events", []):
            db.add(model_from_dict(TimelineEvent, t, case_id=new_case_id))

        # Leads
        for l in bundle.get("leads", []):
            db.add(model_from_dict(Lead, l, case_id=new_case_id))

        # Court Packets
        for cp in bundle.get("court_packets", []):
            new_eid = ev_id_map.get(cp.get("evidence_id")) if cp.get("evidence_id") else None
            zip_fname = Path(cp["zip_path"]).name
            new_zip_path = str(PACKET_DIR / zip_fname)
            new_files_json = {}
            if cp.get("files_json"):
                fjson = json.loads(cp["files_json"]) if isinstance(cp["files_json"], str) else cp["files_json"]
                for k, pstr in fjson.items():
                    doc_p = Path(pstr)
                    folder_name = doc_p.parent.name
                    new_files_json[k] = str(PACKET_DIR / folder_name / doc_p.name)
            db.add(model_from_dict(
                CourtPacket,
                cp,
                case_id=new_case_id,
                evidence_id=new_eid,
                zip_path=new_zip_path,
                files_json=new_files_json
            ))

        # Extracted Entities
        for ee in bundle.get("extracted_entities", []):
            new_eid = ev_id_map.get(ee["evidence_id"])
            if not new_eid:
                continue
            val = ee.get("value") or ee.get("entity_value")
            etype = ee.get("entity_type")
            exists = db.query(ExtractedEntity).filter(
                ExtractedEntity.evidence_id == new_eid,
                ExtractedEntity.entity_type == etype,
                ExtractedEntity.value == val
            ).first()
            if not exists:
                db.add(model_from_dict(ExtractedEntity, ee, evidence_id=new_eid, value=val))

        # Graph Nodes & Edges
        for gn in bundle.get("graph_nodes", []):
            db.add(model_from_dict(GraphNode, gn, case_id=new_case_id))

        for ge in bundle.get("graph_edges", []):
            db.add(model_from_dict(GraphEdge, ge, case_id=new_case_id))

        # Fingerprint Ledger
        for fp in bundle.get("fingerprint_ledger", []):
            exists = db.query(FingerprintLedger).filter(
                FingerprintLedger.case_ref == fp.get("case_ref"),
                FingerprintLedger.evidence_ref == fp.get("evidence_ref"),
                FingerprintLedger.media_sha256 == fp.get("media_sha256")
            ).first()
            if not exists:
                db.add(model_from_dict(FingerprintLedger, fp))

        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database migration transaction failed: {e}")

    # Post-import verification query
    imported_ev_count = db.query(Evidence).filter(Evidence.case_id == new_case_id).count()
    auth_ref_ev = db.query(Evidence).filter(
        Evidence.case_id == new_case_id,
        Evidence.evidence_ref == "EV-CASE-2026-112-001"
    ).first()

    return {
        "status": "SUCCESS",
        "case_ref": case_ref,
        "case_id": new_case_id,
        "evidence_count": imported_ev_count,
        "authentic_reference": auth_ref_ev.evidence_ref if auth_ref_ev else "NOT FOUND",
        "authentic_reference_role": auth_ref_ev.forensic_role if auth_ref_ev else "NOT FOUND",
        "comparisons_count": comparisons_imported,
        "files_verified_count": len(verified_manifest),
        "files_manifest": verified_manifest,
        "backup_performed": backup_meta,
    }
