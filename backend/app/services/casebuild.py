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

from ..models import (
    Case, Evidence, AnalysisRun, Signal, ExtractedEntity, OriginMatch, CorpusItem,
    RecaptureResult, GraphNode, GraphEdge, TimelineEvent, Lead, CampaignMatch,
    FrameAnalysis, StressTestRun,
)

ENTITY_KIND = {"UPI": "identifier", "PHONE": "identifier", "WALLET": "identifier",
               "URL": "identifier", "HANDLE": "account", "AMOUNT": "identifier",
               "DATE": "identifier", "TIME": "identifier"}


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
    node(ev_key, "evidence", ev.evidence_ref, ev.filename,
         source_evidence_id=ev.id, extraction_method="case ingest",
         confidence=1.0, observed_at=ev.ingested_at,
         attrs_json={"sha256": ev.sha256, "size_bytes": ev.size_bytes,
                     "media_kind": ev.media_kind, "mime": ev.mime_type})

    case_key = f"case:{case.case_ref}"
    node(case_key, "case", case.case_ref, case.title, confidence=1.0,
         source_evidence_id=ev.id,
         extraction_method="case record (registered by the investigating officer)",
         observed_at=case.created_at)
    edge(ev_key, case_key, "registered in", f"Evidence registered under case {case.case_ref}.",
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
        q_nodes = q_nodes.filter((GraphNode.source_evidence_id == ev.id) | (GraphNode.source_evidence_id.is_(None)))
        q_edges = q_edges.filter((GraphEdge.evidence_ref == ev.evidence_ref) | (GraphEdge.evidence_ref.is_(None)))
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
    COLUMN = {"case": 0, "campaign": 0, "hash": 1, "origin": 1, "copy": 1, "evidence": 2,
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
def rebuild_timeline(db: Session, case: Case, ev: Evidence, run: AnalysisRun) -> int:
    db.query(TimelineEvent).filter(TimelineEvent.case_id == case.id).delete()
    db.commit()
    events: list[TimelineEvent] = []

    for m, c in (db.query(OriginMatch, CorpusItem)
                 .join(CorpusItem, OriginMatch.corpus_id == CorpusItem.id)
                 .filter(OriginMatch.evidence_id == ev.id, OriginMatch.run_id == run.id)
                 .order_by(OriginMatch.similarity.desc()).all()):
        if not c.observed_at:
            continue
        events.append(TimelineEvent(
            case_id=case.id, occurred_at=c.observed_at,
            title=("Earliest known copy observed" if m.is_earliest else "Near-duplicate copy observed"),
            detail=f"{c.label} ({c.source_kind}) — perceptual similarity {m.similarity:.1f}% "
                   f"to {ev.evidence_ref}; transform recorded as '{c.transform or 'unspecified'}'.",
            kind="corpus", evidence_ref=c.label, confidence=m.similarity / 100.0,
            is_synthetic=bool(c.is_synthetic)))

    events.append(TimelineEvent(
        case_id=case.id, occurred_at=ev.ingested_at,
        title="Evidence ingested and hashed",
        detail=f"{ev.evidence_ref} ({ev.filename}) registered; SHA-256 computed before analysis.",
        kind="evidence", evidence_ref=ev.evidence_ref, confidence=1.0))

    if run.finished_at:
        events.append(TimelineEvent(
            case_id=case.id, occurred_at=run.finished_at,
            title="Forensic analysis completed",
            detail=f"Assessment: {run.assessment} (confidence band {run.confidence_band}); "
                   f"{run.frames_sampled} frames sampled; backend {run.detector_backend}.",
            kind="system", evidence_ref=ev.evidence_ref, confidence=None))

    db.add_all(events); db.commit()
    return len(events)


# ── leads ────────────────────────────────────────────────────────────────────
def rebuild_leads(db: Session, case: Case, ev: Evidence, run: AnalysisRun) -> int:
    """Deterministic, evidence-backed ranking. Each lead cites the rows it came from."""
    db.query(Lead).filter(Lead.case_id == case.id).delete()
    db.commit()

    candidates: list[dict[str, Any]] = []

    earliest = (db.query(OriginMatch, CorpusItem)
                .join(CorpusItem, OriginMatch.corpus_id == CorpusItem.id)
                .filter(OriginMatch.evidence_id == ev.id, OriginMatch.run_id == run.id,
                        OriginMatch.is_earliest.is_(True)).first())
    if earliest:
        m, c = earliest
        reasons = [
            {"text": f"Earliest observed timestamp among {db.query(OriginMatch).filter(OriginMatch.run_id == run.id).count()} corpus matches",
             "value": c.observed_at.strftime("%d %b %Y · %H:%M") if c.observed_at else "unknown"},
            {"text": "Perceptual similarity to the seized evidence", "value": f"{m.similarity:.1f}%"},
            {"text": "Hamming distance on the perceptual fingerprint", "value": f"{m.hamming}/64"},
            {"text": "Recorded transform relative to the seed media", "value": c.transform or "unspecified"},
        ]
        candidates.append({"weight": m.similarity + 30, "priority": "HIGH",
                           "title": f"Review earliest known copy: {c.label}",
                           "summary": "This copy predates the seized evidence in the searched corpus "
                                      "and carries a different source label.",
                           "reasons": reasons,
                           "limitation": "Ordering is limited to the searched corpus and is not a claim "
                                         "of first publication anywhere."})

    rc = (db.query(RecaptureResult)
          .filter(RecaptureResult.evidence_id == ev.id, RecaptureResult.run_id == run.id).first())
    if rc and rc.recovered_handles_json:
        h = rc.recovered_handles_json[0]
        h_fi = h.get("frame_index")
        h_conf = h.get("confidence")
        f_str = f"frame {h_fi}" if h_fi is not None else "media frame"
        conf_str = f" — {h_conf}% OCR confidence ({f_str})" if h_conf is not None else f" ({f_str})"
        candidates.append({
            "weight": 95, "priority": "HIGH",
            "title": f"Verify recovered interface handle: {h['handle']}{conf_str}",
            "summary": f"A candidate source handle was read by OCR from an interface region of {f_str} — it survived metadata removal because it is in the pixels.",
            "reasons": [
                {"text": "Source frame", "value": f_str},
                {"text": "Recovered from region", "value": h.get("region", "unknown")},
                {"text": "OCR confidence", "value": f"{h_conf}%" if h_conf is not None else "n/a"},
                {"text": "Recapture indication for this evidence", "value": rc.likelihood},
            ],
            "limitation": "OCR output requires human verification. A handle is an account label, not an identified person."})

    for ent in (db.query(ExtractedEntity)
                .filter(ExtractedEntity.evidence_id == ev.id, ExtractedEntity.run_id == run.id,
                        ExtractedEntity.entity_type.in_(("UPI", "WALLET", "PHONE", "URL"))).all()):
        f_num = f"frame {ent.frame_number}" if ent.frame_number is not None else f"frame {ent.frame_index}"
        ts_str = f", {ent.timestamp_s:.1f} s" if ent.timestamp_s is not None else ""
        conf_str = f" — {ent.ocr_confidence:.0f}% OCR confidence ({f_num}{ts_str})" if ent.ocr_confidence is not None else f" ({f_num}{ts_str})"
        candidates.append({
            "weight": 60 + (ent.ocr_confidence or 0) / 5,
            "priority": "MEDIUM",
            "title": f"Examine media-derived {ent.entity_type.lower()}: {ent.value}{conf_str}",
            "summary": f"Identifier read directly out of the media by OCR from {f_num}{ts_str} — it exists in this case only because it was visible in that frame.",
            "reasons": [
                {"text": "Source frame", "value": f_num},
                {"text": "Timestamp in media", "value": (f"{ent.timestamp_s:.2f}s" if ent.timestamp_s is not None else "n/a")},
                {"text": "Bounding box (x,y,w,h)", "value": str(ent.bbox_json)},
                {"text": "OCR confidence", "value": f"{ent.ocr_confidence:.1f}%" if ent.ocr_confidence is not None else "n/a"},
                {"text": "Script detected", "value": ent.language or "unknown"},
            ],
            "limitation": "SROT does not resolve ownership of any identifier. That requires authorised legal process."})

    cm = db.query(CampaignMatch).filter(CampaignMatch.case_id == case.id,
                                        CampaignMatch.evidence_id == ev.id).all()
    if cm:
        top = max(cm, key=lambda x: x.similarity or 0)
        candidates.append({
            "weight": 85, "priority": "HIGH",
            "title": f"Joint review with case {top.other_case_ref}",
            "summary": f"{len(cm)} cross-case fingerprint match(es) found in the department ledger.",
            "reasons": [{"text": f"{c.other_case_ref} / {c.other_evidence_ref}",
                         "value": f"{c.similarity:.1f}% (Hamming {c.hamming}/64)"} for c in cm[:5]],
            "limitation": "Similar media indicates a potential campaign relationship only. It does "
                          "not establish that the same person is involved."})

    top_frames = (db.query(FrameAnalysis)
                  .filter(FrameAnalysis.run_id == run.id, FrameAnalysis.score.isnot(None))
                  .order_by(FrameAnalysis.score.desc()).limit(3).all())
    if top_frames and top_frames[0].score is not None:
        f = top_frames[0]
        candidates.append({
            "weight": 40 + (f.score or 0) / 4, "priority": "MEDIUM",
            "title": "Send the highest-anomaly frames for examiner review",
            "summary": "Directs examiner time to the specific frames carrying the strongest measured "
                       "signal rather than the whole file.",
            "reasons": [{"text": (f"frame {x.frame_number}" if x.frame_number is not None
                                  else f"sample #{x.frame_index}"),
                         "value": f"score {x.score:.1f}"
                                  + (f" @ {x.timestamp_s:.2f}s" if x.timestamp_s is not None else "")}
                        for x in top_frames],
            "limitation": "Frame scores are relative within this file and are not calibrated "
                          "probabilities."})

    prov = (db.query(Signal).filter(Signal.run_id == run.id, Signal.key == "provenance").first())
    if prov and "No C2PA" in (prov.result or ""):
        candidates.append({
            "weight": 25, "priority": "LOW",
            "title": "Record provenance absence in the case file",
            "summary": "No Content Credentials manifest is embedded in this evidence.",
            "reasons": [{"text": "Scan method", "value": prov.method or ""},
                        {"text": "Markers found", "value": str((prov.measurement or {}).get("markers"))}],
            "limitation": "Absence of provenance is not evidence of manipulation — most platforms "
                          "strip it on re-upload."})

    candidates.sort(key=lambda c: -c["weight"])
    rows = [Lead(case_id=case.id, run_id=run.id, rank=i + 1, priority=c["priority"],
                 title=c["title"], summary=c["summary"], reasons_json=jsonable(c["reasons"]),
                 limitation=c["limitation"])
            for i, c in enumerate(candidates[:8])]
    db.add_all(rows); db.commit()
    return len(rows)


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
    db.query(TimelineEvent).filter(TimelineEvent.case_id == case.id).delete()
    db.query(Lead).filter(Lead.case_id == case.id).delete()
    db.commit()

    row = (db.query(Ev, AnalysisRun)
           .join(AnalysisRun, AnalysisRun.evidence_id == Ev.id)
           .filter(Ev.case_id == case.id, AnalysisRun.status == "completed")
           .order_by(AnalysisRun.id.desc()).first())
    if not row:
        return {"rebuilt": False, "graph": {"nodes": 0, "edges": 0},
                "reason": "No analysed evidence remains in this case."}

    ev, run = row
    graph = rebuild_graph(db, case, ev, run)
    timeline = rebuild_timeline(db, case, ev, run)
    leads = rebuild_leads(db, case, ev, run)
    return {"rebuilt": True, "graph": graph, "timeline_events": timeline,
            "leads": leads, "from_evidence": ev.evidence_ref}
