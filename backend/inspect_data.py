#!/usr/bin/env python3
"""
Final data inspection: prove that nothing on screen is fabricated.

Walks the database and checks that every derived row is genuinely derived —
the numbers recompute, the files exist, the methods are recorded, and the
synthetic demonstration records are flagged as synthetic everywhere.

    python inspect_data.py

Exit code 0 only if every check passes.
"""
from __future__ import annotations
import re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.db import SessionLocal                                   # noqa: E402
from app.models import (Case, Evidence, AnalysisRun, Signal, FrameAnalysis,  # noqa: E402
                        Fingerprint, CorpusItem, OriginMatch, ExtractedEntity,
                        RecaptureResult, StressTestRun, StressVariant, GraphNode,
                        GraphEdge, TimelineEvent, Lead, CampaignMatch,
                        FingerprintLedger, AuditLog, CourtPacket)
from app.services import integrity, fingerprint as fp_svc, audit as audit_svc  # noqa: E402

PASS: list[str] = []
FAIL: list[str] = []

# strings that would indicate placeholder or invented content leaked into data
PLACEHOLDER = re.compile(
    r"\b(lorem ipsum|TODO|FIXME|XXX+|dummy|placeholder|foo ?bar|sample data|"
    r"john doe|123-45-6789)\b", re.I)

# claims the system must never make
FORBIDDEN_CLAIM = re.compile(
    r"(guaranteed (?:fake|real|authentic)|100% (?:accurate|certain)|"
    r"definitely (?:fake|real)|this is the original file|"
    r"makes the evidence admissible|is legally admissible|"
    r"identified the (?:person|suspect|sender)|subscriber is|account belongs to)", re.I)


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASS if ok else FAIL).append(name)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  — ' + detail if detail else ''}")


def section(t: str) -> None:
    print(f"\n{'=' * 70}\n{t}\n{'=' * 70}")


def main() -> int:  # noqa: C901
    db = SessionLocal()
    try:
        # ── 1. evidence integrity ────────────────────────────────────────────
        section("1 · EVIDENCE INTEGRITY")
        evs = db.query(Evidence).all()
        check("evidence present", bool(evs), f"{len(evs)} items")
        for ev in evs:
            p = Path(ev.stored_path)
            check(f"{ev.evidence_ref}: stored file exists", p.exists(), str(p))
            if p.exists():
                live = integrity.sha256_file(p)
                check(f"{ev.evidence_ref}: stored SHA-256 still matches the file",
                      live == ev.sha256, f"db={ev.sha256[:16]}… disk={live[:16]}…")
                check(f"{ev.evidence_ref}: recorded size matches the file",
                      p.stat().st_size == ev.size_bytes,
                      f"db={ev.size_bytes} disk={p.stat().st_size}")
            check(f"{ev.evidence_ref}: stored inside the evidence directory",
                  "/data/evidence/" in str(p.resolve()) and ".." not in str(p),
                  str(p))

        # ── 2. signals are measurements, not labels ──────────────────────────
        section("2 · SIGNALS CARRY REAL MEASUREMENTS")
        sigs = db.query(Signal).all()
        check("signals recorded", bool(sigs), f"{len(sigs)} rows")
        no_method = [s.name for s in sigs if not s.method]
        check("every signal records its method", not no_method, str(no_method))
        scored_no_measurement = [s.name for s in sigs
                                 if s.score is not None and not s.measurement]
        check("every scored signal carries its raw measurement",
              not scored_no_measurement, str(scored_no_measurement))
        empty_measure = [s.name for s in sigs
                         if s.score is not None and isinstance(s.measurement, dict)
                         and not any(isinstance(v, (int, float)) or isinstance(v, list)
                                     for v in s.measurement.values())]
        check("measurements contain actual numbers", not empty_measure, str(empty_measure))
        out_of_range = [f"{s.name}={s.score}" for s in sigs
                        if s.score is not None and not (0 <= s.score <= 100)]
        check("signal scores lie in 0..100", not out_of_range, str(out_of_range))

        # ── 3. aggregate recomputes from the stored signals ──────────────────
        section("3 · AGGREGATE SCORE RECOMPUTES")
        for run in db.query(AnalysisRun).filter(AnalysisRun.status == "completed").all():
            rows = db.query(Signal).filter(Signal.run_id == run.id).all()
            num = sum(s.score * s.weight for s in rows if s.score is not None and s.weight > 0)
            den = sum(s.weight for s in rows if s.score is not None and s.weight > 0)
            recomputed = round(num / den, 2) if den else None
            check(f"run {run.id}: aggregate = Σ(score×weight)/Σ(weight)",
                  recomputed is not None and abs(recomputed - (run.aggregate_score or -1)) < 0.02,
                  f"stored={run.aggregate_score} recomputed={recomputed}")
            VALID_BACKENDS = {
                "heuristic-forensic-ensemble-v1",
                "heuristic-forensic-ensemble-v1 + neural-vit-v1",
            }
            check(f"run {run.id}: detector backend recorded honestly",
                  run.detector_backend in VALID_BACKENDS,
                  run.detector_backend or "(empty)")

        # ── 4. origin matches recompute from stored hashes ───────────────────
        section("4 · ORIGIN MATCHES RECOMPUTE FROM STORED FINGERPRINTS")
        matches = db.query(OriginMatch).all()
        check("origin matches recorded", bool(matches), f"{len(matches)} rows")
        for m in matches:
            expected = fp_svc.sim_from_hamming(m.hamming)
            check(f"match {m.id}: similarity derives from Hamming distance",
                  abs(expected - m.similarity) < 0.01,
                  f"stored={m.similarity} from_hamming={expected}")
            check(f"match {m.id}: satisfies the calibrated rule "
                  f"(distance and frame corroboration)",
                  fp_svc.qualifies({"hamming": m.hamming,
                                    "matched_frames": m.matched_frames}),
                  f"{m.hamming} bits <= {fp_svc.MATCH_THRESHOLD}, "
                  f"{m.matched_frames} frames >= {fp_svc.MIN_CORROBORATING_FRAMES}")
            check(f"match {m.id}: records how it was normalised",
                  bool(m.normalisation), m.normalisation or "(none)")
        # recompute one match end-to-end from the stored hashes
        if matches:
            m = matches[0]
            q = fp_svc.group_view_rows(
                db.query(Fingerprint).filter(Fingerprint.evidence_id == m.evidence_id).all())
            c = fp_svc.group_view_rows(
                db.query(Fingerprint).filter(Fingerprint.corpus_id == m.corpus_id).all())
            live = fp_svc.best_match_views(q, c)
            check("a match recomputes exactly from the stored hash rows",
                  live["hamming"] == m.hamming,
                  f"stored={m.hamming} recomputed={live['hamming']}")

        # ── 5. corpus files are real and flagged synthetic ───────────────────
        section("5 · REFERENCE CORPUS")
        for c in db.query(CorpusItem).all():
            p = Path(c.stored_path)
            check(f"corpus {c.label}: file exists on disk", p.exists(), str(p))
            if p.exists():
                check(f"corpus {c.label}: SHA-256 matches the file",
                      integrity.sha256_file(p) == c.sha256, "")
            check(f"corpus {c.label}: flagged as synthetic", bool(c.is_synthetic), "")
            check(f"corpus {c.label}: records its transformation", bool(c.transform),
                  c.transform or "(none)")

        # ── 6. entities point at real pixels ─────────────────────────────────
        section("6 · EXTRACTED ENTITIES ARE ANCHORED TO REAL FRAMES")
        ents = db.query(ExtractedEntity).all()
        check("entities recorded", bool(ents), f"{len(ents)} rows")
        for e in ents:
            fa = (db.query(FrameAnalysis)
                  .filter(FrameAnalysis.evidence_id == e.evidence_id,
                          FrameAnalysis.frame_index == e.frame_index).first())
            check(f"entity {e.value!r}: cites a frame that exists",
                  fa is not None and bool(fa.path) and Path(fa.path).exists(),
                  f"frame_index={e.frame_index}")
            box = e.bbox_json
            check(f"entity {e.value!r}: has a real bounding box",
                  isinstance(box, list) and len(box) == 4 and all(isinstance(v, int) for v in box)
                  and box[2] > 0 and box[3] > 0, str(box))
            check(f"entity {e.value!r}: has an OCR confidence",
                  e.ocr_confidence is not None and 0 <= e.ocr_confidence <= 100,
                  str(e.ocr_confidence))
            check(f"entity {e.value!r}: records its method", bool(e.method), e.method or "")

        # ── 7. recapture: no invented handle ─────────────────────────────────
        section("7 · RECAPTURE FINDINGS")
        for rc in db.query(RecaptureResult).all():
            handles = rc.recovered_handles_json or []
            check("recapture result records a note", bool(rc.note), rc.note or "")
            if not handles:
                check("no handle recovered ⇒ the note says so",
                      "no reliable source handle" in (rc.note or "").lower(), rc.note or "")
            for h in handles:
                check(f"handle {h.get('handle')!r}: carries frame, region, box and confidence",
                      all(k in h for k in ("handle", "frame_index", "region", "bbox", "confidence")),
                      str(sorted(h.keys())))
                check(f"handle {h.get('handle')!r}: confidence is a measured value",
                      isinstance(h.get("confidence"), (int, float)) and 0 <= h["confidence"] <= 100,
                      str(h.get("confidence")))

        # ── 8. stress variants are real files ────────────────────────────────
        section("8 · STRESS-TEST VARIANTS ARE REAL FILES")
        variants = db.query(StressVariant).all()
        if not variants:
            print("  (no stress test has been run — nothing to inspect)")
        for v in variants:
            if v.error:
                check(f"variant {v.name}: failure recorded rather than substituted",
                      v.score is None, f"error={v.error[:60]}")
                continue
            p = Path(v.path) if v.path else None
            check(f"variant {v.name}: file exists", bool(p and p.exists()), str(p))
            if p and p.exists():
                check(f"variant {v.name}: SHA-256 matches the generated file",
                      integrity.sha256_file(p) == v.sha256, "")
            check(f"variant {v.name}: records the FFmpeg arguments used",
                  bool(v.ffmpeg_args), v.ffmpeg_args or "")
            if v.phash_similarity is not None and v.reliable is not None:
                consistent = (v.reliable is False) if v.phash_similarity < 78.0 else True
                check(f"variant {v.name}: reliability flag agrees with the fingerprint result",
                      consistent, f"sim={v.phash_similarity} reliable={v.reliable}")
        distinct = {v.sha256 for v in variants if v.sha256}
        if variants:
            check("every variant is a distinct file",
                  len(distinct) == len([v for v in variants if v.sha256]),
                  f"{len(distinct)} distinct hashes")

        # ── 9. graph provenance ──────────────────────────────────────────────
        section("9 · GRAPH NODES RECORD THEIR PROVENANCE")
        nodes = db.query(GraphNode).all()
        edges = db.query(GraphEdge).all()
        check("graph populated", bool(nodes), f"{len(nodes)} nodes, {len(edges)} edges")
        no_method = [n.label for n in nodes if not n.extraction_method]
        check("every node records how it was derived", not no_method, str(no_method))
        no_reason = [e.relation for e in edges if not e.reason]
        check("every edge records why it exists", not no_reason, str(no_reason))
        bad_obs = [e.relation for e in edges
                   if e.observation not in ("DIRECTLY_OBSERVED", "INFERRED")]
        check("every edge is labelled observed or inferred", not bad_obs, str(bad_obs))
        dangling = [e.relation for e in edges
                    if e.src_key not in {n.node_key for n in nodes}
                    or e.dst_key not in {n.node_key for n in nodes}]
        check("no edge points at a missing node", not dangling, str(dangling))

        # ── 10. leads cite their evidence ────────────────────────────────────
        section("10 · LEADS AND TIMELINE")
        leads = db.query(Lead).all()
        check("leads generated", bool(leads), f"{len(leads)} rows")
        check("every lead cites at least one reason",
              all(l.reasons_json for l in leads),
              str([l.title for l in leads if not l.reasons_json]))
        check("every lead states its limitation",
              all(l.limitation for l in leads),
              str([l.title for l in leads if not l.limitation]))
        tl = db.query(TimelineEvent).all()
        check("timeline populated", bool(tl), f"{len(tl)} events")
        check("synthetic timeline entries are flagged",
              all(e.is_synthetic for e in tl if e.kind == "corpus"), "")

        # ── 11. audit chain ──────────────────────────────────────────────────
        section("11 · AUDIT CHAIN")
        for case in db.query(Case).all():
            v = audit_svc.verify_chain(db, case.id)
            check(f"{case.case_ref}: audit chain verifies", v["verified"], v["message"])

        # ── 12. language check across all stored text ────────────────────────
        section("12 · NO PLACEHOLDER OR OVER-CLAIMING TEXT IN STORED DATA")
        blobs: list[tuple[str, str]] = []
        for s in sigs:
            blobs += [(f"signal.{s.key}.note", s.note or ""),
                      (f"signal.{s.key}.result", s.result or "")]
        for l in leads:
            blobs += [(f"lead.{l.rank}.summary", l.summary or ""),
                      (f"lead.{l.rank}.limitation", l.limitation or "")]
        for rc in db.query(RecaptureResult).all():
            blobs.append(("recapture.note", rc.note or ""))
        for cm in db.query(CampaignMatch).all():
            blobs.append(("campaign.hash_type", cm.hash_type or ""))
        for e in tl:
            blobs.append((f"timeline.{e.kind}", f"{e.title} {e.detail}"))
        for a in db.query(AuditLog).all():
            blobs.append((f"audit.{a.id}", a.action or ""))

        placeholders = [(k, PLACEHOLDER.search(t).group(0)) for k, t in blobs
                        if PLACEHOLDER.search(t)]
        check("no placeholder text stored anywhere", not placeholders, str(placeholders[:4]))
        claims = [(k, FORBIDDEN_CLAIM.search(t).group(0)) for k, t in blobs
                  if FORBIDDEN_CLAIM.search(t)]
        check("no forbidden claim stored anywhere", not claims, str(claims[:4]))

        # ── 13. court packets ────────────────────────────────────────────────
        section("13 · COURT PACKETS")
        packets = db.query(CourtPacket).all()
        if not packets:
            print("  (no packet generated — nothing to inspect)")
        for pk in packets:
            files = pk.files_json or {}
            missing = [k for k, v in files.items() if not Path(v).exists()]
            check(f"packet {pk.id}: every document exists on disk", not missing, str(missing))
            check(f"packet {pk.id}: archive exists",
                  bool(pk.zip_path) and Path(pk.zip_path).exists(), str(pk.zip_path))
            check(f"packet {pk.id}: archive has its own SHA-256",
                  bool(pk.packet_sha256), (pk.packet_sha256 or "")[:16])

        # ── 14. ledger hygiene ───────────────────────────────────────────────
        section("14 · FINGERPRINT LEDGER")
        led = db.query(FingerprintLedger).all()
        check("ledger populated", bool(led), f"{len(led)} rows")
        bad_type = {r.hash_type for r in led if not fp_svc.view_of_hash_type(r.hash_type or "")}
        check("every ledger row uses a known hash view", not bad_type, str(bad_type))
        orphan = [r.evidence_ref for r in led
                  if r.evidence_ref and r.evidence_ref.startswith("EV-")
                  and not db.query(Evidence).filter(
                      Evidence.evidence_ref == r.evidence_ref).first()
                  and not db.query(Case).filter(Case.case_ref == r.case_ref).first()]
        check("no ledger row references a deleted case", not orphan, str(set(orphan)))

    finally:
        db.close()

    section("RESULT")
    print(f"  passed: {len(PASS)}   failed: {len(FAIL)}")
    for f in FAIL:
        print(f"    FAILED: {f}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
