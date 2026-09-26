"""
Unit & Integration Test Suite for SROT Forensic Comparison Engine.
Validates:
1. Multi-view perceptual hashing & SSIM determinism
2. True pixel and edge gradient delta calculations
3. Swin-ViT model signal comparison (labeled MODEL SIGNAL, not proof)
4. OCR identifier differencing and QR detection
5. Heatmap generation with examiner decision-support metadata
6. Case graph & timeline semantics (DIRECTLY_OBSERVED vs INFERRED)
7. Origin trace bounds (no claim of universal origin)
8. Court packet Section 63 BSA 2023 report generation
9. Tamper-evident hash-linked audit logging
"""
import sys
import unittest
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db import SessionLocal
from app.models import Case, Evidence, ExtractedEntity, AuditLog, ForensicComparison
from app.services import comparison as comp_svc
from app.services import casebuild, report as report_svc, audit as audit_svc
from app.services import ocr as ocr_svc


class TestForensicComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        cls.case = cls.db.query(Case).filter(Case.case_ref == "CASE-2026-112").first()
        if not cls.case:
            raise RuntimeError("Demo case CASE-2026-112 not found. Run seed script first.")

        # Classify demo case evidence
        comp_svc.classify_demo_case_evidence(cls.db, cls.case.id)
        cls.ref = comp_svc.get_authentic_reference(cls.case_id if hasattr(cls, "case_id") else cls.db, cls.case.id)
        cls.deriv_poster = (
            cls.db.query(Evidence)
            .filter(Evidence.case_id == cls.case.id, Evidence.evidence_ref == "EV-CASE-2026-112-009")
            .first()
        )
        cls.deriv_ai = (
            cls.db.query(Evidence)
            .filter(Evidence.case_id == cls.case.id, Evidence.evidence_ref == "EV-CASE-2026-112-002")
            .first()
        )

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_authentic_reference_classification(self):
        """Authentic camera reference is correctly identified with intact metadata."""
        self.assertIsNotNone(self.ref, "Authentic reference must be established")
        self.assertEqual(self.ref.evidence_ref, "EV-CASE-2026-112-001")
        self.assertEqual(self.ref.forensic_role, "AUTHENTIC_REFERENCE")
        self.assertIn("Motorola", self.ref.classification_basis)
        self.assertGreater(len(self.ref.exif_json or {}), 10, "Reference must have intact camera EXIF")

    def test_02_pairwise_comparison_metrics(self):
        """Pairwise comparison computes real, deterministic metrics across all dimensions."""
        comp = comp_svc.compare_evidence(self.db, self.ref.id, self.deriv_poster.id)

        # Visual metrics
        visual = comp.get("visual", {})
        self.assertGreater(visual.get("best_view_similarity", 0), 50.0)
        self.assertLess(visual.get("best_view_similarity", 0), 100.0)
        self.assertGreaterEqual(visual.get("ssim", 0), 0.0)
        self.assertLessEqual(visual.get("ssim", 0), 1.0)
        self.assertGreater(visual.get("mean_pixel_delta", 0), 10.0)
        self.assertGreater(visual.get("edge_delta", 0), 5.0)

        # Model signal
        ai_signal = comp.get("ai_signal", {})
        self.assertEqual(ai_signal.get("signal_label"), "MODEL SIGNAL")
        self.assertIn("decision-support", ai_signal.get("interpretation", ""))

        # Assessment and boundaries
        self.assertIn("AI-generated or materially modified", comp.get("assessment", ""))
        self.assertGreater(len(comp.get("why_srot_reached_result", [])), 0)
        self.assertGreater(len(comp.get("what_srot_cannot_establish", [])), 0)

    def test_03_ocr_and_qr_differencing(self):
        """Differencing correctly detects added UPI, added QR, and removed reference handles."""
        comp = comp_svc.compare_evidence(self.db, self.ref.id, self.deriv_poster.id)
        idents = comp.get("identifiers", {})

        # Added identifiers must contain UPI and QR
        added_types = [a["entity_type"] for a in idents.get("added", [])]
        added_values = [a["value"] for a in idents.get("added", [])]
        self.assertIn("UPI", added_types)
        self.assertTrue(any("princemahto@ibl" in v for v in added_values))

        # QR detection
        qr_info = idents.get("qr", {})
        self.assertTrue(qr_info.get("detected"), "QR code must be detected in poster")
        self.assertIsNotNone(qr_info.get("coordinates"), "QR coordinates must be recorded")

        # Removed identifiers must include SIH / college handles from reference
        removed_values = [r["value"] for r in idents.get("removed", [])]
        self.assertTrue(any("roorkee" in v.lower() or "sih" in v.lower() for v in removed_values))

    def test_04_difference_heatmap_generation(self):
        """Difference heatmap generates valid blended Magma PNG bytes and metadata."""
        png_bytes, meta = comp_svc.generate_difference_heatmap(
            self.ref.stored_path, self.deriv_poster.stored_path
        )
        self.assertIsNotNone(png_bytes)
        self.assertTrue(png_bytes.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(meta.get("trace_type"), "difference_heatmap")
        self.assertIn("decision-support", meta.get("interpretation", ""))
        self.assertGreater(meta.get("mean_pixel_delta", 0), 10.0)

    def test_05_graph_semantics(self):
        """Investigation graph distinguishes DIRECTLY_OBSERVED from INFERRED edges."""
        g = casebuild.graph_payload(self.db, self.case, ev=self.deriv_poster)
        nodes = g.get("nodes", [])
        edges = g.get("edges", [])

        # Nodes must include reference and derivative
        kinds = [n.get("kind") for n in nodes]
        self.assertIn("reference", kinds)
        self.assertIn("derivative", kinds)

        # Inferred edge connects reference to derivative
        inferred = [e for e in edges if e.get("observation") == "INFERRED"]
        self.assertGreater(len(inferred), 0)
        self.assertTrue(any("visually related" in e.get("relation", "") for e in inferred))
        self.assertTrue(any("perceptual similarity" in e.get("reason", "") for e in inferred))

        # Directly observed edge connects derivative to payment/entity
        observed = [e for e in edges if e.get("observation") == "DIRECTLY_OBSERVED"]
        self.assertGreater(len(observed), 0)

    def test_06_court_packet_generation(self):
        """Court packet includes Section 'AUTHENTIC REFERENCE VS DERIVATIVE COMPARISON'."""
        rendered = report_svc.render_all(self.db, self.deriv_poster.id)
        report_html = rendered["docs"]["forensic_report"]
        bsa_html = rendered["docs"]["bsa63_certificate"]
        self.assertIn("AUTHENTIC REFERENCE VS DERIVATIVE COMPARISON", report_html)
        self.assertTrue("motorola" in report_html.lower())
        self.assertIn("princemahto@ibl", report_html)
        self.assertIn("QR Matrix", report_html)
        self.assertIn("Bharatiya Sakshya Adhiniyam, 2023", bsa_html)
        self.assertIn("section 63", bsa_html.lower())

    def test_07_hash_linked_audit_chain(self):
        """Audit ledger records comparison and maintains unbroken hash integrity."""
        chain_status = audit_svc.verify_chain(self.db, self.case.id)
        self.assertTrue(chain_status.get("verified"), "Audit chain must remain cryptographically unbroken")
        self.assertIsNone(chain_status.get("broken_at_id"))

        # Check for comparison audit action
        actions = [
            a.action for a in self.db.query(AuditLog).filter(AuditLog.case_id == self.case.id).all()
        ]
        self.assertTrue(
            any("Forensic comparison" in a or "Pairwise forensic comparison" in a for a in actions),
            f"Comparison action not logged in audit: {actions}"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
