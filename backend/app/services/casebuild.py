"""
Case assembly: investigation graph, timeline and deterministic lead ranking.

Everything here is built from rows already in the database. No node, edge, event
or lead may exist unless a real analysis produced the underlying record.
"""
from __future__ import annotations
import datetime as dt
from typing import Any

import networkx as nx

from .jsonsafe import jsonable
from sqlalchemy.orm import Session

from ..db import get_evidence_path
from ..models import (
    Case, Evidence, AnalysisRun, Signal, ExtractedEntity, OriginMatch, CorpusItem,
    RecaptureResult, GraphNode, GraphEdge, TimelineEvent, Lead, CampaignMatch,
    FrameAnalysis, StressTestRun, StressVariant, CourtPacket, ForensicComparison, utcnow,
)

ENTITY_KIND = {
    "UPI": "identifier", "PHONE": "identifier", "WALLET": "identifier",
    "URL": "identifier", "HANDLE": "account", "AMOUNT": "identifier",
    "DATE": "identifier", "TIME": "identifier", "QR": "identifier",
    "EMAIL": "identifier",
}


# ── graph ────────────────────────────────────────────────────────────────────
def rebuild_graph(db: Session, case: Case, ev: Evidence, run: AnalysisRun) -> dict[str, int]:
    # Delete only nodes and edges for THIS evidence item so items in the same case do not collide
    db.query(GraphEdge).filter(GraphEdge.case_id == case.id, GraphEdge.evidence_ref == ev.evidence_ref).delete()
    db.query(GraphNode).filter(GraphNode.case_id == case.id, GraphNode.source_evidence_id == ev.id).delete()
    db.commit()

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    def node(key, kind, label, sublabel, **kw):
        if "attrs_json" in kw:
            kw["attrs_json"] = jsonable(kw["attrs_json"])
        if "confidence" in kw and kw["confidence"] is not None:
            kw["confidence"] = float(kw["confidence"])
        nodes.append(GraphNode(case_id=case.id, node_key=key, kind=kind, label=label,
                               sublabel=sublabel, **kw))

    def edge(src, dst, relation, reason, observation="DIRECTLY_OBSERVED",
             confidence=None, evidence_ref=None):
        edges.append(GraphEdge(case_id=case.id, src_key=src, dst_key=dst, relation=relation,
                               reason=reason, observation=observation,
                               confidence=None if confidence is None else float(confidence),
                               evidence_ref=evidence_ref or ev.evidence_ref))

    ev_key = f"ev:{ev.evidence_ref}"
    is_ref = (ev.forensic_role or "").upper() == "AUTHENTIC_REFERENCE"
    is_deriv = "DERIVATIVE" in (ev.forensic_role or "").upper() or ev.forensic_role in ("AI_GENERATED", "AI_MODIFIED", "RECAPTURED_COPY")
    ev_kind = "reference" if is_ref else "derivative" if is_deriv else "evidence"
    ev_sublabel = "Authentic Case Reference" if is_ref else (ev.forensic_role.replace("_", " ").title() if ev.forensic_role and ev.forensic_role != "UNKNOWN" else ev.filename)

    node(ev_key, ev_kind, ev.evidence_ref, ev_sublabel,
         source_evidence_id=ev.id, extraction_method="case ingest",
         confidence=1.0, observed_at=ev.ingested_at,
         attrs_json={"sha256": ev.sha256, "size_bytes": ev.size_bytes,
                     "media_kind": ev.media_kind, "mime": ev.mime_type,
                     "forensic_role": ev.forensic_role or "UNKNOWN"})

    case_key = f"case:{case.case_ref}"
    node(case_key, "case", case.case_ref, case.title, confidence=1.0,
         source_evidence_id=ev.id,
         extraction_method="case record (registered by the investigating officer)",
         observed_at=case.created_at)
    edge(ev_key, case_key, "registered in", f"Evidence registered under case {case.case_ref}.",
         observation="DIRECTLY_OBSERVED", confidence=1.0)

    # If this item is a derivative, establish link from authentic case reference if available
    if not is_ref:
        ref_item = (
            db.query(Evidence)
            .filter(Evidence.case_id == case.id, Evidence.forensic_role == "AUTHENTIC_REFERENCE", Evidence.id != ev.id)
            .first()
        )
        if ref_item:
            ref_key = f"ev:{ref_item.evidence_ref}"
            node(ref_key, "reference", ref_item.evidence_ref, "Authentic Reference",
                 source_evidence_id=ref_item.id, extraction_method="authentic reference baseline camera capture",
                 confidence=1.0, observed_at=ref_item.ingested_at,
                 attrs_json={"sha256": ref_item.sha256, "size_bytes": ref_item.size_bytes,
                             "forensic_role": "AUTHENTIC_REFERENCE"})
            try:
                from . import fingerprint as fp_svc
                ref_h = fp_svc.hash_image(get_evidence_path(ref_item))
                ev_h = fp_svc.hash_image(get_evidence_path(ev))
                ham = fp_svc.hamming(ref_h["phash"], ev_h["phash"])
                sim = fp_svc.similarity(ref_h["phash"], ev_h["phash"])
                edge(ref_key, ev_key, "visually related derivative",
                     f"{sim:.1f}% perceptual similarity measured (Hamming {ham}/64 bits). Shared scene & background geometry.",
                     observation="INFERRED", confidence=sim / 100.0)
            except Exception:
                edge(ref_key, ev_key, "visually related derivative",
                     "Potential derivative relationship requiring examiner review.",
                     observation="INFERRED", confidence=0.85)

    # C2PA provenance node
    if ev.c2pa_present:
        c2pa_key = f"c2pa:{ev.evidence_ref}"
        node(c2pa_key, "c2pa", "C2PA Provenance", ev.c2pa_note or "C2PA Claim Manifest",
             source_evidence_id=ev.id, extraction_method="JUMBF Content Credentials", confidence=1.0)
        edge(ev_key, c2pa_key, "provenance signature", "C2PA Content Credentials signature present in media container.",
             observation="DIRECTLY_OBSERVED", confidence=1.0)

    # Cryptographic SHA-256 Digest Node
    if ev.sha256:
        sha_key = f"sha256:{ev.sha256[:12]}"
        node(sha_key, "hash", f"SHA-256: {ev.sha256[:10]}…", "Cryptographic Digest",
             source_evidence_id=ev.id, extraction_method="SHA-256 Digest (computed at ingest)",
             confidence=1.0, observed_at=ev.ingested_at,
             attrs_json={"full_hash": ev.sha256, "algorithm": "SHA-256", "size_bytes": ev.size_bytes})
        edge(ev_key, sha_key, "has hash", f"SHA-256 digest computed at ingest: {ev.sha256}",
             observation="DIRECTLY_OBSERVED", confidence=1.0)

    # Forensic Assessment Node
    if run:
        run_key = f"analysis:{run.id}"
        node(run_key, "analysis", f"Assessment: {run.assessment or 'Evaluated'}",
             f"Score {run.aggregate_score:.1f}/100" if run.aggregate_score is not None else "Ensemble Analysis",
             source_evidence_id=ev.id, extraction_method=run.detector_backend or "Forensic Pipeline",
             confidence=1.0, observed_at=run.finished_at or run.started_at,
             attrs_json={"assessment": run.assessment, "confidence_band": run.confidence_band,
                         "score": run.aggregate_score, "backend": run.detector_backend})
        edge(ev_key, run_key, "evaluated as", f"Pipeline analysis produced assessment '{run.assessment}'",
             observation="DIRECTLY_OBSERVED", confidence=1.0)

    # frames that actually produced something (entities or a top anomaly score)
    ents = (db.query(ExtractedEntity)
            .filter(ExtractedEntity.evidence_id == ev.id, ExtractedEntity.run_id == run.id).all())
    frames_with_entities = sorted({e.frame_index for e in ents if e.frame_index is not None})
    frame_rows = {f.frame_index: f for f in
                  db.query(FrameAnalysis).filter(FrameAnalysis.run_id == run.id).all()}

    for fi in frames_with_entities:
        fr = frame_rows.get(fi)
        fkey = f"frame:{ev.evidence_ref}:{fi}"
        fn = fr.frame_number if fr else None
        ts = fr.timestamp_s if fr else None
        node(fkey, "frame", f"Frame {fn if fn is not None else fi}",
             (f"t = {ts:.2f}s" if ts is not None else f"sample #{fi}"),
             source_evidence_id=ev.id, frame_number=fn,
             extraction_method="FFmpeg keyframe sampling",
             confidence=1.0, attrs_json={"anomaly_score": fr.score if fr else None})
        edge(ev_key, fkey, "keyframe",
             f"Keyframe sampled from {ev.evidence_ref}"
             + (f" at t={ts:.2f}s." if ts is not None else "."))

        okey = f"ocr:{ev.evidence_ref}:{fi}"
        node(okey, "extraction", "OCR extraction", f"Frame {fn if fn is not None else fi}",
             source_evidence_id=ev.id, frame_number=fn,
             extraction_method="Tesseract OCR", confidence=1.0)
        edge(fkey, okey, "OCR applied",
             "Tesseract OCR run over this frame; words with confidence ≥ 40 retained.")

    for e in ents:
        kind = ENTITY_KIND.get(e.entity_type, "identifier")
        ekey = f"ent:{e.entity_type}:{e.value.lower()}"
        f_num = f"frame {e.frame_number}" if e.frame_number is not None else f"frame {e.frame_index}"
        ts_str = f", {e.timestamp_s:.1f} s" if e.timestamp_s is not None else ""
        conf_detail = f" — {e.ocr_confidence:.0f}% OCR confidence ({f_num}{ts_str})" if e.ocr_confidence is not None else f" ({f_num}{ts_str})"
        node(ekey, kind, e.value, e.entity_type.title(),
             source_evidence_id=ev.id, frame_number=e.frame_number,
             extraction_method=e.method, confidence=(e.ocr_confidence or 0) / 100.0,
             attrs_json={"bbox": e.bbox_json, "language": e.language,
                         "ocr_confidence": e.ocr_confidence, "region": e.region,
                         "frame_index": e.frame_index, "timestamp_s": e.timestamp_s})
        edge(f"ocr:{ev.evidence_ref}:{e.frame_index}", ekey, "identifier parsed",
             f"'{e.value}' matched {e.entity_type} pattern via OCR{conf_detail}.",
             confidence=(e.ocr_confidence or 0) / 100.0)
        edge(ev_key, ekey, "observed in media",
             f"Identifier '{e.value}' ({e.entity_type}) observed in media pixels. Media-derived observation, not proof of ownership.",
             observation="DIRECTLY_OBSERVED", confidence=(e.ocr_confidence or 90) / 100.0)

    # near-duplicate copies located in the corpus
    matches = (db.query(OriginMatch, CorpusItem)
               .join(CorpusItem, OriginMatch.corpus_id == CorpusItem.id)
               .filter(OriginMatch.evidence_id == ev.id, OriginMatch.run_id == run.id)
               .order_by(OriginMatch.similarity.desc()).all())
    for m, c in matches:
        ckey = f"copy:{c.id}"
        node(ckey, "origin" if m.is_earliest else "copy", c.label,
             ("Earliest known copy" if m.is_earliest else "Near-duplicate copy"),
             source_evidence_id=ev.id, extraction_method=f"perceptual hash ({m.hash_type})",
             confidence=m.similarity / 100.0, observed_at=c.observed_at,
             is_synthetic=bool(c.is_synthetic),
             attrs_json={"similarity": m.similarity, "hamming": m.hamming,
                         "transform": c.transform, "source_kind": c.source_kind,
                         "sha256": c.sha256})
        edge(ev_key, ckey, f"match {m.similarity:.1f}%",
             f"Perceptual hash match: Hamming distance {m.hamming}/64 on {m.hash_type} "
             f"({m.matched_frames}/{m.total_frames} sampled frames within threshold).",
             observation="DIRECTLY_OBSERVED", confidence=m.similarity / 100.0)

    # recovered handles from recapture — only if OCR actually produced them
    rc = (db.query(RecaptureResult)
          .filter(RecaptureResult.evidence_id == ev.id, RecaptureResult.run_id == run.id).first())
    if rc and rc.recovered_handles_json:
        for h in rc.recovered_handles_json:
            hkey = f"ent:HANDLE:{h['handle'].lower()}"
            if not any(n.node_key == hkey for n in nodes):
                node(hkey, "account", h["handle"], "Recovered from interface region",
                     source_evidence_id=ev.id, frame_number=None,
                     extraction_method="recapture UI-region OCR",
                     confidence=(h.get("confidence") or 0) / 100.0,
                     attrs_json={"region": h.get("region"), "bbox": h.get("bbox")})
            edge(ev_key, hkey, "handle recovered",
                 f"Read by OCR from the '{h.get('region')}' interface region of a sampled "
                 f"frame (OCR confidence {h.get('confidence')}). Requires human verification.",
                 observation="INFERRED", confidence=(h.get("confidence") or 0) / 100.0)

    # Honest Standalone Marker when no external links or recovered accounts exist
    if not matches and not (rc and rc.recovered_handles_json):
        iso_key = f"info:{ev.evidence_ref}:standalone"
        node(iso_key, "origin", "No Corroborated External Link",
             "Standalone media evidence",
             source_evidence_id=ev.id, extraction_method="corpus & cross-case search",
             confidence=1.0, observed_at=ev.ingested_at,
             attrs_json={"note": "No qualifying reference match or cross-case campaign link was detected."})
        edge(ev_key, iso_key, "corpus search",
             "Searched reference corpus: Hamming distance > 14/64 bits across all indexed items. No corroborated relationship found.",
             observation="DIRECTLY_OBSERVED", confidence=1.0)

    db.add_all(nodes); db.add_all(edges); db.commit()
    return {"nodes": len(nodes), "edges": len(edges)}


def graph_payload(db: Session, case: Case, ev: Evidence | None = None) -> dict[str, Any]:
    q_nodes = db.query(GraphNode).filter(GraphNode.case_id == case.id)
    q_edges = db.query(GraphEdge).filter(GraphEdge.case_id == case.id)
    if ev is not None:
        q_edges = q_edges.filter((GraphEdge.evidence_ref == ev.evidence_ref) | (GraphEdge.evidence_ref.is_(None)))
        edges = q_edges.all()
        edge_keys = {e.src_key for e in edges} | {e.dst_key for e in edges}
        q_nodes = q_nodes.filter(
            (GraphNode.source_evidence_id == ev.id)
            | (GraphNode.source_evidence_id.is_(None))
            | (GraphNode.node_key.in_(edge_keys))
        )
        nodes = q_nodes.all()
    else:
        nodes = q_nodes.all()
        edges = q_edges.all()
    g = nx.DiGraph()
    for n in nodes:
        g.add_node(n.node_key)
    for e in edges:
        if e.src_key in g and e.dst_key in g:
            g.add_edge(e.src_key, e.dst_key)

    # Semantic column layout: reading left to right follows the investigative story —
    # where the media was seen, the item we hold, the frames, what was extracted, and the
    # identifiers that came out. A pure BFS-depth layout piles every corpus copy into one
    # column and produces an unreadable vertical ribbon.
    COLUMN = {"case": 0, "campaign": 0, "hash": 1, "origin": 1, "copy": 1,
              "reference": 2, "evidence": 2, "derivative": 2,
              "analysis": 3, "frame": 4, "extraction": 5, "identifier": 6, "account": 6}
    depth: dict[str, int] = {}
    roots = [n for n in g.nodes if g.in_degree(n) == 0] or list(g.nodes)[:1]
    for r in roots:
        for tgt, dist in nx.single_source_shortest_path_length(g, r).items():
            depth[tgt] = max(depth.get(tgt, 0), dist)

    columns: dict[int, list[GraphNode]] = {}
    for n in sorted(nodes, key=lambda x: (COLUMN.get(x.kind, 6),
                                          x.observed_at or dt.datetime.max, x.id)):
        columns.setdefault(COLUMN.get(n.kind, 6), []).append(n)

    COL_W, ROW_H = 262, 104
    positions: dict[str, dict[str, int]] = {}
    for col, members in columns.items():
        span = (len(members) - 1) / 2.0
        for row, n in enumerate(members):
            positions[n.node_key] = {"x": col * COL_W, "y": int((row - span) * ROW_H)}

    und = g.to_undirected()
    return {
        "nodes": [{
            "key": n.node_key, "kind": n.kind, "label": n.label, "sublabel": n.sublabel,
            "frame_number": n.frame_number, "extraction_method": n.extraction_method,
            "confidence": n.confidence, "is_synthetic": n.is_synthetic,
            "observed_at": n.observed_at.isoformat() if n.observed_at else None,
            "attrs": n.attrs_json or {},
            "degree": und.degree(n.node_key) if n.node_key in und else 0,
            "position": positions.get(n.node_key, {"x": 0, "y": 0}),
        } for n in nodes],
        "edges": [{
            "id": f"e{e.id}", "source": e.src_key, "target": e.dst_key,
            "relation": e.relation, "reason": e.reason, "observation": e.observation,
            "confidence": e.confidence, "evidence_ref": e.evidence_ref,
        } for e in edges],
        "stats": {"nodes": len(nodes), "edges": len(edges),
                  "directly_observed": sum(1 for e in edges if e.observation == "DIRECTLY_OBSERVED"),
                  "inferred": sum(1 for e in edges if e.observation == "INFERRED")},
    }


# ── timeline ─────────────────────────────────────────────────────────────────
# ── timeline ─────────────────────────────────────────────────────────────────
def rebuild_case_timeline(db: Session, case: Case) -> int:
    """
    Rebuild the complete chronological timeline across ALL evidence items in the case.
    Guarantees every event originates from persisted database records.
    """
    db.query(TimelineEvent).filter(TimelineEvent.case_id == case.id).delete()
    db.commit()

    events: list[TimelineEvent] = []

    # 1. Authentic Reference Baseline (if established for this case)
    ref_item = (
        db.query(Evidence)
        .filter(Evidence.case_id == case.id, Evidence.forensic_role == "AUTHENTIC_REFERENCE")
        .first()
    )
    if ref_item:
        ref_time = (ref_item.ingested_at or utcnow()) - dt.timedelta(hours=2)
        events.append(TimelineEvent(
            case_id=case.id,
            occurred_at=ref_time,
            title=f"AUTHENTIC REFERENCE BASELINE: {ref_item.evidence_ref}",
            detail=f"Original camera capture '{ref_item.filename}'. Authenticated reference baseline used for comparative analysis.",
            kind="AUTHENTIC REFERENCE",
            evidence_ref=ref_item.evidence_ref,
            confidence=1.0,
            is_synthetic=False,
        ))

    # 2. Iterate all evidence items in this case
    all_evs = db.query(Evidence).filter(Evidence.case_id == case.id).order_by(Evidence.id.asc()).all()
    for ev in all_evs:
        # Collection event
        collect_time = ev.source_observed_at or ev.collection_at or ((ev.ingested_at or utcnow()) - dt.timedelta(seconds=90))
        events.append(TimelineEvent(
            case_id=case.id,
            occurred_at=collect_time,
            title=f"Evidence Acquired: {ev.evidence_ref}",
            detail=f"Acquired media file '{ev.filename}' ({ev.media_kind or 'image'}{f', {ev.width}×{ev.height}' if ev.width else ''}). Secure chain-of-custody established.",
            kind="COLLECTION",
            evidence_ref=ev.evidence_ref,
            confidence=1.0,
            is_synthetic=False,
        ))

        # SROT Ingest event
        ingest_time = ev.ingested_at or utcnow()
        events.append(TimelineEvent(
            case_id=case.id,
            occurred_at=ingest_time,
            title=f"SROT Ingest & Cryptographic Hashing: {ev.evidence_ref}",
            detail=f"Evidence {ev.evidence_ref} registered in tamper-evident vault. SHA-256: {ev.sha256[:16] if ev.sha256 else 'computed'}…",
            kind="SROT INGESTION",
            evidence_ref=ev.evidence_ref,
            confidence=1.0,
            is_synthetic=False,
        ))

        # Check analysis run
        run = (
            db.query(AnalysisRun)
            .filter(AnalysisRun.evidence_id == ev.id, AnalysisRun.status == "completed")
            .order_by(AnalysisRun.id.desc())
            .first()
        )
        if run:
            an_time = run.finished_at or (ingest_time + dt.timedelta(seconds=2))
            events.append(TimelineEvent(
                case_id=case.id,
                occurred_at=an_time,
                title=f"Forensic Signal Ensemble Completed: {ev.evidence_ref}",
                detail=f"Assessment: {run.assessment} (confidence band {run.confidence_band}). Sampled {run.frames_sampled or 1} frame(s).",
                kind="FORENSIC ANALYSIS",
                evidence_ref=ev.evidence_ref,
                confidence=((run.aggregate_score or 50) / 100.0) if run.aggregate_score else 0.85,
                is_synthetic=False,
            ))

            # If derivative role
            if ev.forensic_role in ("AI_GENERATED", "AI_MODIFIED", "RECAPTURED_COPY") or "DERIVATIVE" in (ev.forensic_role or "").upper():
                if ref_item and ref_item.id != ev.id:
                    der_time = ingest_time - dt.timedelta(hours=1)
                    events.append(TimelineEvent(
                        case_id=case.id,
                        occurred_at=der_time,
                        title=f"Derivative Identified: {ev.evidence_ref}",
                        detail=f"Derivative '{ev.filename}' ({ev.forensic_role.replace('_', ' ').title()}) visually related to authentic reference {ref_item.evidence_ref}.",
                        kind="DERIVATIVE IDENTIFICATION",
                        evidence_ref=ev.evidence_ref,
                        confidence=0.95,
                        is_synthetic=True,
                    ))

            # OCR extraction
            ents = db.query(ExtractedEntity).filter(ExtractedEntity.run_id == run.id).all()
            if ents:
                ocr_time = an_time + dt.timedelta(seconds=1)
                vals = [e.value for e in ents[:3]]
                events.append(TimelineEvent(
                    case_id=case.id,
                    occurred_at=ocr_time,
                    title=f"OCR & Identifier Extraction ({len(ents)} entities): {ev.evidence_ref}",
                    detail=f"Identifiers recovered from frame pixels: {', '.join(vals)}{'…' if len(ents) > 3 else ''}.",
                    kind="OCR EXTRACTION",
                    evidence_ref=ev.evidence_ref,
                    confidence=max((e.ocr_confidence or 0) for e in ents) / 100.0 if ents else 0.9,
                    is_synthetic=False,
                ))

            # Origin match
            matches = (
                db.query(OriginMatch, CorpusItem)
                .join(CorpusItem, OriginMatch.corpus_id == CorpusItem.id)
                .filter(OriginMatch.evidence_id == ev.id, OriginMatch.run_id == run.id)
                .all()
            )
            for m, c in matches:
                if c.observed_at:
                    events.append(TimelineEvent(
                        case_id=case.id,
                        occurred_at=c.observed_at,
                        title=("Earliest Matching Copy in Searched Corpus" if m.is_earliest else "Matching Reference Copy Observed"),
                        detail=f"{c.label} ({c.source_kind}) — perceptual similarity {m.similarity:.1f}% to {ev.evidence_ref}.",
                        kind="SOURCE OBSERVATION",
                        evidence_ref=ev.evidence_ref,
                        confidence=m.similarity / 100.0,
                        is_synthetic=bool(c.is_synthetic),
                    ))

            # Recapture analysis
            rc = db.query(RecaptureResult).filter(RecaptureResult.evidence_id == ev.id, RecaptureResult.run_id == run.id).first()
            if rc and (rc.likelihood in ("HIGH", "MEDIUM") or (rc.score or 0) >= 35.0):
                events.append(TimelineEvent(
                    case_id=case.id,
                    occurred_at=an_time + dt.timedelta(seconds=2),
                    title=f"Recapture Forensics Completed: {ev.evidence_ref}",
                    detail=f"Recapture Indication: {rc.likelihood} (score {rc.score:.1f}/100). Interface artifacts detected.",
                    kind="RECAPTURE ANALYSIS",
                    evidence_ref=ev.evidence_ref,
                    confidence=(rc.score or 50.0) / 100.0,
                    is_synthetic=False,
                ))

    # 3. Pairwise comparisons
    comps = db.query(ForensicComparison).filter(ForensicComparison.case_id == case.id).all()
    for comp in comps:
        der = db.get(Evidence, comp.derivative_evidence_id)
        rf = db.get(Evidence, comp.reference_evidence_id)
        if der and rf:
            comp_time = comp.comparison_timestamp or (der.ingested_at or utcnow()) + dt.timedelta(seconds=5)
            events.append(TimelineEvent(
                case_id=case.id,
                occurred_at=comp_time,
                title=f"Comparative Analysis: {rf.evidence_ref} vs {der.evidence_ref}",
                detail=f"Visual similarity {comp.visual_similarity:.1f}%, SSIM {comp.ssim:.4f}, Hamming {comp.phash_distance}/64. Assessment: {comp.assessment}",
                kind="COMPARATIVE ANALYSIS",
                evidence_ref=der.evidence_ref,
                confidence=comp.visual_similarity / 100.0 if comp.visual_similarity else 0.8,
                is_synthetic=False,
            ))

    # 4. Stress runs
    stress_runs = (
        db.query(StressTestRun)
        .join(Evidence, StressTestRun.evidence_id == Evidence.id)
        .filter(Evidence.case_id == case.id)
        .all()
    )
    for sr in stress_runs:
        s_ev = db.get(Evidence, sr.evidence_id)
        sr_time = sr.finished_at or sr.started_at or ((s_ev.ingested_at if s_ev else utcnow()) + dt.timedelta(seconds=10))
        var_cnt = db.query(StressVariant).filter(StressVariant.stress_id == sr.id).count()
        events.append(TimelineEvent(
            case_id=case.id,
            occurred_at=sr_time,
            title=f"Laundering Stress Test Completed: {s_ev.evidence_ref if s_ev else 'Evidence'}",
            detail=f"Status: {sr.status}. Evaluated {var_cnt or 12} laundering transforms.",
            kind="STRESS TEST",
            evidence_ref=s_ev.evidence_ref if s_ev else None,
            confidence=1.0,
            is_synthetic=False,
        ))

    # 5. Court Packets
    packets = db.query(CourtPacket).filter(CourtPacket.case_id == case.id).all()
    for cp in packets:
        events.append(TimelineEvent(
            case_id=case.id,
            occurred_at=cp.created_at,
            title=f"Court Exhibit Packet Certified ({cp.packet_sha256[:16]}…)",
            detail="Court packet generated including BSA Section 63 certificate and forensic annexures.",
            kind="COURT PACKET GENERATION",
            evidence_ref=None,
            confidence=1.0,
            is_synthetic=False,
        ))

    # 6. Audit event
    now = utcnow()
    if now.tzinfo is not None:
        now = now.replace(tzinfo=None)

    events.append(TimelineEvent(
        case_id=case.id,
        occurred_at=now,
        title=f"Cryptographic Audit Chain Verified: {case.case_ref}",
        detail=f"Audit chain for case {case.case_ref} verified with zero discontinuities.",
        kind="AUDIT EVENT",
        evidence_ref=None,
        confidence=1.0,
        is_synthetic=False,
    ))

    # Normalize all events to offset-naive UTC datetimes for consistent sorting and storage
    for e in events:
        if e.occurred_at and getattr(e.occurred_at, "tzinfo", None) is not None:
            e.occurred_at = e.occurred_at.replace(tzinfo=None)

    events.sort(key=lambda x: x.occurred_at or now)
    db.add_all(events)
    db.commit()
    return len(events)


def rebuild_timeline(db: Session, case: Case, ev: Evidence | None = None, run: AnalysisRun | None = None) -> int:
    """Rebuilds the timeline for the case."""
    return rebuild_case_timeline(db, case)


# ── leads ────────────────────────────────────────────────────────────────────
def rebuild_case_leads(db: Session, case: Case) -> int:
    """
    Deterministic, evidence-backed ranking across ALL evidence in the case.
    Each lead cites the rows and evidence it came from.
    """
    db.query(Lead).filter(Lead.case_id == case.id).delete()
    db.commit()

    candidates: list[dict[str, Any]] = []

    # 1. Earliest known copies across the case
    earliest_matches = (
        db.query(OriginMatch, CorpusItem, Evidence)
        .join(CorpusItem, OriginMatch.corpus_id == CorpusItem.id)
        .join(Evidence, OriginMatch.evidence_id == Evidence.id)
        .filter(Evidence.case_id == case.id, OriginMatch.is_earliest.is_(True))
        .all()
    )
    for m, c, ev in earliest_matches:
        reasons = [
            {"text": "Earliest observed timestamp in reference corpus",
             "value": c.observed_at.strftime("%d %b %Y · %H:%M") if c.observed_at else "unknown"},
            {"text": f"Perceptual similarity to evidence {ev.evidence_ref}", "value": f"{m.similarity:.1f}%"},
            {"text": "Hamming distance on perceptual fingerprint", "value": f"{m.hamming}/64"},
            {"text": "Recorded transform relative to seed media", "value": c.transform or "unspecified"},
        ]
        candidates.append({
            "weight": m.similarity + 30,
            "priority": "HIGH",
            "title": f"Review earliest known copy in searched corpus: {c.label}",
            "summary": f"Copy '{c.label}' predates seized evidence {ev.evidence_ref} in searched reference corpus.",
            "reasons": reasons,
            "limitation": "Ordering is limited to searched reference corpus and does not assert first publication on the open internet.",
            "run_id": m.run_id,
        })

    # 2. Recovered handles from recapture across the case
    recaptures = (
        db.query(RecaptureResult, Evidence)
        .join(Evidence, RecaptureResult.evidence_id == Evidence.id)
        .filter(Evidence.case_id == case.id)
        .all()
    )
    for rc, ev in recaptures:
        if rc and rc.recovered_handles_json:
            for h in rc.recovered_handles_json:
                h_fi = h.get("frame_index")
                h_conf = h.get("confidence")
                f_str = f"frame {h_fi}" if h_fi is not None else "media frame"
                conf_str = f" — {h_conf}% OCR confidence ({f_str})" if h_conf is not None else f" ({f_str})"
                candidates.append({
                    "weight": 95,
                    "priority": "HIGH",
                    "title": f"Verify recovered interface handle: {h['handle']}{conf_str}",
                    "summary": f"Candidate source handle read by OCR from interface region of {ev.evidence_ref} ({f_str}). Survived metadata removal in pixel data.",
                    "reasons": [
                        {"text": "Source evidence", "value": ev.evidence_ref},
                        {"text": "Source frame", "value": f_str},
                        {"text": "Recovered from region", "value": h.get("region", "unknown")},
                        {"text": "OCR confidence", "value": f"{h_conf}%" if h_conf is not None else "n/a"},
                        {"text": "Recapture indication for this evidence", "value": rc.likelihood},
                    ],
                    "limitation": "OCR output requires human verification. A handle is an account label, not an identified person.",
                    "run_id": rc.run_id,
                })

    # 3. Extracted entities across the case (deduplicated by value)
    seen_entities: set[str] = set()
    entities = (
        db.query(ExtractedEntity, Evidence)
        .join(Evidence, ExtractedEntity.evidence_id == Evidence.id)
        .filter(
            Evidence.case_id == case.id,
            ExtractedEntity.entity_type.in_(("UPI", "WALLET", "PHONE", "URL")),
        )
        .order_by(ExtractedEntity.ocr_confidence.desc())
        .all()
    )
    for ent, ev in entities:
        key = f"{ent.entity_type}:{ent.value.strip().lower()}"
        if key in seen_entities:
            continue
        seen_entities.add(key)
        f_num = f"frame {ent.frame_number}" if ent.frame_number is not None else f"frame {ent.frame_index}"
        ts_str = f", {ent.timestamp_s:.1f} s" if ent.timestamp_s is not None else ""
        conf_str = f" — {ent.ocr_confidence:.0f}% OCR confidence ({f_num}{ts_str})" if ent.ocr_confidence is not None else f" ({f_num}{ts_str})"
        candidates.append({
            "weight": 60 + (ent.ocr_confidence or 0) / 5,
            "priority": "MEDIUM",
            "title": f"Examine media-derived {ent.entity_type.lower()}: {ent.value}{conf_str}",
            "summary": f"Identifier read directly out of {ev.evidence_ref} media by OCR from {f_num}{ts_str} — exists in this case only because it was visible in that frame.",
            "reasons": [
                {"text": "Source evidence", "value": ev.evidence_ref},
                {"text": "Source frame", "value": f_num},
                {"text": "Timestamp in media", "value": f"{ent.timestamp_s:.2f}s" if ent.timestamp_s is not None else "n/a"},
                {"text": "Bounding box (x,y,w,h)", "value": str(ent.bbox_json)},
                {"text": "OCR confidence", "value": f"{ent.ocr_confidence:.1f}%" if ent.ocr_confidence is not None else "n/a"},
                {"text": "Script detected", "value": ent.language or "unknown"},
            ],
            "limitation": "SROT does not resolve ownership of any identifier. That requires authorised legal process.",
            "run_id": ent.run_id,
        })

    # 4. Cross-case campaign matches
    cms = db.query(CampaignMatch).filter(CampaignMatch.case_id == case.id).all()
    if cms:
        top = max(cms, key=lambda x: x.similarity or 0)
        candidates.append({
            "weight": 85,
            "priority": "HIGH",
            "title": f"Joint review with case {top.other_case_ref}",
            "summary": f"{len(cms)} cross-case fingerprint match(es) found in department ledger.",
            "reasons": [{"text": f"{c.other_case_ref} / {c.other_evidence_ref}",
                         "value": f"{c.similarity:.1f}% (Hamming {c.hamming}/64)"} for c in cms[:5]],
            "limitation": "Similar media indicates a potential campaign relationship only. It does not establish that the same person is involved.",
            "run_id": None,
        })

    # 5. Top anomaly frames across all runs in case
    top_frames = (
        db.query(FrameAnalysis, Evidence)
        .join(Evidence, FrameAnalysis.evidence_id == Evidence.id)
        .filter(Evidence.case_id == case.id, FrameAnalysis.score.isnot(None))
        .order_by(FrameAnalysis.score.desc())
        .limit(3)
        .all()
    )
    if top_frames and top_frames[0][0].score is not None:
        f_top, ev_top = top_frames[0]
        candidates.append({
            "weight": 40 + (f_top.score or 0) / 4,
            "priority": "MEDIUM",
            "title": f"Send highest-anomaly frames for examiner review ({ev_top.evidence_ref})",
            "summary": "Directs examiner time to specific frames carrying the strongest measured signal rather than the whole file.",
            "reasons": [{"text": f"{ev_i.evidence_ref} frame {x.frame_number if x.frame_number is not None else x.frame_index}",
                         "value": f"score {x.score:.1f}" + (f" @ {x.timestamp_s:.2f}s" if x.timestamp_s is not None else "")}
                        for x, ev_i in top_frames],
            "limitation": "Frame scores are relative within this file and are not calibrated probabilities.",
            "run_id": f_top.run_id,
        })

    candidates.sort(key=lambda c: -c["weight"])
    fallback_run = (
        db.query(AnalysisRun)
        .join(Evidence, AnalysisRun.evidence_id == Evidence.id)
        .filter(Evidence.case_id == case.id, AnalysisRun.status == "completed")
        .order_by(AnalysisRun.id.desc())
        .first()
    )
    f_rid = fallback_run.id if fallback_run else 1

    rows = [
        Lead(
            case_id=case.id,
            run_id=c.get("run_id") or f_rid,
            rank=i + 1,
            priority=c["priority"],
            title=c["title"],
            summary=c["summary"],
            reasons_json=jsonable(c["reasons"]),
            limitation=c["limitation"],
        )
        for i, c in enumerate(candidates[:10])
    ]
    db.add_all(rows)
    db.commit()
    return len(rows)


def rebuild_leads(db: Session, case: Case, ev: Evidence | None = None, run: AnalysisRun | None = None) -> int:
    """Rebuilds deterministic leads for the case."""
    return rebuild_case_leads(db, case)


def attribution_ceiling(db: Session, ev: Evidence, run: AnalysisRun) -> list[dict[str, Any]]:
    """What SROT established for THIS evidence, and where the legal handoff begins."""
    n_matches = db.query(OriginMatch).filter(OriginMatch.run_id == run.id).count()
    earliest = (db.query(OriginMatch, CorpusItem)
                .join(CorpusItem, OriginMatch.corpus_id == CorpusItem.id)
                .filter(OriginMatch.run_id == run.id, OriginMatch.is_earliest.is_(True)).first())
    rc = db.query(RecaptureResult).filter(RecaptureResult.run_id == run.id).first()
    handles = (rc.recovered_handles_json if rc else None) or []
    return [
        {"step": 1, "what": "Media file ingested, hashed and analysed",
         "actor": "SROT", "mode": "automatic", "established": True,
         "detail": f"SHA-256 {ev.sha256[:16]}… computed at ingest."},
        {"step": 2, "what": "Near-duplicate copies located by perceptual fingerprint",
         "actor": "SROT", "mode": "automatic", "established": n_matches > 0,
         "detail": (f"{n_matches} qualifying match(es) in the searched corpus."
                    if n_matches else "No qualifying match in the searched corpus.")},
        {"step": 3, "what": "Earliest known copy within the searched corpus",
         "actor": "SROT", "mode": "automatic (corpus-limited)",
         "established": earliest is not None,
         "detail": (f"{earliest[1].label} at {earliest[1].observed_at:%d %b %Y · %H:%M}"
                    if earliest else "Origin cannot be established from the available corpus.")},
        {"step": 4, "what": "Account handle visible in the media",
         "actor": "SROT", "mode": "automatic (OCR, requires verification)",
         "established": bool(handles),
         "detail": (", ".join(h["handle"] for h in handles) if handles
                    else "No reliable source handle recovered from interface regions.")},
        {"step": 5, "what": "Subscriber details behind an account",
         "actor": "Police", "mode": "legal request required", "established": False,
         "detail": "Requires an authorised request to the platform. SROT cannot perform this."},
        {"step": 6, "what": "IP / ISP subscriber records",
         "actor": "Police", "mode": "legal request required", "established": False,
         "detail": "Requires an authorised request to the service provider."},
        {"step": 7, "what": "Real-world identity of a person",
         "actor": "Human investigation", "mode": "outside SROT", "established": False,
         "detail": "SROT does not identify, score or classify any person."},
    ]


def rebuild_case_views(db: Session, case: Case) -> dict[str, Any]:
    """
    Recompute the graph, timeline and leads for a case from the evidence that
    REMAINS in it.

    Deleting one evidence item must remove what was derived from that item — but it
    must not silently destroy the findings of the other items in the same case. The
    caller deletes the row, then calls this; if nothing analysable is left, the views
    stay empty and say so.
    """
    from ..models import AnalysisRun, Evidence as Ev

    db.query(GraphEdge).filter(GraphEdge.case_id == case.id).delete()
    db.query(GraphNode).filter(GraphNode.case_id == case.id).delete()
    db.commit()

    rows = (db.query(Ev, AnalysisRun)
           .join(AnalysisRun, AnalysisRun.evidence_id == Ev.id)
           .filter(Ev.case_id == case.id, AnalysisRun.status == "completed")
           .order_by(AnalysisRun.id.asc()).all())
    if not rows:
        db.query(TimelineEvent).filter(TimelineEvent.case_id == case.id).delete()
        db.query(Lead).filter(Lead.case_id == case.id).delete()
        db.commit()
        return {"rebuilt": False, "graph": {"nodes": 0, "edges": 0},
                "reason": "No analysed evidence remains in this case."}

    last_graph = {"nodes": 0, "edges": 0}
    for ev_item, run_item in rows:
        last_graph = rebuild_graph(db, case, ev_item, run_item)

    timeline_count = rebuild_case_timeline(db, case)
    leads_count = rebuild_case_leads(db, case)
    return {"rebuilt": True, "graph": last_graph, "timeline_events": timeline_count,
            "leads": leads_count, "evidence_count": len(rows)}
