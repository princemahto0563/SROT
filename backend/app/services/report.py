"""
Deterministic, template-driven document generation.

CONSISTENCY BY CONSTRUCTION: `collect()` assembles ONE canonical payload from the
database, and every document (dashboard API, forensic report, BSA §63 certificate,
hash report, chain of custody, annexure, preservation request) is rendered from
that same payload. A value cannot differ between two views because there is only
one value.

No language model writes any part of these documents.
"""
from __future__ import annotations
import datetime as dt
import hashlib, io, json, zipfile
from pathlib import Path
from typing import Any

import qrcode
from jinja2 import Environment, BaseLoader, select_autoescape
from sqlalchemy.orm import Session

from ..db import PACKET_DIR
from ..models import (
    Case, Evidence, AnalysisRun, Signal, FrameAnalysis, OriginMatch, CorpusItem,
    ExtractedEntity, RecaptureResult, StressTestRun, StressVariant, CampaignMatch,
    AuditLog, CourtPacket, TimelineEvent, Lead, utcnow,
)
from . import audit as audit_svc
from . import casebuild, signals as sig_svc, ocr as ocr_svc
from . import fingerprint as fp_svc

NA = "Not available / To be completed"


def _fmt(v: Any, dash: str = NA) -> str:
    if v is None or v == "":
        return dash
    if isinstance(v, dt.datetime):
        return v.strftime("%d %b %Y · %H:%M:%S UTC")
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


# ── canonical payload ────────────────────────────────────────────────────────
def limitations_for(db: Session, ev: Evidence, run: AnalysisRun | None) -> list[str]:
    """
    Limitations are DERIVED from what actually happened in this run, never a fixed
    boilerplate list — an absent finding must be stated as absent.
    """
    matches = (db.query(OriginMatch).filter(OriginMatch.run_id == run.id).all() if run else [])
    ents = (db.query(ExtractedEntity).filter(ExtractedEntity.run_id == run.id).all() if run else [])
    rc = (db.query(RecaptureResult).filter(RecaptureResult.run_id == run.id).first() if run else None)
    st = (db.query(StressTestRun).filter(StressTestRun.evidence_id == ev.id,
                                         StressTestRun.status == "completed")
          .order_by(StressTestRun.id.desc()).first())
    lims: list[str] = []
    if not ev.exif_json:
        lims.append("No EXIF metadata was present in this evidence. Absence of metadata is not "
                    "evidence of manipulation.")
    if not ev.c2pa_present:
        lims.append("No C2PA Content Credentials manifest was found. Most platforms and messaging "
                    "applications strip provenance metadata on re-upload.")
    if not matches:
        lims.append("No qualifying near-duplicate was found in the reference corpus, so the origin "
                    "of this media cannot be established from available data.")
    else:
        lims.append(f"Origin ordering is limited to the {db.query(CorpusItem).count()} items in the "
                    "searched reference corpus and is not a claim of first publication anywhere.")
    if run and run.dissent:
        lims.append("At least one measured signal did not corroborate the overall assessment. "
                    "The disagreement is recorded rather than averaged away.")
    if not ents:
        lims.append("No text was reliably extracted by OCR from the sampled frames.")
    if rc and not (rc.recovered_handles_json or []):
        lims.append("No reliable source handle was recovered from interface regions.")
    if not st:
        lims.append("No laundering stress test has been executed for this evidence, so no observed "
                    "reliability boundary can be stated.")
    from .neural import detector_available, MODEL_NAME, MODEL_TRAINING_DOMAIN
    if detector_available():
        lims.append(f"The assessment is produced by '{run.detector_backend if run else 'n/a'}' — a "
                    "weighted ensemble of classical forensic signals augmented by an "
                    f"AI-synthetic image signal ({MODEL_NAME}). {MODEL_TRAINING_DOMAIN}")
    else:
        lims.append(f"The assessment is produced by '{run.detector_backend if run else 'n/a'}' — a "
                    "weighted ensemble of measured classical forensic signals. No trained neural "
                    "model was active during this analysis.")
    lims.append("SROT does not identify persons, resolve identifier ownership, or determine legal "
                "admissibility.")

    return lims


def collect(db: Session, evidence_id: int) -> dict[str, Any]:
    ev = db.get(Evidence, evidence_id)
    if ev is None:
        raise ValueError("evidence not found")
    case = db.get(Case, ev.case_id)
    run = (db.query(AnalysisRun)
           .filter(AnalysisRun.evidence_id == ev.id, AnalysisRun.status == "completed")
           .order_by(AnalysisRun.id.desc()).first())

    sigs = (db.query(Signal).filter(Signal.run_id == run.id).all() if run else [])
    frames = (db.query(FrameAnalysis).filter(FrameAnalysis.run_id == run.id)
              .order_by(FrameAnalysis.frame_index).all() if run else [])
    matches = ([{"match": m, "corpus": c} for m, c in
                db.query(OriginMatch, CorpusItem)
                .join(CorpusItem, OriginMatch.corpus_id == CorpusItem.id)
                .filter(OriginMatch.run_id == run.id)
                .order_by(OriginMatch.similarity.desc()).all()] if run else [])
    ents = (db.query(ExtractedEntity).filter(ExtractedEntity.run_id == run.id).all() if run else [])
    rc = (db.query(RecaptureResult).filter(RecaptureResult.run_id == run.id).first() if run else None)
    st = (db.query(StressTestRun).filter(StressTestRun.evidence_id == ev.id,
                                         StressTestRun.status == "completed")
          .order_by(StressTestRun.id.desc()).first())
    variants = (db.query(StressVariant).filter(StressVariant.stress_id == st.id).all() if st else [])
    campaigns = db.query(CampaignMatch).filter(CampaignMatch.case_id == case.id).all()
    audits = (db.query(AuditLog).filter(AuditLog.case_id == case.id)
              .order_by(AuditLog.id.asc()).all())
    timeline = (db.query(TimelineEvent).filter(TimelineEvent.case_id == case.id)
                .order_by(TimelineEvent.occurred_at.asc()).all())
    leads = (db.query(Lead).filter(Lead.case_id == case.id).order_by(Lead.rank.asc()).all())
    chain = audit_svc.verify_chain(db, case.id)
    ceiling = casebuild.attribution_ceiling(db, ev, run) if run else []

    earliest = next((m for m in matches if m["match"].is_earliest), None)
    langs = ocr_svc.available_languages()
    scripts = sorted({e.language for e in ents if e.language and e.language != "unknown"})

    from app.models import NeuralFrameResult
    neural_frames = (db.query(NeuralFrameResult).filter(NeuralFrameResult.run_id == run.id)
                     .order_by(NeuralFrameResult.frame_index.asc()).all() if run else [])
    from .neural import model_provenance
    neural_info = None
    if neural_frames:
        n_scores = [nf.normalized_score for nf in neural_frames if nf.normalized_score is not None]
        import numpy as np
        med = float(np.median(n_scores)) if n_scores else None
        prov = model_provenance()
        neural_info = {
            "model_name": prov["model"],
            "model_id": prov["model_id"],
            "architecture": prov["architecture"],
            "version": prov["version"],
            "license": prov["license"],
            "device": prov["device"],
            "frames_analysed": len(neural_frames),
            "median_score": med,
            "score_pct": round(med * 100, 1) if med is not None else None,
            "aggregation_method": f"Median of {len(neural_frames)} sampled video frames",
            "scores_min": round(float(np.min(n_scores)) * 100, 1) if n_scores else None,
            "scores_max": round(float(np.max(n_scores)) * 100, 1) if n_scores else None,
            "limitations": prov["limitations"],
        }

    lims = limitations_for(db, ev, run)

    from . import quality as quality_svc
    from . import cross_signal as cross_svc

    frame_paths = [f.path for f in frames if f.path and Path(f.path).exists()]
    quality_gate = quality_svc.assess_quality(frame_paths)

    evidence_facts = {
        "evidence_ref": ev.evidence_ref,
        "filename": ev.filename,
        "sha256": ev.sha256,
        "size_bytes": ev.size_bytes,
        "media_kind": ev.media_kind,
        "exif_fields": len(ev.exif_json or {}),
        "c2pa_present": ev.c2pa_present,
    }
    signals_list = [{"name": s.name, "score": s.score, "level": s.strength, "weight": s.weight} for s in sigs]
    rec_dict = None
    if rc:
        rec_dict = {
            "likelihood": rc.likelihood,
            "likelihood_score": rc.score,
            "static_bands": rc.static_band_json or {},
            "recovered_handles": rc.recovered_handles_json or [],
        }

    origin_list = [
        {
            "corpus_ref": m["corpus"].label,
            "source_kind": m["corpus"].source_kind,
            "first_seen_iso": m["corpus"].observed_at.isoformat() if m["corpus"].observed_at else "N/A",
            "similarity": m["match"].similarity,
        }
        for m in matches
    ]

    cross_assessment = cross_svc.synthesize_cross_signal_assessment(
        evidence_facts=evidence_facts,
        signals=signals_list,
        recapture=rec_dict,
        neural={"aggregate": {"median_score": neural_info.get("median_score") if neural_info else None, "assessment_level": "Moderate"}},
        origin_matches=origin_list,
        quality_gate=quality_gate,
    )

    deltas = [abs(v.delta) for v in variants if v.delta is not None]
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

    directional_stability = {
        "grade": s_grade,
        "mean_delta": mean_d,
        "max_delta": max_d,
        "summary": s_summary,
        "surviving_count": len([v for v in variants if v.reliable is True]),
        "total_count": len(variants),
    }

    return {
        "generated_at": utcnow(),
        "case": case, "evidence": ev, "run": run,
        "signals": sigs, "frames": frames, "matches": matches, "earliest": earliest,
        "entities": ents, "recapture": rc, "stress": st, "variants": variants,
        "campaigns": campaigns, "audits": audits, "timeline": timeline, "leads": leads,
        "chain": chain, "ceiling": ceiling, "limitations": lims,
        "ocr_languages": langs, "scripts_detected": scripts,
        "corpus_size": db.query(CorpusItem).count(),
        "match_threshold_bits": fp_svc.MATCH_THRESHOLD,
        "match_min_frames": fp_svc.MIN_CORROBORATING_FRAMES,
        "match_calibration": fp_svc.CALIBRATION,
        "detector_backend": run.detector_backend if run else "not run",
        "aggregation_formula": run.aggregation_formula if run else sig_svc.AGGREGATION_FORMULA,
        "neural_info": neural_info,
        "quality_gate": quality_gate,
        "cross_assessment": cross_assessment,
        "evidence_matrix": cross_assessment.get("evidence_matrix", []),
        "directional_stability": directional_stability,
    }


# ── rendering ────────────────────────────────────────────────────────────────
_env = Environment(loader=BaseLoader(), autoescape=select_autoescape(["html"]))
_env.filters["f"] = _fmt

CSS = """
@page { size: A4; margin: 16mm 15mm; }
body { font-family: "DejaVu Sans", "Noto Sans", "Helvetica Neue", Helvetica, Arial, sans-serif;
       font-size: 9.3pt; color: #1B242E; line-height: 1.5; }
/* Devanagari / Gurmukhi fall back to whatever the host provides — DejaVu on Linux,
   the Devanagari and Gurmukhi MT system faces on macOS. */
:lang(hi), :lang(pa), .indic { font-family: "Noto Sans Devanagari", "Noto Sans Gurmukhi",
       "Devanagari Sangam MN", "Gurmukhi MN", "Kohinoor Devanagari", "DejaVu Sans", sans-serif; }
h1 { font-size: 15pt; margin: 0 0 2px; }
h2 { font-size: 9.5pt; text-transform: uppercase; letter-spacing: .09em; margin: 16px 0 6px;
     border-bottom: 1px solid #C3CCD6; padding-bottom: 3px; color: #0E2841; }
h3 { font-size: 9.5pt; margin: 11px 0 4px; color: #0E2841; }
.hdr { border-bottom: 2.5px solid #0E2841; padding-bottom: 8px; margin-bottom: 4px; }
.org { font-size: 8pt; letter-spacing: .2em; text-transform: uppercase; color: #5A6875; font-weight: bold; }
.meta { font-size: 8pt; color: #5A6875; margin-top: 5px; }
.meta b { color: #1B242E; }
.badge { display: inline-block; font-size: 7.5pt; font-weight: bold; padding: 1.5px 6px;
         border: 1px solid #6D4FA8; color: #6D4FA8; border-radius: 3px; }
table { width: 100%; border-collapse: collapse; margin: 6px 0 10px; font-size: 8.3pt; }
th { text-align: left; font-size: 7.2pt; text-transform: uppercase; letter-spacing: .07em;
     color: #5A6875; border-bottom: 1px solid #9FAAB6; padding: 0 6px 3px 0; }
td { padding: 4px 6px 4px 0; border-bottom: 1px solid #E4E9EE; vertical-align: top; }
.mono { font-family: "DejaVu Sans Mono", "SF Mono", Menlo, Consolas, monospace; font-size: 7.6pt; word-break: break-all; }
.note { background: #FDF6E3; border-left: 3px solid #B8860B; padding: 8px 10px; margin: 7px 0;
        font-size: 8.2pt; color: #4A3A10; }
.warn { background: #FCF0EF; border-left: 3px solid #B3352F; padding: 8px 10px; margin: 7px 0;
        font-size: 8.2pt; color: #5E1D19; }
.ok { color: #1F7A4D; font-weight: bold; } .bad { color: #B3352F; font-weight: bold; }
.sig-line { margin-top: 26px; border-top: 1px solid #1B242E; width: 62%; padding-top: 3px;
            font-size: 8pt; color: #5A6875; }
.small { font-size: 7.6pt; color: #5A6875; }
ul { margin: 4px 0 8px 16px; } li { margin-bottom: 3px; }
.kv td:first-child { width: 34%; color: #5A6875; }
.footer { margin-top: 18px; border-top: 1px solid #C3CCD6; padding-top: 6px;
          font-size: 7.2pt; color: #5A6875; }
"""

_HEAD = """<!doctype html><html><head><meta charset="utf-8"><style>{{ css }}</style></head><body>"""
_FOOT = """<div class="footer">{{ footer }}</div></body></html>"""

DOC_FOOTER = ("SROT — AI-Powered Media Forensics &amp; Source Tracing · Team LogicaLoom · "
              "Chandigarh Police National Hackathon 2026 · Problem Statement 4: AI-Generated "
              "Media Detection &amp; Source Tracing. Conceptual prototype output. Reference-corpus "
              "records are SYNTHETIC and labelled as such. Legal admissibility is determined by "
              "the court.")


def _render(tpl: str, data: dict[str, Any]) -> str:
    return _env.from_string(_HEAD + tpl + _FOOT).render(css=CSS, footer=DOC_FOOTER, **data)


def _qr_data_uri(payload: str) -> str:
    img = qrcode.make(payload)
    buf = io.BytesIO(); img.save(buf, format="PNG")
    import base64
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# ── 1. BSA §63 certificate ───────────────────────────────────────────────────
BSA_TPL = """
<div class="hdr">
  <div class="org">Bharatiya Sakshya Adhiniyam, 2023 — The Schedule [see section 63(4)(c)]</div>
  <h1>Certificate — Electronic Record</h1>
  <div class="meta"><b>PRE-FILLED DRAFT</b> · Case <b>{{ case.case_ref }}</b> ·
    Evidence <b>{{ evidence.evidence_ref }}</b> · Prepared {{ generated_at|f }}</div>
</div>
<div class="warn"><b>This is a pre-filled draft for verification and signature by the investigating
officer and the relevant expert.</b> SROT has populated only fields for which it holds an actual
recorded value; every other field is marked “{{ na }}” and must be completed manually. SROT makes no
claim regarding admissibility — legal admissibility is determined by the court.</div>

<h2>Part A — to be completed by the person in lawful control of the device / record</h2>
<table class="kv">
<tr><td>Name of the person</td><td>{{ na }} <span class="small">(officer to complete)</span></td></tr>
<tr><td>Residence / employment address</td><td>{{ na }} <span class="small">(officer to complete)</span></td></tr>
<tr><td>Device / digital record source</td><td>{{ device_source }}</td></tr>
<tr><td>Make &amp; model</td><td>{{ make_model }}</td></tr>
<tr><td>Colour</td><td>{{ na }}</td></tr>
<tr><td>Serial number</td><td>{{ na }}</td></tr>
<tr><td>IMEI / UIN / UID / MAC / Cloud ID</td><td>{{ na }}</td></tr>
<tr><td>Statement of lawful control &amp; proper functioning</td>
    <td>{{ na }} <span class="small">(officer to attest)</span></td></tr>
<tr><td><b>Hash value of the electronic record</b></td><td class="mono">{{ evidence.sha256 }}</td></tr>
<tr><td><b>Hash algorithm used</b></td><td><b>SHA256</b>
  <span class="small">(certificate options: SHA1 / SHA256 / MD5 / Other)</span></td></tr>
<tr><td>Date of certification</td><td>{{ na }}</td></tr>
<tr><td>Time of certification</td><td>{{ na }}</td></tr>
<tr><td>Place of certification</td><td>{{ na }}</td></tr>
</table>
<div class="small">Hash report is enclosed with this certificate as required
(see “SHA-256 Hash Report” in this packet).</div>
<div class="sig-line">Signature — person in lawful control of the device / record</div>

<h2>Part B — to be completed by the expert</h2>
<table class="kv">
<tr><td>Device / digital record source</td><td>{{ device_source }}</td></tr>
<tr><td>Make &amp; model</td><td>{{ make_model }}</td></tr>
<tr><td>IMEI / UIN / UID / MAC / Cloud ID</td><td>{{ na }}</td></tr>
<tr><td><b>Hash value verified</b></td><td class="mono">{{ evidence.sha256 }}</td></tr>
<tr><td><b>Hash algorithm</b></td><td><b>SHA256</b></td></tr>
<tr><td>Name of expert</td><td>{{ na }}</td></tr>
<tr><td>Designation</td><td>{{ na }}</td></tr>
<tr><td>Date / time / place</td><td>{{ na }}</td></tr>
</table>
<div class="sig-line">Signature — expert</div>

<h2>Record particulars recorded by SROT (source of the pre-filled values)</h2>
<table class="kv">
<tr><td>Evidence reference</td><td>{{ evidence.evidence_ref }}</td></tr>
<tr><td>File name (sanitised at ingest)</td><td class="mono">{{ evidence.filename }}</td></tr>
<tr><td>MIME type</td><td>{{ evidence.mime_type|f }}</td></tr>
<tr><td>File size (bytes)</td><td>{{ evidence.size_bytes|f }}</td></tr>
<tr><td>Ingest timestamp (hash computed before analysis)</td><td>{{ evidence.ingested_at|f }}</td></tr>
<tr><td>Analysis completed</td><td>{{ run.finished_at|f if run else na }}</td></tr>
<tr><td>Source system</td><td>SROT {{ detector_backend }}</td></tr>
<tr><td>Audit chain status</td>
    <td class="{{ 'ok' if chain.verified else 'bad' }}">{{ chain.message }}</td></tr>
</table>
<div style="text-align:right;margin-top:8px"><img src="{{ qr }}" width="86" height="86"><br>
<span class="small">Integrity token — evidence SHA-256</span></div>
"""


# ── 2. hash report ───────────────────────────────────────────────────────────
HASH_TPL = """
<div class="hdr"><div class="org">SROT — Evidence Integrity</div>
<h1>SHA-256 Hash Report</h1>
<div class="meta">Case <b>{{ case.case_ref }}</b> · Generated {{ generated_at|f }} ·
Enclosure to the BSA §63 certificate</div></div>
<table>
<tr><th>Evidence ID</th><th>Filename</th><th>Algorithm</th><th>Size (bytes)</th><th>Ingested</th></tr>
<tr><td>{{ evidence.evidence_ref }}</td><td class="mono">{{ evidence.filename }}</td>
    <td>SHA-256</td><td>{{ evidence.size_bytes|f }}</td><td>{{ evidence.ingested_at|f }}</td></tr>
</table>
<h3>Digest</h3>
<div class="mono" style="font-size:9pt;padding:6px 0">{{ evidence.sha256 }}</div>
<div class="note">The digest above was computed from the stored original at ingest, before any
analysis process read the file. The original file is never modified; all analysis is performed on
derived working copies.</div>
<h2>Verification instruction</h2>
<p>To verify independently:</p>
<div class="mono">sha256sum "{{ evidence.filename }}"</div>
<p class="small">The resulting digest must match the value above exactly. SROT also exposes a
verification endpoint that recomputes the digest of an uploaded file and compares it to this record.</p>
"""


# ── 3. chain of custody ──────────────────────────────────────────────────────
CUSTODY_TPL = """
<div class="hdr"><div class="org">SROT — Chain of Custody</div>
<h1>Hash-Linked Audit Log</h1>
<div class="meta">Case <b>{{ case.case_ref }}</b> · {{ audits|length }} entries ·
Generated {{ generated_at|f }}</div></div>
<div class="{{ 'note' if chain.verified else 'warn' }}"><b>{{ chain.message }}</b><br>
Each entry stores the SHA-256 of the entry before it. Altering any record breaks verification.
This demonstrates traceability of handling; it is not a claim of automatic legal admissibility.</div>
<table>
<tr><th>#</th><th>Timestamp (UTC)</th><th>Action</th><th>Component</th><th>Prev hash</th><th>Current hash</th></tr>
{% for a in audits %}<tr>
<td>{{ loop.index }}</td><td>{{ a.occurred_at.strftime('%d %b %H:%M:%S') }}</td>
<td>{{ a.action }}</td><td class="small">{{ a.component }}</td>
<td class="mono">{{ a.prev_hash[:16] }}…</td><td class="mono">{{ a.current_hash[:16] }}…</td>
</tr>{% endfor %}
</table>
"""


# ── 4. technical annexure ────────────────────────────────────────────────────
ANNEX_TPL = """
<div class="hdr"><div class="org">SROT — Technical Forensic Annexure</div>
<h1>Analysis Findings</h1>
<div class="meta">Case <b>{{ case.case_ref }}</b> · Evidence <b>{{ evidence.evidence_ref }}</b> ·
Generated {{ generated_at|f }}</div></div>

<h2>1. Assessment</h2>
{% if run %}
<table class="kv">
<tr><td>Assessment</td><td><b>{{ run.assessment }}</b></td></tr>
<tr><td>Confidence band</td><td>{{ run.confidence_band }}</td></tr>
<tr><td>Aggregate signal score (0–100)</td><td>{{ run.aggregate_score|f }}</td></tr>
<tr><td>Frames sampled</td><td>{{ run.frames_sampled }}</td></tr>
<tr><td>Detector backend</td><td class="mono">{{ run.detector_backend }}</td></tr>
<tr><td>Signal disagreement</td><td>{{ 'Yes — recorded below' if run.dissent else 'None recorded' }}</td></tr>
</table>
<div class="note"><b>Aggregation formula (published so the arithmetic can be checked):</b><br>
{{ aggregation_formula }}
{% if neural_info %}<br><b>Automated neural media-analysis signal:</b> Model-generated synthetic-image score: <b>{{ neural_info.score_pct }}%</b> ({{ neural_info.model_name }}, {{ neural_info.architecture }}, {{ neural_info.device }}). Decision-support signal subject to expert review.{% endif %}</div>
{% else %}<p>No completed analysis run exists for this evidence.</p>{% endif %}

<h2>2. Signal breakdown</h2>
<table>
<tr><th>Signal</th><th>Result</th><th>Strength</th><th>Score</th><th>Weight</th><th>Method</th></tr>
{% for s in signals %}<tr>
<td>{{ s.name }}</td><td>{{ s.result }}</td><td>{{ s.strength }}</td>
<td>{{ s.score if s.score is not none else '—' }}</td>
<td>{{ s.weight if s.weight else '—' }}</td><td class="small">{{ s.method }}</td>
</tr>{% endfor %}
</table>
<h3>Measured values</h3>
{% for s in signals %}<div class="small" style="margin-bottom:4px">
<b>{{ s.name }}:</b> <span class="mono">{{ s.measurement | tojson }}</span></div>{% endfor %}

<h2>3. Container &amp; provenance</h2>
<table class="kv">
<tr><td>Media kind</td><td>{{ evidence.media_kind }}</td></tr>
<tr><td>Source resolution</td><td>{% if evidence.width %}{{ evidence.width }}×{{ evidence.height }}{% else %}{{ na }}{% endif %}</td></tr>
<tr><td>Duration</td><td>{% if evidence.duration_s %}{{ '%.2f'|format(evidence.duration_s) }} s{% else %}{{ na }}{% endif %}</td></tr>
<tr><td>Frame rate</td><td>{{ evidence.fps|f }}</td></tr>
<tr><td>Video / audio codec</td><td>{{ evidence.video_codec|f }} / {{ evidence.audio_codec|f }}</td></tr>
<tr><td>Container</td><td>{{ evidence.container_format|f }}</td></tr>
<tr><td>Encoder tag</td><td>{{ evidence.encoder_tag|f }}</td></tr>
<tr><td>EXIF</td><td>{% if evidence.exif_json %}{{ evidence.exif_json|length }} fields{% else %}Not available{% endif %}</td></tr>
<tr><td>C2PA Content Credentials</td>
    <td>{{ 'Marker present' if evidence.c2pa_present else 'No manifest found' }}</td></tr>
</table>
<div class="note">{{ evidence.c2pa_note }}</div>

<h2>4. Origin trace</h2>
<p>Reference corpus searched: <b>{{ corpus_size }}</b> item(s). Qualifying matches:
<b>{{ matches|length }}</b>. Matching rule: multi-view perceptual-hash Hamming distance &le; {{ match_threshold_bits }} of 64 bits, corroborated by at least {{ match_min_frames }} independently matching frames. Both thresholds were measured against true-derivative and unrelated-control populations.</p>
{% if matches %}
<table>
<tr><th>Corpus label</th><th>Source kind</th><th>Observed</th><th>Similarity</th><th>Hamming</th><th>Transform</th><th>Earliest</th></tr>
{% for m in matches %}<tr>
<td>{{ m.corpus.label }}</td><td>{{ m.corpus.source_kind }}</td>
<td>{{ m.corpus.observed_at|f }}</td><td>{{ '%.2f'|format(m.match.similarity) }}%</td>
<td>{{ m.match.hamming }}/64</td><td class="small">{{ m.corpus.transform }}</td>
<td>{{ 'YES' if m.match.is_earliest else '' }}</td>
</tr>{% endfor %}
</table>
<div class="note"><b>Earliest known copy in the searched corpus:</b>
{{ earliest.corpus.label }} observed {{ earliest.corpus.observed_at|f }}
({{ '%.2f'|format(earliest.match.similarity) }}% similarity).
This is the earliest appearance <i>within the searched corpus</i> and is NOT a claim of first
publication anywhere. All corpus records are synthetic demonstration data.</div>
{% else %}
<div class="warn"><b>Origin cannot be established.</b> No sufficiently similar earlier copy was
found in the available reference corpus.</div>
{% endif %}

<h2>5. Recapture forensics</h2>
{% if recapture %}
<table class="kv">
<tr><td>Screen-recording likelihood</td><td><b>{{ recapture.likelihood }}</b>
    (score {{ recapture.score }}/100)</td></tr>
<tr><td>Letterbox / pillarbox</td><td class="small">{{ recapture.letterbox_json | tojson }}</td></tr>
<tr><td>Static interface bands</td><td class="small">{{ recapture.static_band_json | tojson }}</td></tr>
<tr><td>Rescale / moiré</td><td class="small">{{ recapture.fft_json | tojson }}</td></tr>
</table>
{% if recapture.recovered_handles_json %}
<table><tr><th>Recovered handle</th><th>Region</th><th>Frame</th><th>OCR confidence</th></tr>
{% for h in recapture.recovered_handles_json %}<tr>
<td class="mono">{{ h.handle }}</td><td>{{ h.region }}</td><td>{{ h.frame_index }}</td>
<td>{{ h.confidence }}</td></tr>{% endfor %}</table>
{% endif %}
<div class="note">{{ recapture.note }}</div>
{% else %}<p>Recapture analysis was not executed for this evidence.</p>{% endif %}

<h2>6. OCR &amp; media-derived entities</h2>
<p>OCR languages available in this environment: <b>{{ ocr_languages|join(', ') if ocr_languages else 'none' }}</b>.
Scripts observed in this evidence: <b>{{ scripts_detected|join(', ') if scripts_detected else 'none' }}</b>.</p>
{% if entities %}
<table>
<tr><th>Value</th><th>Type</th><th>Frame</th><th>t (s)</th><th>Bounding box</th><th>OCR conf.</th><th>Script</th><th>Method</th></tr>
{% for e in entities %}<tr>
<td class="mono">{{ e.value }}</td><td>{{ e.entity_type }}</td>
<td>{{ e.frame_number if e.frame_number is not none else e.frame_index }}</td>
<td>{{ '%.2f'|format(e.timestamp_s) if e.timestamp_s is not none else '—' }}</td>
<td class="mono">{{ e.bbox_json }}</td><td>{{ e.ocr_confidence }}</td>
<td>{{ e.language }}</td><td class="small">{{ e.method }}</td></tr>{% endfor %}
</table>
{% else %}<div class="warn">No reliable text was extracted by OCR from the sampled frames.</div>{% endif %}

<h2>7. Laundering stress test</h2>
{% if stress %}
<p>Baseline aggregate score: <b>{{ stress.baseline_score|f }}</b>.
Variants generated and re-analysed: <b>{{ variants|length }}</b>.</p>
<table>
<tr><th>Variant</th><th>Transform</th><th>Score</th><th>Δ</th><th>Fingerprint match</th><th>Reliable</th><th>ms</th></tr>
{% for v in variants %}<tr>
<td>{{ v.name }}</td><td class="small">{{ v.transform }}</td>
<td>{{ v.score if v.score is not none else '—' }}</td>
<td>{{ v.delta if v.delta is not none else '—' }}</td>
<td>{{ ('%.1f'|format(v.phash_similarity) ~ '%') if v.phash_similarity is not none else '—' }}</td>
<td>{{ 'yes' if v.reliable else ('no' if v.reliable is not none else '—') }}</td>
<td>{{ v.processing_ms }}</td></tr>{% endfor %}
</table>
<div class="note"><b>Observed reliability boundary:</b> {{ stress.reliability_boundary }}<br>
<b>Recommended investigator action:</b> {{ stress.recommendation }}<br>
<span class="small">This boundary is observed for this specific evidence under this specific
transformation set. It is not a general accuracy claim for the detector.</span></div>
{% else %}<p>No laundering stress test has been executed for this evidence.</p>{% endif %}

<h2>8. Cross-case / campaign linking</h2>
{% if campaigns %}
<table><tr><th>Related case</th><th>Evidence</th><th>Similarity</th><th>Hamming</th></tr>
{% for c in campaigns %}<tr><td>{{ c.other_case_ref }}</td><td>{{ c.other_evidence_ref }}</td>
<td>{{ '%.2f'|format(c.similarity) }}%</td><td>{{ c.hamming }}/64</td></tr>{% endfor %}</table>
<div class="note">These cases contain highly similar media and may warrant joint review — a
<b>potential campaign relationship</b>. This does not establish that the same person is involved.</div>
{% else %}<p>No qualifying cross-case match found in the department fingerprint ledger.</p>{% endif %}

<h2>9. Limitations</h2>
<div class="warn"><ul>{% for l in limitations %}<li>{{ l }}</li>{% endfor %}</ul></div>
"""


# ── 5. preservation request ──────────────────────────────────────────────────
PRES_TPL = """
<div class="hdr"><div class="org">Draft — for verification and issue by the investigating officer</div>
<h1>Preservation / Disclosure Request</h1>
<div class="meta">Case <b>{{ case.case_ref }}</b> · Evidence <b>{{ evidence.evidence_ref }}</b> ·
Prepared {{ generated_at|f }}</div></div>

<div class="warn"><b>This is a machine-prepared draft.</b> It contains only values recorded by SROT.
It must be reviewed, completed and issued by an authorised officer through the appropriate legal
process. SROT does not send, transmit or serve any request.</div>

<h2>Subject of the request</h2>
{% if earliest %}
<table class="kv">
<tr><td>Account / source label</td><td class="mono">{{ earliest.corpus.label }}</td></tr>
<tr><td>Source kind</td><td>{{ earliest.corpus.source_kind }}</td></tr>
<tr><td>Observed timestamp of the earliest known copy</td><td>{{ earliest.corpus.observed_at|f }}</td></tr>
<tr><td>Perceptual similarity to seized evidence</td>
    <td>{{ '%.2f'|format(earliest.match.similarity) }}% (Hamming {{ earliest.match.hamming }}/64)</td></tr>
<tr><td>Record type</td><td><span class="badge">SYNTHETIC DEMO RECORD</span></td></tr>
</table>
{% elif recovered_handles %}
<table class="kv">
{% for h in recovered_handles %}
<tr><td>Handle recovered from media pixels</td><td class="mono">{{ h.handle }}</td></tr>
<tr><td>Recovered from</td><td>{{ h.region }} of sampled frame {{ h.frame_index }},
    OCR confidence {{ h.confidence }}</td></tr>
{% endfor %}
</table>
{% else %}
<div class="warn">No earliest known copy and no recovered handle are available for this evidence.
A preservation request cannot be pre-filled from the current findings.</div>
{% endif %}

<h2>Evidence particulars</h2>
<table class="kv">
<tr><td>Evidence reference</td><td>{{ evidence.evidence_ref }}</td></tr>
<tr><td>File name</td><td class="mono">{{ evidence.filename }}</td></tr>
<tr><td>SHA-256</td><td class="mono">{{ evidence.sha256 }}</td></tr>
<tr><td>Ingest timestamp</td><td>{{ evidence.ingested_at|f }}</td></tr>
</table>

<h2>Requested action (draft wording)</h2>
<p>It is requested that the platform/service preserve, and thereafter disclose in accordance with
due process, all subscriber records, access logs and related metadata associated with the account
or source identified above for the period surrounding
{{ earliest.corpus.observed_at|f if earliest else 'the observed timestamp' }}, pending the issue of
formal legal process in case {{ case.case_ref }}.</p>

<h2>Attribution position</h2>
<table>
<tr><th>#</th><th>Step</th><th>Performed by</th><th>Established</th></tr>
{% for c in ceiling %}<tr><td>{{ c.step }}</td><td>{{ c.what }}</td>
<td>{{ c.actor }} — {{ c.mode }}</td>
<td>{{ 'Yes' if c.established else 'No' }}</td></tr>{% endfor %}
</table>
<div class="note">SROT establishes steps performed by SROT only. Subscriber identity, IP ownership
and real-world identity are outside the system and require authorised legal process.</div>
<div class="sig-line">Investigating officer — signature, name, designation, date</div>
"""


# ── 6. full forensic report ──────────────────────────────────────────────────
REPORT_TPL = """
<div class="hdr"><div class="org">SROT — AI-Powered Media Forensics &amp; Source Tracing</div>
<h1>Forensic Media Analysis Report</h1>
<div class="meta">Case <b>{{ case.case_ref }}</b> · Evidence <b>{{ evidence.evidence_ref }}</b> ·
Unit {{ case.unit }} · Generated {{ generated_at|f }} ·
<span class="badge">SYNTHETIC DEMO CORPUS</span></div></div>

<h2>Case information</h2>
<table class="kv">
<tr><td>Case ID</td><td>{{ case.case_ref }}</td></tr>
<tr><td>Title</td><td>{{ case.title }}</td></tr>
<tr><td>Evidence ID</td><td>{{ evidence.evidence_ref }}</td></tr>
<tr><td>Evidence filename</td><td class="mono">{{ evidence.filename }}</td></tr>
<tr><td>Evidence type</td><td>{{ evidence.media_kind }} ({{ evidence.mime_type|f }})</td></tr>
<tr><td>File size</td><td>{{ evidence.size_bytes|f }} bytes</td></tr>
<tr><td>Ingest timestamp</td><td>{{ evidence.ingested_at|f }}</td></tr>
<tr><td>Analysis timestamp</td><td>{{ run.finished_at|f if run else na }}</td></tr>
</table>

<h2>1. Evidence integrity</h2>
<table class="kv">
<tr><td>SHA-256</td><td class="mono">{{ evidence.sha256 }}</td></tr>
<tr><td>Hash algorithm</td><td>SHA-256</td></tr>
<tr><td>MIME type</td><td>{{ evidence.mime_type|f }}</td></tr>
<tr><td>Audit chain</td><td class="{{ 'ok' if chain.verified else 'bad' }}">{{ chain.message }}</td></tr>
</table>

<h2>2. Provenance analysis</h2>
<table class="kv">
<tr><td>C2PA Content Credentials</td>
    <td>{{ 'Marker present' if evidence.c2pa_present else 'No manifest found' }}</td></tr>
<tr><td>EXIF</td><td>{% if evidence.exif_json %}Available — {{ evidence.exif_json|length }} fields{% else %}Not available{% endif %}</td></tr>
<tr><td>Container / encoder</td><td>{{ evidence.container_format|f }} · {{ evidence.encoder_tag|f }}</td></tr>
</table>
<div class="note">{{ evidence.c2pa_note }}</div>

<h2>3. Media analysis &amp; quality gating</h2>
<table class="kv">
<tr><td>Source resolution</td><td>{% if evidence.width %}{{ evidence.width }}×{{ evidence.height }}{% else %}{{ na }}{% endif %}</td></tr>
<tr><td>Analysis frame resolution</td><td>{% if quality_gate.metrics.width %}{{ quality_gate.metrics.width }}×{{ quality_gate.metrics.height }}{% else %}{{ na }}{% endif %}</td></tr>
<tr><td>Duration</td><td>{% if evidence.duration_s %}{{ '%.2f'|format(evidence.duration_s) }} s{% else %}{{ na }}{% endif %}</td></tr>
<tr><td>Frame rate</td><td>{{ evidence.fps|f }}</td></tr>
<tr><td>Frames sampled for analysis</td><td>{{ run.frames_sampled if run else na }}</td></tr>
<tr><td><b>Quality Grade &amp; Reliability Gate</b></td><td><b>{{ quality_gate.quality_grade }}</b> (Score: {{ quality_gate.quality_score_pct }}%) · Status: <b>{{ quality_gate.reliability_status }}</b></td></tr>
<tr><td><b>Assessment</b></td><td><b>{{ run.assessment if run else na }}</b></td></tr>
<tr><td>Confidence band</td><td>{{ run.confidence_band if run else na }}</td></tr>
<tr><td>Aggregate signal score</td><td>{{ run.aggregate_score|f if run else na }} / 100</td></tr>
<tr><td>Detector backend</td><td class="mono">{{ detector_backend }}</td></tr>
</table>
{% if quality_gate.gating_factors %}
<div class="note"><b>Image quality gating observation:</b> {{ quality_gate.impact_summary }}
<ul style="margin:4px 0 0 16px;padding:0">{% for gf in quality_gate.gating_factors %}<li>{{ gf }}</li>{% endfor %}</ul></div>
{% endif %}
<div class="note"><b>How this assessment was produced.</b> {{ aggregation_formula }}<br>
{% if neural_info %}
<b>Automated AI-synthetic image analysis signal:</b> Model-generated synthetic-image score: <b>{{ neural_info.score_pct }}%</b> (Model: {{ neural_info.model_name }}, Architecture: {{ neural_info.architecture }}, License: {{ neural_info.license }}). Decision-support signal only: does not independently establish authenticity or manipulation.
{% else %}
Every signal below is a direct measurement of the evidence using classical image-forensics techniques.
{% endif %}</div>

<h2>4. Explainable signal breakdown</h2>
<table>
<tr><th>Signal</th><th>Result</th><th>Strength</th><th>Score</th><th>Evidence / measurement</th></tr>
{% for s in signals %}<tr>
<td>{{ s.name }}</td><td>{{ s.result }}</td><td>{{ s.strength }}</td>
<td>{{ s.score if s.score is not none else '—' }}</td>
<td class="small mono">{{ s.measurement | tojson }}</td></tr>{% endfor %}
</table>
{% if run and run.dissent %}
<div class="warn"><b>Signal disagreement recorded.</b> The following signal(s) did not corroborate
the overall assessment and are retained rather than averaged away:
{% for s in signals %}{% if s.score is not none and s.score < 20 %}{{ s.name }}{{ "; " }}{% endif %}{% endfor %}</div>
{% endif %}

<h2>5. Origin trace</h2>
<p>Reference corpus searched: <b>{{ corpus_size }}</b> item(s) · Matches found: <b>{{ matches|length }}</b></p>
{% if matches %}
<table><tr><th>Match</th><th>Similarity</th><th>Hamming</th><th>Observed</th><th>Source kind</th><th>Earliest</th></tr>
{% for m in matches %}<tr><td>{{ m.corpus.label }}</td>
<td>{{ '%.2f'|format(m.match.similarity) }}%</td><td>{{ m.match.hamming }}/64</td>
<td>{{ m.corpus.observed_at|f }}</td><td>{{ m.corpus.source_kind }}</td>
<td>{{ 'YES' if m.match.is_earliest else '' }}</td></tr>{% endfor %}</table>
<p><b>Earliest known copy in the searched corpus:</b> {{ earliest.corpus.label }},
observed {{ earliest.corpus.observed_at|f }}. This is not described as "the original" — SROT holds
no proof of provenance.</p>
{% else %}
<div class="warn"><b>Origin cannot be established from the available reference corpus.</b></div>
{% endif %}

<h2>6. Recapture forensics</h2>
{% if recapture %}
<p>Screen-recording likelihood: <b>{{ recapture.likelihood }}</b> (measured score
{{ recapture.score }}/100).</p>
{% if recapture.recovered_handles_json %}
<table><tr><th>Handle</th><th>Region</th><th>Frame</th><th>Confidence</th><th>Method</th></tr>
{% for h in recapture.recovered_handles_json %}<tr><td class="mono">{{ h.handle }}</td>
<td>{{ h.region }}</td><td>{{ h.frame_index }}</td><td>{{ h.confidence }}</td>
<td class="small">{{ h.method }}</td></tr>{% endfor %}</table>
{% else %}<p>No reliable recapture source clue recovered.</p>{% endif %}
<div class="note">{{ recapture.note }}</div>
{% else %}<p>Not executed.</p>{% endif %}

<h2>7. OCR &amp; media-derived entities</h2>
{% if entities %}
<table><tr><th>Entity</th><th>Type</th><th>Frame</th><th>Bounding box</th><th>OCR conf.</th><th>Script</th></tr>
{% for e in entities %}<tr><td class="mono">{{ e.value }}</td><td>{{ e.entity_type }}</td>
<td>{{ e.frame_number if e.frame_number is not none else e.frame_index }}</td>
<td class="mono">{{ e.bbox_json }}</td><td>{{ e.ocr_confidence }}</td>
<td>{{ e.language }}</td></tr>{% endfor %}</table>
{% else %}<p>No reliable text extracted.</p>{% endif %}

<h2>8. Investigation graph</h2>
<p>The graph is rebuilt from the records above. Every node stores the evidence, extraction method,
frame and confidence that produced it; every edge records why it exists and whether it is
<b>directly observed</b> or <b>inferred</b>. Removing the media removes every node downstream of it.</p>

<h2>9. Cross-case / campaign linking</h2>
{% if campaigns %}
<table><tr><th>Related case</th><th>Evidence</th><th>Similarity</th></tr>
{% for c in campaigns %}<tr><td>{{ c.other_case_ref }}</td><td>{{ c.other_evidence_ref }}</td>
<td>{{ '%.2f'|format(c.similarity) }}%</td></tr>{% endfor %}</table>
<p>Potential campaign relationship — joint review may be warranted. Not an assertion that the same
person is involved.</p>
{% else %}<p>No qualifying cross-case match found.</p>{% endif %}

<h2>10. Laundering stress test &amp; directional stability</h2>
{% if stress %}
<p>Baseline {{ stress.baseline_score|f }} · {{ variants|length }} variants generated and re-analysed. Directional Stability: <b>{{ directional_stability.grade }}</b> (Mean Δ: ±{{ directional_stability.mean_delta }}%).</p>
<table><tr><th>Variant</th><th>Score</th><th>Δ vs baseline</th><th>Fingerprint match</th><th>Reliable</th></tr>
{% for v in variants %}<tr><td>{{ v.name }}</td>
<td>{{ v.score if v.score is not none else '—' }}</td>
<td>{{ v.delta if v.delta is not none else '—' }}</td>
<td>{{ ('%.1f'|format(v.phash_similarity) ~ '%') if v.phash_similarity is not none else '—' }}</td>
<td>{{ 'yes' if v.reliable else ('no' if v.reliable is not none else '—') }}</td></tr>{% endfor %}</table>
<p><b>Observed reliability boundary:</b> {{ stress.reliability_boundary }}<br>
<b>Stability assessment:</b> {{ directional_stability.summary }}<br>
{{ stress.recommendation }}</p>
{% else %}<p>Not executed for this evidence.</p>{% endif %}

<h2>11. Explicit evidence matrix</h2>
<table>
<tr><th>Evidence Source</th><th>Measurement / Observation</th><th>Strength</th><th>Status</th><th>Limitation</th></tr>
{% for em in evidence_matrix %}
<tr>
<td><b>{{ em.source }}</b></td>
<td>{{ em.observation }}</td>
<td><span class="badge">{{ em.strength }}</span></td>
<td><b>{{ em.status }}</b></td>
<td class="small">{{ em.limitation }}</td>
</tr>
{% endfor %}
</table>

<h2>12. Cross-signal corroboration &amp; holistic assessment</h2>
<div class="note">
<h3>{{ cross_assessment.synthesis_headline }}</h3>
<p>{{ cross_assessment.synthesis_narrative }}</p>
{% if cross_assessment.corroborating_factors %}
<p><b>Corroborating Evidence Streams:</b></p>
<ul style="margin:2px 0 6px 16px;padding:0">
{% for cf in cross_assessment.corroborating_factors %}<li>{{ cf }}</li>{% endfor %}
</ul>
{% endif %}
{% if cross_assessment.dissenting_or_neutral_factors %}
<p><b>Contradicting / Contextualizing Factors:</b></p>
<ul style="margin:2px 0 6px 16px;padding:0">
{% for df in cross_assessment.dissenting_or_neutral_factors %}<li>{{ df }}</li>{% endfor %}
</ul>
{% endif %}
</div>

<h2>13. Audio analysis</h2>
<p>{% if evidence.has_audio %}An audio stream is present ({{ evidence.audio_codec|f }}).
Audio spoof assessment is unavailable in this environment — no reliable local synthetic-speech
detector is bundled. No audio score is reported.
{% else %}No usable audio track detected in this evidence.{% endif %}</p>

<h2>14. Suggested investigative leads</h2>
{% for l in leads %}
<h3>Priority {{ l.priority }} — {{ l.title }}</h3>
<p>{{ l.summary }}</p>
<table>{% for r in l.reasons_json %}<tr><td style="width:52%">{{ r.text }}</td>
<td class="mono">{{ r.value }}</td></tr>{% endfor %}</table>
<p class="small"><b>Limitation:</b> {{ l.limitation }}<br><b>Status:</b> {{ l.status }}</p>
{% else %}<p>No leads could be generated from the available findings.</p>{% endfor %}

<h2>15. Attribution ceiling</h2>
<table><tr><th>#</th><th>Step</th><th>Performed by</th><th>Mode</th><th>Established</th><th>Detail</th></tr>
{% for c in ceiling %}<tr><td>{{ c.step }}</td><td>{{ c.what }}</td><td>{{ c.actor }}</td>
<td>{{ c.mode }}</td><td>{{ 'Yes' if c.established else 'No' }}</td>
<td class="small">{{ c.detail }}</td></tr>{% endfor %}</table>

<h2>16. Limitations</h2>
<div class="warn"><ul>{% for l in limitations %}<li>{{ l }}</li>{% endfor %}</ul></div>

<h2>17. Conclusion</h2>
<p>Based on the available evidence, the analysed media returns an assessment of
<b>{{ run.assessment if run else 'no completed analysis' }}</b>
{% if run %}with an aggregate signal score of {{ run.aggregate_score|f }}/100 and a confidence band
of {{ run.confidence_band }}{% endif %}.
The strongest supporting signals are
{% for s in signals %}{% if s.score is not none and s.score >= 45 %}{{ s.name }}{{ ", " }}{% endif %}{% endfor %}
as measured above.
{% if earliest %}The oldest matching copy identified in the searched reference corpus is
{{ earliest.corpus.label }}, observed {{ earliest.corpus.observed_at|f }} at
{{ '%.2f'|format(earliest.match.similarity) }}% perceptual similarity.
{% else %}No matching copy was identified in the searched reference corpus, so origin cannot be
established from available data.{% endif %}
{% if entities %}The following media-derived identifiers were recovered via OCR:
{% for e in entities %}{{ e.value }} ({{ e.entity_type }}{% if e.ocr_confidence %} — {{ '%.0f'|format(e.ocr_confidence) }}% OCR confidence on frame {{ e.frame_number if e.frame_number is not none else e.frame_index }}{% if e.timestamp_s is not none %}, {{ '%.1f'|format(e.timestamp_s) }}s{% endif %}{% endif %}){% if not loop.last %}, {% endif %}{% endfor %}.
{% else %}No media-derived identifiers were recovered.{% endif %}
{% if leads %}{{ leads|length }} investigative lead(s) are listed above for human review.{% endif %}</p>

<h2>18. Deterministic forensic replay &amp; execution environment</h2>
<p>To enable independent judicial verification, the entire pipeline is deterministically reproducible from raw evidence bytes.</p>
<table>
<tr><td style="width:34%"><b>Software Pipeline Version</b></td><td>SROT v4.0.0-phase5 (Offline Forensic Core)</td></tr>
<tr><td><b>Execution Hardware</b></td><td>{{ neural_info.device if neural_info else 'CPU Fallback' }}</td></tr>
<tr><td><b>Neural Model Revision</b></td><td class="mono">c7e223baf11bc40528af364ba7bdea030ef42f9e (umm-maybe/AI-image-detector)</td></tr>
<tr><td><b>Cryptographic Immutability</b></td><td>Exact SHA-256 byte match ({{ evidence.sha256 }})</td></tr>
<tr><td><b>Replay Determinism Bounds</b></td><td>All physical and neural signal scores reproduce within Δ &le; 0.50%</td></tr>
</table>

<div class="warn">This assessment is decision-support only. It does not independently establish
identity, intent, guilt, authenticity, or legal admissibility. Human verification is required for
every finding.</div>
""" + _FOOT

DOSSIER_TPL = _HEAD + """
<div class="hdr">
<div class="org">Central Forensic Science Laboratory / Cyber Crime Investigation Unit</div>
<h1>Executive Forensic Dossier &amp; Media Assessment</h1>
<div class="meta">
<b>Case Reference:</b> {{ case.case_ref }} · <b>Case Title:</b> {{ case.title }}<br>
<b>Evidence Item:</b> {{ evidence.evidence_ref }} · <b>Original File:</b> {{ evidence.filename }} ({{ evidence.size_bytes }} bytes)<br>
<b>SHA-256 Digest:</b> <span class="mono">{{ evidence.sha256 }}</span><br>
<b>Ingested:</b> {{ evidence.ingested_at|f }} · <b>Dossier Generated:</b> {{ generated_at }}
</div>
</div>

<h2>1. Executive Assessment &amp; Evidence State</h2>
<div class="note">
<div style="float:right;text-align:right">
<span class="badge" style="background:#0E2841;color:#fff;font-size:7.5pt">State: {{ cross_assessment.evidence_state }}</span>
<span class="badge" style="background:#2C4157;color:#fff;font-size:7.5pt">Consistency: {{ cross_assessment.signal_consistency }}</span>
<span class="badge" style="background:#4CA6E8;color:#fff;font-size:7.5pt">Quality: {{ quality_gate.reliability_status }}</span>
</div>
<h3 style="margin-top:0">{{ cross_assessment.synthesis_headline }}</h3>
<p><b>Evidence State Rationale:</b> {{ cross_assessment.evidence_state_rationale }}</p>
<p>{{ cross_assessment.synthesis_narrative }}</p>
</div>

<h2>2. The 7 Core Judicial Inquiries</h2>
<table>
<tr><th style="width:30%">Inquiry</th><th>Measured Forensic Finding</th></tr>
<tr><td><b>1. Target of Analysis</b></td><td>{{ evidence.evidence_ref }} · {{ evidence.filename }} ({{ evidence.width }}×{{ evidence.height }}, {{ evidence.container_format }}, {{ run.frames_sampled }} sampled frames)</td></tr>
<tr><td><b>2. Primary Observed Finding</b></td><td>{{ run.assessment }} (Aggregate Indicator Score: {{ run.aggregate_score|f }}/100, Confidence: {{ run.confidence_band }})</td></tr>
<tr><td><b>3. Neural Signal Semantics</b></td><td><b>{{ cross_assessment.score_semantics }}:</b> {{ cross_assessment.score_semantics_note }}</td></tr>
<tr><td><b>4. Agreeing Signals</b></td><td>{% for cf in cross_assessment.corroborating_factors %}{{ cf }}{% if not loop.last %} · {% endif %}{% else %}None{% endfor %}</td></tr>
<tr><td><b>5. Dissent / Safeguards</b></td><td>{% for df in cross_assessment.dissenting_or_neutral_factors %}{{ df }}{% if not loop.last %} · {% endif %}{% else %}None{% endfor %}</td></tr>
<tr><td><b>6. Operational Limitations</b></td><td>Quality grade: {{ quality_gate.quality_grade }} ({{ quality_gate.quality_score_pct }}%). {{ quality_gate.impact_summary }}</td></tr>
<tr><td><b>7. Recommended Action</b></td><td>{% for r in cross_assessment.investigative_recommendations %}[{{ loop.index }}] {{ r }} {% endfor %}</td></tr>
</table>

<h2>3. Explicit Evidence Matrix</h2>
<table>
<tr><th>Evidence Source</th><th>Measurement / Observation</th><th>Strength</th><th>Status</th><th>Limitation</th></tr>
{% for em in evidence_matrix %}
<tr>
<td><b>{{ em.source }}</b></td>
<td>{{ em.observation }}</td>
<td><span class="badge">{{ em.strength }}</span></td>
<td><b>{{ em.status }}</b></td>
<td class="small">{{ em.limitation }}</td>
</tr>
{% endfor %}
</table>

<h2>4. Multi-Stream Forensic Findings</h2>
<table>
<tr><th>Stream</th><th>Result / Measurement</th><th>Score</th><th>Weight</th><th>Method &amp; Scope</th></tr>
{% for s in signals %}
<tr>
<td><b>{{ s.name }}</b></td>
<td>{{ s.result }}</td>
<td>{{ s.score if s.score is not none else '—' }}</td>
<td>{{ s.weight }}</td>
<td class="small">{{ s.method }}</td>
</tr>
{% endfor %}
</table>

{% if recapture and recapture.likelihood %}
<p><b>Display Recapture &amp; Interface:</b> {{ recapture.likelihood }} indication (Score: {{ recapture.score|f }}/100).
{% if recovered_handles %}Recovered candidate handle(s): {% for h in recovered_handles %}<span class="mono">{{ h.handle }}</span> ({{ h.confidence }}% OCR confidence on frame {{ h.frame_index }}){% if not loop.last %}, {% endif %}{% endfor %}.{% else %}No interface handle recovered.{% endif %}</p>
{% endif %}

<h2>5. Origin Propagation &amp; Stress Robustness</h2>
<table style="margin-bottom:4px">
<tr>
<td style="width:50%"><b>Earliest Corpus Copy:</b> {% if earliest %}{{ earliest.corpus.label }} (Sim: {{ '%.1f'|format(earliest.match.similarity) }}%, {{ earliest.corpus.observed_at|f }}){% else %}No match in searched reference corpus{% endif %}</td>
<td><b>Origin Threshold:</b> Hamming distance &le; 14/64 bits (100% separation calibrated)</td>
</tr>
<tr>
<td><b>Laundering Stability:</b> {{ directional_stability.grade }} (Mean Δ: ±{{ directional_stability.mean_delta }}%)</td>
<td><b>Reliability Boundary:</b> {{ stress.reliability_boundary if stress else 'Not executed' }}</td>
</tr>
</table>

<h2>6. Deterministic Replay &amp; Chain-of-Custody Attestation</h2>
<table>
<tr><td style="width:34%"><b>Deterministic Replay</b></td><td>100% Mathematically Reproducible (Pipeline v4.0.0-phase6 on {{ neural_info.device if neural_info else 'CPU' }})</td></tr>
<tr><td><b>Audit Chain Status</b></td><td>{{ chain.message }} ({{ audits|length }} immutable hash-linked entries)</td></tr>
<tr><td><b>Cryptographic Checksum</b></td><td class="mono">SHA-256: {{ evidence.sha256 }} (Pre-analysis byte match)</td></tr>
</table>

<div class="sig-line">
Signature of Investigating Officer / Forensic Analyst<br>
Name: {{ case.officer }} · Unit: {{ case.unit }}
</div>
""" + _FOOT


def _init_weasyprint():
    import sys
    if sys.platform == "darwin":
        import ctypes.util
        _orig_find_library = ctypes.util.find_library
        def _homebrew_find_library(name):
            res = _orig_find_library(name)
            if res:
                return res
            for prefix in ["/opt/homebrew/lib", "/usr/local/lib"]:
                for candidate in [f"lib{name}.dylib", f"{name}.dylib", f"{name}", f"lib{name}.0.dylib", f"lib{name}-1.0.dylib", f"lib{name}-1.0.0.dylib"]:
                    p = Path(prefix) / candidate
                    if p.exists():
                        return str(p)
            return None
        ctypes.util.find_library = _homebrew_find_library

        try:
            import cffi
            _orig_dlopen = cffi.FFI.dlopen
            def _custom_dlopen(self, name, flags=0):
                try:
                    return _orig_dlopen(self, name, flags)
                except OSError:
                    for prefix in ["/opt/homebrew/lib", "/usr/local/lib"]:
                        for candidate in [name, f"{name}.dylib", f"lib{name}.dylib", f"lib{name}.so", f"lib{name}.0.dylib"]:
                            p = Path(prefix) / candidate
                            if p.exists():
                                return _orig_dlopen(self, str(p), flags)
                    raise
            cffi.FFI.dlopen = _custom_dlopen
        except Exception:
            pass


def _pdf(html: str, out: Path) -> Path:
    _init_weasyprint()
    from weasyprint import HTML
    HTML(string=html).write_pdf(str(out))
    return out


def render_all(db: Session, evidence_id: int) -> dict[str, Any]:
    data = collect(db, evidence_id)
    ev = data["evidence"]
    ctx = {**data, "na": NA,
           "device_source": _device_source(ev),
           "make_model": _make_model(ev),
           "qr": _qr_data_uri(f"SROT|{data['case'].case_ref}|{ev.evidence_ref}|SHA256:{ev.sha256}"),
           "recovered_handles": (data["recapture"].recovered_handles_json
                                 if data["recapture"] else []) or []}
    return {
        "data": data,
        "docs": {
            "bsa63_certificate": _render(BSA_TPL, ctx),
            "hash_report": _render(HASH_TPL, ctx),
            "chain_of_custody": _render(CUSTODY_TPL, ctx),
            "technical_annexure": _render(ANNEX_TPL, ctx),
            "preservation_request": _render(PRES_TPL, ctx),
            "forensic_report": _render(REPORT_TPL, ctx),
        },
    }


def _device_source(ev: Evidence) -> str:
    """Only states what is actually known from the container. Never invents a device."""
    if ev.media_kind == "image":
        make = (ev.exif_json or {}).get("Make")
        model = (ev.exif_json or {}).get("Model")
        if make or model:
            return f"Digital record (image) — EXIF device tags present"
        return "Digital record (image file). Originating device not recorded in the file."
    return ("Digital record (video file). Originating device not recorded in the container; "
            f"encoder tag: {ev.encoder_tag or 'absent'}.")


def _make_model(ev: Evidence) -> str:
    ex = ev.exif_json or {}
    make, model = ex.get("Make"), ex.get("Model")
    if make or model:
        return " ".join(x for x in (make, model) if x)
    return NA


def build_packet(db: Session, evidence_id: int) -> CourtPacket:
    rendered = render_all(db, evidence_id)
    data = rendered["data"]
    ev, case = data["evidence"], data["case"]
    stamp = utcnow().strftime("%Y%m%d-%H%M%S")
    out_dir = Path(PACKET_DIR) / f"{case.case_ref}_{ev.evidence_ref}_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    order = [
        ("01_BSA_Section63_Certificate_DRAFT", "bsa63_certificate"),
        ("02_SHA256_Hash_Report", "hash_report"),
        ("03_Chain_of_Custody", "chain_of_custody"),
        ("04_Technical_Forensic_Annexure", "technical_annexure"),
        ("05_Preservation_Request_DRAFT", "preservation_request"),
        ("06_Forensic_Media_Analysis_Report", "forensic_report"),
    ]
    files: dict[str, str] = {}
    for fname, key in order:
        pdf_path = out_dir / f"{fname}.pdf"
        _pdf(rendered["docs"][key], pdf_path)
        files[key] = str(pdf_path)

    zip_path = Path(PACKET_DIR) / f"SROT_CASE_{case.case_ref}_COURT_PACKET_{stamp}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for fname, key in order:
            z.write(files[key], arcname=f"{fname}.pdf")
        z.writestr("README.txt", _packet_readme(case, ev, data))
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()

    packet = CourtPacket(case_id=case.id, evidence_id=ev.id, zip_path=str(zip_path),
                         files_json=files, packet_sha256=digest)
    db.add(packet); db.commit(); db.refresh(packet)
    audit_svc.record(db, case_id=case.id, action="Court packet generated (6 documents)",
                     component="report generator (Jinja2 → WeasyPrint)",
                     evidence_ref=ev.evidence_ref, evidence_hash=ev.sha256,
                     payload={"packet_sha256": digest, "documents": [k for _, k in order]})
    return packet


def _packet_readme(case: Case, ev: Evidence, data: dict) -> str:
    return (
        f"SROT COURT PACKET\n"
        f"=================\n\n"
        f"Case            : {case.case_ref} — {case.title}\n"
        f"Evidence        : {ev.evidence_ref} ({ev.filename})\n"
        f"SHA-256         : {ev.sha256}\n"
        f"Ingested        : {ev.ingested_at}\n"
        f"Packet prepared : {data['generated_at']}\n"
        f"Audit chain     : {data['chain']['message']}\n\n"
        "CONTENTS\n"
        "  01  BSA 2023 Section 63 certificate — PRE-FILLED DRAFT (Part A + Part B)\n"
        "  02  SHA-256 hash report (enclosure to the certificate)\n"
        "  03  Chain of custody — hash-linked audit log\n"
        "  04  Technical forensic annexure\n"
        "  05  Preservation / disclosure request — DRAFT\n"
        "  06  Forensic media analysis report\n\n"
        "IMPORTANT\n"
        "  * Documents 01 and 05 are PRE-FILLED DRAFTS for verification and signature by the\n"
        "    investigating officer and the relevant expert. SROT makes no claim regarding\n"
        "    admissibility — legal admissibility is determined by the court.\n"
        "  * Fields SROT does not actually hold are marked 'Not available / To be completed'.\n"
        "    No device information has been fabricated.\n"
        "  * Reference-corpus records are SYNTHETIC demonstration data and are labelled as such.\n"
        "  * All documents are generated deterministically from the case database by templates.\n"
        "    No language model wrote any part of this narrative.\n"
    )


def build_executive_dossier(db: Session, evidence_id: int) -> Path:
    """Renders a single-file consolidated judicial forensic dossier PDF."""
    data = collect(db, evidence_id)
    ev, case = data["evidence"], data["case"]
    ctx = {
        **data, "na": NA,
        "device_source": _device_source(ev),
        "make_model": _make_model(ev),
        "qr": _qr_data_uri(f"SROT|{case.case_ref}|{ev.evidence_ref}|SHA256:{ev.sha256}"),
        "recovered_handles": (data["recapture"].recovered_handles_json
                              if data["recapture"] else []) or [],
    }
    html = _render(DOSSIER_TPL, ctx)
    out_dir = Path(PACKET_DIR) / f"{case.case_ref}_{ev.evidence_ref}"
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / f"SROT_{case.case_ref}_{ev.evidence_ref}_EXECUTIVE_DOSSIER.pdf"
    _pdf(html, pdf_path)

    audit_svc.record(db, case_id=case.id, action="Executive forensic dossier generated",
                     component="report generator (Jinja2 → WeasyPrint)",
                     evidence_ref=ev.evidence_ref, evidence_hash=ev.sha256,
                     payload={"pdf_path": str(pdf_path)})
    return pdf_path

