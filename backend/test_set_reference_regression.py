#!/usr/bin/env python3
"""
Regression test for Blocker 1: POST /api/cases/{case_ref}/set-reference
Verifies:
1. POST /set-reference returns HTTP 200 (no 500 TypeError).
2. Reference evidence forensic_role is updated to AUTHENTIC_REFERENCE.
3. Graph is correctly rebuilt and verified valid via /graph API.
4. Timeline is correctly rebuilt and verified valid via /timeline API.
"""
import os
import sys
import unittest
from pathlib import Path
import requests

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db import SessionLocal
from app.models import Case, Evidence, GraphNode, GraphEdge, TimelineEvent

BASE_URL = "http://127.0.0.1:8077/api"
DEMO_BADGE = os.environ.get("DEMO_OFFICER_BADGE", "DEMO-OFFICER")
DEMO_PWD = os.environ.get("DEMO_OFFICER_PASSWORD", "SROT@Police2026#Demo")


class TestSetReferenceRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 1. Login to obtain bearer token
        login_res = requests.post(
            f"{BASE_URL}/auth/login",
            json={"badge_id": DEMO_BADGE, "password": DEMO_PWD},
            timeout=10,
        )
        if login_res.status_code != 200:
            raise RuntimeError(f"Login failed: {login_res.status_code} {login_res.text}")
        cls.token = login_res.json()["token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}
        cls.case_ref = "CASE-2026-112"
        cls.ref_evidence_ref = "EV-CASE-2026-112-001"

    def test_01_set_reference_endpoint_200(self):
        """POST /api/cases/{case_ref}/set-reference returns HTTP 200 and updates role."""
        url = f"{BASE_URL}/cases/{self.case_ref}/set-reference"
        res = requests.post(url, json={"evidence_ref": self.ref_evidence_ref}, headers=self.headers, timeout=15)
        self.assertEqual(res.status_code, 200, f"Expected 200 OK, got {res.status_code}: {res.text}")
        data = res.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("reference_ref"), self.ref_evidence_ref)

        # Verify in DB
        db = SessionLocal()
        try:
            case = db.query(Case).filter(Case.case_ref == self.case_ref).first()
            self.assertIsNotNone(case)
            ev = db.query(Evidence).filter(Evidence.case_id == case.id, Evidence.evidence_ref == self.ref_evidence_ref).first()
            self.assertIsNotNone(ev)
            self.assertEqual(ev.forensic_role, "AUTHENTIC_REFERENCE")
            self.assertIsNone(ev.reference_evidence_id)
        finally:
            db.close()

    def test_02_graph_remains_valid_after_set_reference(self):
        """Graph endpoint reflects rebuilt graph with reference and derivative nodes."""
        url = f"{BASE_URL}/evidence/{self.ref_evidence_ref}/graph"
        res = requests.get(url, headers=self.headers, timeout=10)
        self.assertEqual(res.status_code, 200, f"Expected 200 for graph, got {res.status_code}: {res.text}")
        graph_data = res.json()
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        self.assertGreater(len(nodes), 0, "Graph must contain nodes")
        self.assertGreater(len(edges), 0, "Graph must contain edges")

        # Verify reference node exists
        ref_node = next((n for n in nodes if n.get("key") == f"ev:{self.ref_evidence_ref}"), None)
        self.assertIsNotNone(ref_node, "Reference node must exist in graph")
        self.assertEqual(ref_node.get("kind"), "reference")

    def test_03_timeline_remains_valid_after_set_reference(self):
        """Timeline endpoint reflects authentic reference event and derivative identification."""
        url = f"{BASE_URL}/cases/{self.case_ref}/timeline"
        res = requests.get(url, headers=self.headers, timeout=10)
        self.assertEqual(res.status_code, 200, f"Expected 200 for timeline, got {res.status_code}: {res.text}")
        events = res.json()
        self.assertIsInstance(events, list)
        self.assertGreater(len(events), 0, "Timeline must contain events")

        # Verify authentic reference event is present
        ref_event = next((e for e in events if "AUTHENTIC" in (e.get("kind") or "").upper()), None)
        self.assertIsNotNone(ref_event, "Timeline must include AUTHENTIC REFERENCE event")


if __name__ == "__main__":
    unittest.main(verbosity=2)
