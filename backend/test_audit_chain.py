#!/usr/bin/env python3
"""
Prove the audit chain actually detects tampering.

A chain that always verifies is worthless — this test writes entries, verifies the
chain, then alters a stored row directly in the database and confirms verification
fails and names the entry. Runs in an isolated scratch case that is deleted afterwards.

    python test_audit_chain.py
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.db import SessionLocal, init_db                # noqa: E402
from app.models import Case, AuditLog                   # noqa: E402
from app.services import audit                          # noqa: E402

ok = True


def check(name: str, cond: bool, detail: str = "") -> None:
    global ok
    ok = ok and cond
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}{'  — ' + detail if detail else ''}")


def main() -> int:
    init_db()
    db = SessionLocal()
    case = Case(case_ref="CASE-AUDIT-SELFTEST", title="audit chain self-test",
                category="test", officer="test")
    db.add(case); db.commit(); db.refresh(case)
    try:
        for i in range(5):
            audit.record(db, case_id=case.id, action=f"test entry {i}",
                         component="self-test", payload={"i": i})

        v = audit.verify_chain(db, case.id)
        check("freshly written chain verifies", v["verified"] is True, v["message"])
        check("all entries counted", v["entries"] == 5, str(v["entries"]))

        rows = db.query(AuditLog).filter(AuditLog.case_id == case.id).order_by(AuditLog.id).all()

        # ── tamper 1: alter the recorded content of a middle entry ──────────
        target = rows[2]
        original_action = target.action
        target.action = "test entry 2 (silently edited)"
        db.add(target); db.commit()
        v = audit.verify_chain(db, case.id)
        check("content alteration detected", v["verified"] is False, v["message"])
        check("alteration located at the edited entry", v["broken_at_id"] == target.id,
              f"reported id {v['broken_at_id']}, edited id {target.id}")
        check("alteration classified as content change", v.get("reason") == "content",
              str(v.get("reason")))
        target.action = original_action
        db.add(target); db.commit()
        check("chain verifies again once restored",
              audit.verify_chain(db, case.id)["verified"] is True, "")

        # ── tamper 2: alter a payload value only ────────────────────────────
        target = rows[3]
        target.payload_json = {"i": 999}
        db.add(target); db.commit()
        v = audit.verify_chain(db, case.id)
        check("payload-only alteration detected", v["verified"] is False, v["message"])
        target.payload_json = {"i": 3}
        db.add(target); db.commit()
        check("chain verifies again once payload restored",
              audit.verify_chain(db, case.id)["verified"] is True, "")

        # ── tamper 3: delete an entry from the middle ───────────────────────
        removed = rows[1]
        db.delete(removed); db.commit()
        v = audit.verify_chain(db, case.id)
        check("deletion of an entry detected", v["verified"] is False, v["message"])
        check("deletion classified as a broken link", v.get("reason") == "link",
              str(v.get("reason")))
    finally:
        db.query(AuditLog).filter(AuditLog.case_id == case.id).delete()
        db.query(Case).filter(Case.id == case.id).delete()
        db.commit(); db.close()

    print(f"\n{'ALL AUDIT CHAIN CHECKS PASSED' if ok else 'AUDIT CHAIN CHECKS FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
