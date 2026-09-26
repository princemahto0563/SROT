#!/usr/bin/env python3
"""
Regression & Concurrency Test for Blocker 2: Cryptographic Audit Ledger Concurrency
Verifies:
1. Multiple concurrent threads writing to audit.record() for the same case simultaneously.
2. All concurrent records are successfully written without SQLite database locked errors.
3. Every record's prev_hash strictly equals the preceding record's current_hash.
4. No two records share the same prev_hash (no chain split or duplicate predecessor).
5. verify_chain() returns verified=True with broken_at_id=None.
"""
from __future__ import annotations
import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db import SessionLocal, init_db
from app.models import Case, AuditLog
from app.services import audit


class TestAuditConcurrencyRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.db = SessionLocal()
        cls.test_case_ref = f"CASE-AUDIT-CONCURRENCY-TEST"
        # Clean existing test case if any
        existing = cls.db.query(Case).filter(Case.case_ref == cls.test_case_ref).first()
        if existing:
            cls.db.query(AuditLog).filter(AuditLog.case_id == existing.id).delete()
            cls.db.query(Case).filter(Case.id == existing.id).delete()
            cls.db.commit()

        cls.case = Case(
            case_ref=cls.test_case_ref,
            title="Concurrency Audit Stress Case",
            category="test",
            officer="DEMO-OFFICER",
        )
        cls.db.add(cls.case)
        cls.db.commit()
        cls.db.refresh(cls.case)
        cls.case_id = cls.case.id

    @classmethod
    def tearDownClass(cls):
        try:
            cls.db.query(AuditLog).filter(AuditLog.case_id == cls.case_id).delete()
            cls.db.query(Case).filter(Case.id == cls.case_id).delete()
            cls.db.commit()
        except Exception:
            pass
        finally:
            cls.db.close()

    def test_concurrent_audit_writes(self):
        """Fires 25 concurrent threads writing audit logs simultaneously and verifies unbroken chain."""
        concurrency_count = 25

        def _worker(thread_idx: int) -> int:
            thread_db = SessionLocal()
            try:
                row = audit.record(
                    thread_db,
                    case_id=self.case_id,
                    action=f"Concurrent audit event from worker {thread_idx}",
                    component="concurrency-test-suite",
                    actor=f"worker-{thread_idx}",
                    payload={"worker_id": thread_idx},
                )
                return row.id
            finally:
                thread_db.close()

        # Execute simultaneously using ThreadPoolExecutor
        row_ids = []
        with ThreadPoolExecutor(max_workers=concurrency_count) as executor:
            futures = [executor.submit(_worker, i) for i in range(concurrency_count)]
            for fut in as_completed(futures):
                row_ids.append(fut.result())

        # 1. Verify all records are present
        self.assertEqual(len(row_ids), concurrency_count, "All concurrent writes must complete")

        # 2. Query all records in order of ID
        db = SessionLocal()
        try:
            records = (
                db.query(AuditLog)
                .filter(AuditLog.case_id == self.case_id)
                .order_by(AuditLog.id.asc())
                .all()
            )
            self.assertEqual(len(records), concurrency_count)

            # 3. Verify no duplicate prev_hash (no split predecessor)
            prev_hashes = [r.prev_hash for r in records]
            self.assertEqual(
                len(prev_hashes),
                len(set(prev_hashes)),
                f"Duplicate prev_hash detected in concurrent writes! Found duplicates: {len(prev_hashes) - len(set(prev_hashes))}"
            )

            # 4. Verify chain links: every record.prev_hash equals the immediately preceding record.current_hash
            prev = audit.GENESIS
            for i, r in enumerate(records):
                self.assertEqual(
                    r.prev_hash,
                    prev,
                    f"Chain link broken at record index {i} (id {r.id}): expected {prev[:12]}..., got {r.prev_hash[:12]}..."
                )
                prev = r.current_hash

            # 5. Verify verify_chain() returns True
            v = audit.verify_chain(db, self.case_id)
            self.assertTrue(v["verified"], f"verify_chain() failed: {v.get('message')}")
            self.assertIsNone(v["broken_at_id"])
            self.assertEqual(v["entries"], concurrency_count)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
