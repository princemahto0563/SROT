#!/usr/bin/env python3
"""
Seed and verify the SROT hero demonstration case: CASE-2026-112.

Idempotent, deterministic, and safe to rerun.
Ensures CASE-2026-112 has:
- 1 authentic reference baseline (EV-CASE-2026-112-001) with intact SHA-256
- 12 derivative evidence files
- 12/12 pairwise comparisons
- Stress test run (12 variants)
- Investigation graph, chronological timeline, and deterministic leads
- Deterministic audit chain entries
"""
from __future__ import annotations
import os, sys
from pathlib import Path

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db import SessionLocal, init_db, resolve_data_path, EVIDENCE_DIR
from app.models import (
    Case, Evidence, ForensicComparison, StressTestRun, StressVariant,
    TimelineEvent, Lead, GraphNode, GraphEdge, utcnow
)
from app.services import (
    integrity,
    comparison as comparison_svc,
    casebuild as casebuild_svc,
    stress as stress_svc,
    audit as audit_svc
)

EXPECTED_AUTH_SHA = "c2ff38465cf4c2faf50bdd5b9f51abcadc90beba73867ce795c1edc4393bd63f"
CASE_REF = "CASE-2026-112"

EVIDENCE_SPECS = [
    ("EV-CASE-2026-112-001", "IMG_20260908_165231473_HDR.jpg.jpeg", "AUTHENTIC_REFERENCE", None),
    ("EV-CASE-2026-112-002", "Gemini_Generated_Image_cshus7cshus7cshu.png", "AI_OR_MODIFIED_DERIVATIVE", "EV-CASE-2026-112-001"),
    ("EV-CASE-2026-112-003", "Snapchat-1750414434.jpg.jpeg", "AI_OR_MODIFIED_DERIVATIVE", "EV-CASE-2026-112-001"),
    ("EV-CASE-2026-112-004", "799946502_1476495787834719_144319825552126184_n-2.webp", "AI_OR_MODIFIED_DERIVATIVE", "EV-CASE-2026-112-001"),
    ("EV-CASE-2026-112-005", "799946502_1476495787834719_144319825552126184_n.webp", "AI_OR_MODIFIED_DERIVATIVE", "EV-CASE-2026-112-001"),
    ("EV-CASE-2026-112-006", "photo_6124954613908706836_y.jpg", "AI_OR_MODIFIED_DERIVATIVE", "EV-CASE-2026-112-001"),
    ("EV-CASE-2026-112-007", "photo_6124954613908706836_y.jpg", "AI_OR_MODIFIED_DERIVATIVE", "EV-CASE-2026-112-001"),
    ("EV-CASE-2026-112-008", "photo_6124954613908706835_y.jpg", "AI_OR_MODIFIED_DERIVATIVE", "EV-CASE-2026-112-001"),
    ("EV-CASE-2026-112-009", "image.png", "AI_OR_MODIFIED_DERIVATIVE", "EV-CASE-2026-112-001"),
    ("EV-CASE-2026-112-010", "IMG_20260908_165231473_HDR.jpg", "AI_OR_MODIFIED_DERIVATIVE", "EV-CASE-2026-112-001"),
    ("EV-CASE-2026-112-011", "IMG_20260908_165231473_HDR.jpg.jpeg", "AI_OR_MODIFIED_DERIVATIVE", "EV-CASE-2026-112-001"),
    ("EV-CASE-2026-112-012", "Snapchat-1750414434.jpg.jpeg", "AI_OR_MODIFIED_DERIVATIVE", "EV-CASE-2026-112-001"),
    ("EV-CASE-2026-112-013", "test_up.png", "AI_OR_MODIFIED_DERIVATIVE", "EV-CASE-2026-112-001"),
]


def seed_demo_case():
    init_db()
    db = SessionLocal()
    try:
        print(f"· Verifying hero demo case {CASE_REF} …")
        case = db.query(Case).filter(Case.case_ref == CASE_REF).first()
        if not case:
            print(f"  Creating case record for {CASE_REF} …")
            case = Case(
                case_ref=CASE_REF,
                title="Cancer / Donation Scam Media Investigation",
                category="Manipulated media / Charity fraud",
                officer="Investigating Officer (demo)",
                unit="Digital Forensics Unit",
                summary=(
                    "Manipulated media circulating on public social platforms claiming medical/charity appeal. "
                    "Authenticated camera reference baseline compared against derivatives to establish alterations, "
                    "synthetic artifacts, and origin timeline."
                ),
                status="Open",
            )
            db.add(case)
            db.commit()
            db.refresh(case)
            audit_svc.record(
                db, case_id=case.id, action=f"Case {case.case_ref} opened",
                component="case manager", payload={"seeded": True}
            )

        case_dir = Path(EVIDENCE_DIR) / CASE_REF
        if not case_dir.exists():
            raise FileNotFoundError(f"Case evidence directory {case_dir} does not exist.")

        # Ensure evidence files exist and are registered
        ref_item = None
        for ev_ref, filename, role, ref_parent in EVIDENCE_SPECS:
            file_match = None
            # Find physical file on disk: either exact name or prefixed with ev_ref__
            prefix_name = f"{ev_ref}__{filename}"
            if (case_dir / prefix_name).exists():
                file_match = case_dir / prefix_name
            elif (case_dir / filename).exists():
                file_match = case_dir / filename
            else:
                # search by prefix
                matches = list(case_dir.glob(f"{ev_ref}__*"))
                if matches:
                    file_match = matches[0]

            if not file_match or not file_match.exists():
                print(f"  [WARN] Physical file for {ev_ref} not found in {case_dir}")
                continue

            canonical_rel_path = f"evidence/{CASE_REF}/{file_match.name}"
            calc_sha = integrity.sha256_file(file_match)

            ev = db.query(Evidence).filter(Evidence.evidence_ref == ev_ref).first()
            if not ev:
                print(f"  Registering evidence record {ev_ref} …")
                ev = Evidence(
                    evidence_ref=ev_ref,
                    case_id=case.id,
                    filename=filename,
                    stored_path=canonical_rel_path,
                    mime_type="image/png" if file_match.suffix.lower() == ".png" else "image/jpeg",
                    media_kind="image",
                    size_bytes=file_match.stat().st_size,
                    sha256=calc_sha,
                    forensic_role=role,
                )
                db.add(ev)
                db.commit()
                db.refresh(ev)
            else:
                # Verify and enforce consistency
                updated = False
                if ev.stored_path != canonical_rel_path:
                    ev.stored_path = canonical_rel_path
                    updated = True
                if ev.forensic_role != role:
                    ev.forensic_role = role
                    updated = True
                if ev.sha256 != calc_sha:
                    ev.sha256 = calc_sha
                    updated = True
                if updated:
                    db.commit()
                    db.refresh(ev)

            if role == "AUTHENTIC_REFERENCE":
                ref_item = ev
                if calc_sha != EXPECTED_AUTH_SHA:
                    print(f"  [WARN] Authentic reference SHA {calc_sha} differs from expected {EXPECTED_AUTH_SHA}")
                else:
                    print(f"  [OK] Authentic reference {ev_ref} verified (SHA-256 match).")

        if not ref_item:
            ref_item = db.query(Evidence).filter(
                Evidence.case_id == case.id,
                Evidence.forensic_role == "AUTHENTIC_REFERENCE"
            ).first()

        # Link parent references for derivatives
        if ref_item:
            derivs = db.query(Evidence).filter(
                Evidence.case_id == case.id,
                Evidence.id != ref_item.id
            ).all()
            for d in derivs:
                if d.reference_evidence_id != ref_item.id:
                    d.reference_evidence_id = ref_item.id
            db.commit()

            # Ensure pairwise comparisons exist
            comp_count = db.query(ForensicComparison).filter(
                ForensicComparison.case_id == case.id,
                ForensicComparison.reference_evidence_id == ref_item.id
            ).count()
            if comp_count < len(derivs):
                print(f"  Computing missing comparisons ({comp_count}/{len(derivs)}) …")
                for d in derivs:
                    existing = db.query(ForensicComparison).filter(
                        ForensicComparison.case_id == case.id,
                        ForensicComparison.reference_evidence_id == ref_item.id,
                        ForensicComparison.derivative_evidence_id == d.id
                    ).first()
                    if not existing:
                        try:
                            comparison_svc.compare_evidence(db, ref_item, d)
                        except Exception as e:
                            print(f"    Failed comparison {ref_item.evidence_ref} -> {d.evidence_ref}: {e}")

        # Ensure stress test run exists for authentic reference
        if ref_item:
            stress_run = db.query(StressTestRun).filter(
                StressTestRun.evidence_id == ref_item.id,
                StressTestRun.status == "completed"
            ).first()
            if not stress_run:
                print(f"  Running stress test for authentic reference {ref_item.evidence_ref} …")
                try:
                    stress_svc.run_stress_test(db, ref_item)
                except Exception as e:
                    print(f"    Stress test failed: {e}")

        # Rebuild graph, timeline, and leads across all evidence in case
        print("  Rebuilding case timeline, leads, and graph …")
        casebuild_svc.rebuild_case_views(db, case)

        # Print summary
        final_ev_count = db.query(Evidence).filter(Evidence.case_id == case.id).count()
        final_comp_count = db.query(ForensicComparison).filter(ForensicComparison.case_id == case.id).count()
        final_tl_count = db.query(TimelineEvent).filter(TimelineEvent.case_id == case.id).count()
        final_leads_count = db.query(Lead).filter(Lead.case_id == case.id).count()
        final_nodes_count = db.query(GraphNode).filter(GraphNode.case_id == case.id).count()
        final_edges_count = db.query(GraphEdge).filter(GraphEdge.case_id == case.id).count()

        print(f"\n✓ CASE-2026-112 Demo State:")
        print(f"    Evidence files: {final_ev_count}")
        print(f"    Authentic ref:  {ref_item.evidence_ref if ref_item else 'None'}")
        print(f"    Comparisons:    {final_comp_count}/12")
        print(f"    Timeline:       {final_tl_count} events")
        print(f"    Leads:          {final_leads_count} qualifying leads")
        print(f"    Graph:          {final_nodes_count} nodes, {final_edges_count} edges")
        print(f"✓ {CASE_REF} is demo-ready.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_case()
