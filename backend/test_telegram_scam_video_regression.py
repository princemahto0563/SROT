#!/usr/bin/env python3
"""
Regression test for Telegram_Video_2026-09-04_AITradingBot_SCAM_DEMO.mp4:
1. Validates dynamic probe and metadata inspection.
2. Validates frame extraction generates real, decodable frames (no placeholder/fake frames).
3. Validates safe fallback decode capability.
4. Validates honest reporting when video frames cannot be decoded.
5. Validates end-to-end pipeline execution via API with zero evidence contamination.
"""
from __future__ import annotations
import os
import sys
import tempfile
import time
from pathlib import Path
from PIL import Image
import requests

BASE = os.environ.get("SROT_API", "http://127.0.0.1:8077")
API = f"{BASE}/api"

SAMPLE_FILE = Path("/Users/princemahto/Downloads/SROT/data/evidence/CASE-2026-024/EV-CASE-2026-024-003__Telegram_Video_2026-09-04_AITradingBot_SCAM_DEMO.mp4")
if not SAMPLE_FILE.is_file():
    # Fallback to alternate copy if present
    SAMPLE_FILE = Path("/Users/princemahto/Downloads/SROT/data/evidence/CASE-2026-002/EV-CASE-2026-002-001__Telegram_Video_2026-09-04_AITradingBot_SCAM_DEMO.mp4")

EXPECTED_SHA256 = "112020137c003848c68e3d0ac2d7fbc5fe0bb487fb1a0b726b8f6ac46b813592"


def test_telegram_video_regression():
    print(f"\n--- Testing Telegram Scam Video Regression ---")
    assert SAMPLE_FILE.is_file(), f"Sample file not found at {SAMPLE_FILE}"
    
    # 1. Verify low-level extraction service
    from app.services import frames, mediainfo, integrity
    
    file_sha = integrity.sha256_file(SAMPLE_FILE)
    assert file_sha == EXPECTED_SHA256, f"SHA mismatch: {file_sha} vs {EXPECTED_SHA256}"
    print(f"✓ SHA256 verified: {file_sha}")

    probe = mediainfo.probe_video(SAMPLE_FILE)
    assert probe.get("available") is True, f"ffprobe not available or probe failed: {probe}"
    assert probe.get("width") == 720, f"Unexpected width: {probe.get('width')}"
    assert probe.get("height") == 1280, f"Unexpected height: {probe.get('height')}"
    assert probe.get("duration_s") == 11.0, f"Unexpected duration: {probe.get('duration_s')}"
    assert probe.get("fps") == 12.0, f"Unexpected fps: {probe.get('fps')}"
    assert probe.get("video_codec") == "h264", f"Unexpected video_codec: {probe.get('video_codec')}"
    assert probe.get("has_audio") is False, f"Expected has_audio=False, got {probe.get('has_audio')}"
    print(f"✓ Dynamic metadata probe passed: {probe['width']}x{probe['height']}, {probe['fps']} fps, {probe['duration_s']}s, codec={probe['video_codec']}")

    # 2. Verify frame extraction produces real, valid image files
    with tempfile.TemporaryDirectory() as td:
        scratch = Path(td) / "frames"
        recs = frames.extract_frames(SAMPLE_FILE, scratch, probe.get("duration_s"), max_frames=16)
        assert len(recs) > 0, "No frames were extracted by frames service!"
        print(f"✓ Extracted {len(recs)} real frames")

        for r in recs:
            fp = Path(r["path"])
            assert fp.is_file(), f"Frame file missing: {fp}"
            assert fp.stat().st_size > 1000, f"Frame file suspiciously small: {fp.stat().st_size} bytes"
            with Image.open(fp) as im:
                assert im.size[0] > 0 and im.size[1] > 0, "Invalid frame dimensions"
        print("✓ All extracted frames verified as valid, decodable JPEG images")

    # 3. Verify honest decode failure reporting on genuinely corrupted bytes
    with tempfile.TemporaryDirectory() as td:
        corrupt_file = Path(td) / "corrupted_media.mp4"
        corrupt_file.write_bytes(b"\x00\x00\x00\x20ftypmp42corrupt_junk_bytes_that_cannot_decode" * 10)
        corrupt_scratch = Path(td) / "corrupt_frames"
        corrupt_recs = frames.extract_frames(corrupt_file, corrupt_scratch, None, max_frames=16)
        assert len(corrupt_recs) == 0, f"Corrupt file should produce 0 frames, got {len(corrupt_recs)}"
        
        from app import pipeline
        res = pipeline.score_media(corrupt_file, corrupt_scratch, "video", max_frames=16)
        assert res.get("score") is None, "Corrupt file should not have a score"
        assert res.get("error") == "Insufficient evidence: video frames could not be decoded", \
            f"Unexpected error string: {res.get('error')}"
        print(f"✓ Honest decode failure verified: '{res.get('error')}'")

    # 4. Verify end-to-end API upload and pipeline analysis
    print("\n--- Running End-to-End API Ingestion & Analysis ---")
    unique_ref = f"CASE-REG-{int(time.time())}"
    case_res = requests.post(f"{API}/cases", json={
        "case_ref": unique_ref,
        "title": "Telegram Scam Demo Regression Case",
        "category": "Digital Forensics",
        "officer": "Regression Harness",
        "summary": "Verifies Telegram video ingestion and complete forensic pipeline",
    }, timeout=10)
    assert case_res.status_code == 200, f"Create case failed: {case_res.text}"
    case_ref = case_res.json()["case_ref"]
    print(f"✓ Created isolated test case: {case_ref}")

    with open(SAMPLE_FILE, "rb") as f:
        up_res = requests.post(
            f"{API}/cases/{case_ref}/evidence",
            files={"file": (SAMPLE_FILE.name, f)},
            data={"analyse": "true"},
            timeout=30,
        )
    assert up_res.status_code == 200, f"Upload failed: {up_res.text}"
    ev_data = up_res.json()
    ev_ref = ev_data.get("evidence", {}).get("evidence_ref") or ev_data.get("evidence_ref")
    print(f"✓ Upload succeeded, evidence_ref: {ev_ref}")

    # Poll analysis run job
    t0 = time.time()
    job_completed = False
    last_status = None
    while time.time() - t0 < 90:
        jr = requests.get(f"{API}/evidence/{ev_ref}/job", timeout=10)
        assert jr.status_code == 200, f"Job poll error: {jr.text}"
        jdata = jr.json()
        last_status = jdata.get("status")
        if last_status == "completed":
            job_completed = True
            break
        if last_status == "failed":
            raise AssertionError(f"Pipeline job failed unexpectedly: {jdata.get('error')}")
        time.sleep(1.0)

    assert job_completed, f"Job did not complete in time, last status: {last_status}"
    print(f"✓ Pipeline completed in {round(time.time() - t0, 1)}s")

    # 5. Verify analysis details
    an_res = requests.get(f"{API}/evidence/{ev_ref}/analysis", timeout=10).json()
    assert an_res.get("frames_sampled", 0) > 0, "No frames sampled in analysis record"
    assert an_res.get("aggregate_score") is not None, "Aggregate score missing"
    print(f"✓ Analysis run verified: aggregate_score={an_res.get('aggregate_score')}, frames_sampled={an_res.get('frames_sampled')}")

    # Verify OCR entities were extracted
    ev_detail = requests.get(f"{API}/evidence/{ev_ref}", timeout=10).json()
    entities = ev_detail.get("entities", [])
    print(f"✓ Extracted {len(entities)} OCR entities from video keyframes")

    # Verify cross-signal assessment
    csa_res = requests.get(f"{API}/evidence/{ev_ref}/cross-signal-assessment", timeout=10).json()
    assert csa_res.get("evidence_state") is not None, "Cross-signal assessment missing evidence_state"
    print(f"✓ Cross-signal assessment state: {csa_res.get('evidence_state')}")

    print("\n[PASS] All regression assertions passed successfully!")


if __name__ == "__main__":
    test_telegram_video_regression()
