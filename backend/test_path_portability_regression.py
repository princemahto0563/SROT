#!/usr/bin/env python3
"""
Regression test for Blocker 3: Evidence Path Resolution and Storage Portability
Tests:
A. Existing absolute Mac path still works when file exists.
B. Existing absolute Mac path that no longer exists falls back safely by re-rooting against active DATA_DIR.
C. Relative stored path resolves correctly under SROT_DATA.
D. Path traversal attempts are rejected.
E. Moving/copying the database + evidence directory into a temporary Linux-style DATA_DIR still allows historical evidence to load.
"""
from __future__ import annotations
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db import get_evidence_path, BASE_DIR, EVIDENCE_DIR
from app.models import Evidence


class TestPathPortabilityRegression(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="srot_path_test_"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_A_existing_absolute_path_returns_directly(self):
        """A. Existing absolute path still works when file exists."""
        test_file = self.temp_dir / "sample_evidence.jpg"
        test_file.write_bytes(b"sample bytes")
        ev = Evidence(stored_path=str(test_file.resolve()))

        resolved = get_evidence_path(ev)
        self.assertEqual(resolved, test_file.resolve())
        self.assertTrue(resolved.exists())

    def test_B_missing_absolute_path_re_roots_to_active_data_dir(self):
        """B. Missing legacy absolute Mac path re-roots against active DATA_DIR."""
        # Create a real file in active EVIDENCE_DIR under a test subfolder
        case_sub = EVIDENCE_DIR / "CASE-MOCK-TEST"
        case_sub.mkdir(parents=True, exist_ok=True)
        dest_file = case_sub / "test_artifact.png"
        dest_file.write_bytes(b"artifact png bytes")

        try:
            # Simulate a historical Mac path that does NOT exist (e.g. from another user's machine)
            nonexistent_mac_path = f"/Users/differentuser/Downloads/SROT/data/evidence/CASE-MOCK-TEST/test_artifact.png"
            ev = Evidence(stored_path=nonexistent_mac_path)

            resolved = get_evidence_path(ev)
            self.assertEqual(resolved.resolve(), dest_file.resolve())
            self.assertTrue(resolved.exists())
            self.assertEqual(resolved.read_bytes(), b"artifact png bytes")
        finally:
            shutil.rmtree(case_sub, ignore_errors=True)

    def test_C_relative_stored_path_resolves_under_srot_data(self):
        """C. Relative stored path resolves correctly under active SROT_DATA."""
        case_sub = EVIDENCE_DIR / "CASE-REL-TEST"
        case_sub.mkdir(parents=True, exist_ok=True)
        dest_file = case_sub / "relative_sample.jpg"
        dest_file.write_bytes(b"relative content")

        try:
            ev = Evidence(stored_path="evidence/CASE-REL-TEST/relative_sample.jpg")
            resolved = get_evidence_path(ev)
            self.assertEqual(resolved.resolve(), dest_file.resolve())
            self.assertTrue(resolved.exists())
            self.assertEqual(resolved.read_bytes(), b"relative content")
        finally:
            shutil.rmtree(case_sub, ignore_errors=True)

    def test_D_path_traversal_is_rejected(self):
        """D. Path traversal outside DATA_DIR raises ValueError."""
        # Attempt to escape via ../
        traversal_attempts = [
            "evidence/../../../../etc/passwd",
            "../../../etc/shadow",
            "evidence/CASE-1/../../../secret.txt",
        ]
        for bad_path in traversal_attempts:
            ev = Evidence(stored_path=bad_path)
            with self.assertRaises(ValueError, msg=f"Should reject: {bad_path}"):
                get_evidence_path(ev)

    def test_E_portable_data_dir_migration(self):
        """E. Moving/copying database + evidence to a temporary Linux-style DATA_DIR still loads evidence."""
        # Setup temporary Linux-style container mount: /tmp/.../var_data
        var_data = self.temp_dir / "var" / "data"
        var_evidence = var_data / "evidence" / "CASE-CONTAINER-TEST"
        var_evidence.mkdir(parents=True, exist_ok=True)

        sample_file = var_evidence / "container_test_image.jpg"
        sample_file.write_bytes(b"container media payload")

        # Temporarily point SROT_DATA to var_data
        orig_srot_data = os.environ.get("SROT_DATA")
        try:
            os.environ["SROT_DATA"] = str(var_data)
            # Re-import or test get_evidence_path with custom SROT_DATA
            from app.db import get_evidence_path as custom_resolver

            # Case item has old Mac path saved in DB
            legacy_stored_path = "/Users/princemahto/Downloads/SROT/data/evidence/CASE-CONTAINER-TEST/container_test_image.jpg"
            ev = Evidence(stored_path=legacy_stored_path)

            resolved = custom_resolver(ev)
            # In the context of the temp data dir, it should resolve to sample_file
            self.assertTrue(resolved.exists(), f"File should be found at {resolved}")
            self.assertEqual(resolved.read_bytes(), b"container media payload")
        finally:
            if orig_srot_data is not None:
                os.environ["SROT_DATA"] = orig_srot_data
            else:
                os.environ.pop("SROT_DATA", None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
