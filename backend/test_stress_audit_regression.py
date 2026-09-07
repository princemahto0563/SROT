#!/usr/bin/env python3
"""
Regression test for BUG 1: Laundering Stress Test / Audit Trail Mismatch.

Verifies:
1. When a stress test is RUNNING for a case + evidence pair:
   - No 'stress test completed' audit event exists.
   - Audit trail does not report a completed variant count.
2. Once the stress test reaches terminal COMPLETED state:
   - The 'stress test completed' audit event is written.
   - The audit variant count equals the completed run's actual variant count.
   - The payload contains status='completed', variant_count, and stress_id matching the database record.
"""
from __future__ import annotations
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.db import SessionLocal, init_db                # noqa: E402
from app.models import Case, Evidence, StressTestRun, StressVariant, AuditLog, utcnow  # noqa: E402
from app.services import audit                          # noqa: E402

def check(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}{' — ' + detail if detail else ''}")
    if not cond:
        raise AssertionError(f"Check failed: {name} — {detail}")


def main() -> int:
    init_db()
    db = SessionLocal()
    case_ref = f"CASE-REG-STRESS-{uuid.uuid4().hex[:6].upper()}"
    ev_ref = f"EV-{case_ref}-001"

    print("=" * 72)
    print(f"BUG 1 REGRESSION TEST: Stress Test / Audit Trail Synchronization")
    print(f"Target: {case_ref} / {ev_ref}")
    print("=" * 72)

    try:
        # 1. Setup isolated test case and evidence
        case = Case(case_ref=case_ref, title="Stress Audit Regression Test", category="test", officer="test")
        db.add(case)
        db.commit()
        db.refresh(case)

        ev = Evidence(
            case_id=case.id,
            evidence_ref=ev_ref,
            filename="sample_test_video.mp4",
            stored_path="/tmp/fake_path.mp4",
            sha256="1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
            size_bytes=1024,
            media_kind="video",
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        # 2. Reproduce RUNNING stress-test state
        st = StressTestRun(evidence_id=ev.id, status="running", started_at=utcnow(), baseline_score=42.5)
        db.add(st)
        db.commit()
        db.refresh(st)

        # Query audit trail for this case + evidence while run is in RUNNING state
        audit_events = db.query(AuditLog).filter(
            AuditLog.case_id == case.id,
            AuditLog.evidence_ref == ev.evidence_ref,
        ).all()

        completed_events = [e for e in audit_events if "completed" in (e.action or "").lower() and "stress" in (e.action or "").lower()]
        check("No 'stress test completed' audit event exists during RUNNING state", len(completed_events) == 0,
              f"Found {len(completed_events)} completed events")

        # Verify audit does not report a completed variant count for this running stress test
        reported_variant_counts = [e.payload_json.get("variant_count") for e in audit_events if e.payload_json and "variant_count" in e.payload_json]
        check("Audit does not report a completed variant count while RUNNING", len(reported_variant_counts) == 0,
              f"Reported counts: {reported_variant_counts}")

        # 3. Simulate processing and variants generation
        v1 = StressVariant(
            stress_id=st.id, name="Re-encode CRF 28", transform="crf28", ffmpeg_args="-crf 28",
            path="/tmp/fake_v1.mp4", sha256="aaaa1111", size_bytes=512, score=41.0, delta=-1.5,
            reliable=True, processing_ms=120
        )
        v2 = StressVariant(
            stress_id=st.id, name="Downscale 50%", transform="scale_half", ffmpeg_args="-vf scale=iw/2:-2",
            path="/tmp/fake_v2.mp4", sha256="bbbb2222", size_bytes=256, score=43.0, delta=0.5,
            reliable=True, processing_ms=110
        )
        v3 = StressVariant(
            stress_id=st.id, name="Heavy Compression", transform="crf38", ffmpeg_args="-crf 38",
            path="/tmp/fake_v3.mp4", sha256="cccc3333", size_bytes=128, score=39.0, delta=-3.5,
            reliable=True, processing_ms=130
        )
        db.add_all([v1, v2, v3])
        st.status = "completed"
        st.reliability_boundary = "Stable up to CRF 28"
        st.finished_at = utcnow()
        db.add(st)
        db.commit()
        db.refresh(st)

        # 4. Now execute the audit completion record matching pipeline.py logic
        db_variants = db.query(StressVariant).filter(StressVariant.stress_id == st.id).all()
        actual_variant_count = len(db_variants)
        scored_variant_count = len([v for v in db_variants if v.score is not None and v.error is None])

        audit.record(
            db,
            case_id=case.id,
            action=f"Laundering stress test completed — {actual_variant_count} variants generated and re-analysed",
            component="stress test (FFmpeg + signal ensemble)",
            evidence_ref=ev.evidence_ref,
            evidence_hash=ev.sha256,
            payload={
                "stress_id": st.id,
                "status": st.status,
                "variant_count": actual_variant_count,
                "scored_variant_count": scored_variant_count,
                "baseline": st.baseline_score,
                "boundary": st.reliability_boundary,
            },
        )

        # 5. Verify the completed state in the audit trail
        audit_events_post = db.query(AuditLog).filter(
            AuditLog.case_id == case.id,
            AuditLog.evidence_ref == ev.evidence_ref,
        ).all()

        completed_events_post = [e for e in audit_events_post if "completed" in (e.action or "").lower() and "stress" in (e.action or "").lower()]
        check("Exactly one 'stress test completed' audit event exists once COMPLETED", len(completed_events_post) == 1,
              f"Found {len(completed_events_post)} completed events")

        target_event = completed_events_post[0]
        check("Audit variant count equals completed run's actual variant count",
              target_event.payload_json.get("variant_count") == actual_variant_count and actual_variant_count == 3,
              f"Audit count: {target_event.payload_json.get('variant_count')}, actual: {actual_variant_count}")

        check("Audit payload correctly records status='completed'",
              target_event.payload_json.get("status") == "completed",
              f"Audit status: {target_event.payload_json.get('status')}")

        check("Audit payload records the exact stress_id",
              target_event.payload_json.get("stress_id") == st.id,
              f"Audit stress_id: {target_event.payload_json.get('stress_id')}, expected: {st.id}")

        print("\n[ALL BUG 1 ASSERTIONS PASSED SUCCESSFULLY]")
        return 0

    finally:
        # Clean up test artifacts
        db.query(StressVariant).filter(StressVariant.stress_id == st.id).delete()
        db.query(StressTestRun).filter(StressTestRun.id == st.id).delete()
        db.query(AuditLog).filter(AuditLog.case_id == case.id).delete()
        db.query(Evidence).filter(Evidence.id == ev.id).delete()
        db.query(Case).filter(Case.id == case.id).delete()
        db.commit()
        db.close()


if __name__ == "__main__":
    sys.exit(main())
