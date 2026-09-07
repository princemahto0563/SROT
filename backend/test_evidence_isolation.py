#!/usr/bin/env python3
"""
SROT Evidence Isolation & Dynamic Analysis Verification Suite
============================================================

Verifies that EVERY newly uploaded evidence file (image, video, or audio)
is analyzed independently and dynamically, without inheriting:
  - previous evidence's neural score
  - previous evidence's forensic signals
  - previous evidence's OCR entities
  - previous evidence's origin matches
  - previous evidence's timeline / graph links
  - previous evidence's scam classification / campaign leads
  - previous evidence's report / dossier conclusions

Tests:
  Test A: Existing WhatsApp investment-scam sample
  Test B: Completely unrelated synthetic test video (no scam content)
  Test C: Completely unrelated image with distinct entities (conference banner)
  Test D: Unrelated audio file (.wav tone sweep)
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

BASE = os.environ.get("SROT_API", "http://127.0.0.1:8077")
API = f"{BASE}/api"
TMP = Path(tempfile.gettempdir()) / "srot_isolation_tests"
TMP.mkdir(parents=True, exist_ok=True)

PASS, FAIL = [], []


def head(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def check(name: str, ok: bool, detail: str = "") -> bool:
    if ok:
        PASS.append(name)
        print(f"  [PASS] {name}{' — ' + detail if detail else ''}")
    else:
        FAIL.append(name)
        print(f"  [FAIL] {name}{' — ' + detail if detail else ''}")
    return ok


def poll_job(evidence_ref: str, timeout: int = 120) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = requests.get(f"{API}/evidence/{evidence_ref}/job", timeout=10)
        data = r.json()
        status = data.get("status")
        if status == "completed":
            return data
        if status == "failed":
            raise RuntimeError(f"Job failed for {evidence_ref}: {data.get('error')}")
        time.sleep(1.0)
    raise TimeoutError(f"Job timed out after {timeout}s for {evidence_ref}")


def create_case(title: str, category: str = "Synthetic media") -> str:
    res = requests.post(f"{API}/cases", json={
        "title": title,
        "category": category,
        "officer": "Forensic Isolation Tester",
        "summary": f"Test case container for: {title}",
    }, timeout=10).json()
    return res["case_ref"]


def upload_file(case_ref: str, file_path: Path) -> dict:
    with open(file_path, "rb") as f:
        res = requests.post(
            f"{API}/cases/{case_ref}/evidence",
            files={"file": (file_path.name, f)},
            data={"analyse": "true"},
            timeout=30,
        )
    if res.status_code != 200:
        raise RuntimeError(f"Upload failed ({res.status_code}): {res.text}")
    return res.json()


# ── File Generators for Unrelated Tests ──────────────────────────────────────
def make_unrelated_video(out_path: Path) -> None:
    """Generate a clean 3-second 640x360 MP4 with synthetic geometric color bars."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=3:size=640x360:rate=24",
        "-f", "lavfi", "-i", "sine=frequency=880:duration=3",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def make_unrelated_image(out_path: Path) -> None:
    """Generate a 800x600 PNG image with distinct tech conference text/entities."""
    im = Image.new("RGB", (800, 600), color=(18, 28, 48))
    draw = ImageDraw.Draw(im)
    # Background accents
    draw.rectangle([(20, 20), (780, 580)], outline=(50, 90, 160), width=3)
    draw.rectangle([(40, 40), (760, 100)], fill=(30, 50, 90))
    # Text lines
    lines = [
        "ACME GLOBAL CYBER DEFENSE SUMMIT 2026",
        "Keynote Speaker: Dr. Elena Vance (MIT Quantum Lab)",
        "Conference Portal: https://acme-cyberdefense.org/summit",
        "Direct Hotline: +1-800-555-0199",
        "Registration ID: ACME-CONF-9842",
        "Support Email: inquiries@acme-cyberdefense.org",
    ]
    y = 60
    for line in lines:
        draw.text((60, y), line, fill=(240, 245, 255))
        y += 75
    im.save(out_path)


def make_unrelated_audio(out_path: Path) -> None:
    """Generate a clean 3-second 16kHz WAV audio file with frequency sweep."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
        "-ar", "16000", "-ac", "1",
        str(out_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)


# ── Main Test Runner ────────────────────────────────────────────────────────
def main() -> None:
    head("SROT EVIDENCE ISOLATION & DYNAMIC ANALYSIS TEST SUITE")
    print(f"Target API: {API}")

    # Health check
    h = requests.get(f"{API}/health", timeout=30).json()
    check("Backend health check", h.get("status") == "ok", f"version={h.get('version')}")

    ROOT = Path(__file__).resolve().parent.parent
    sample_scam = ROOT / "data" / "evidence" / "_to_upload" / "WhatsApp_Video_2026-08-17_forwarded.mp4"
    unrelated_vid = TMP / "unrelated_nature_timelapse.mp4"
    unrelated_img = TMP / "unrelated_acme_conference_notice.png"
    unrelated_aud = TMP / "unrelated_acoustic_sensor_sweep.wav"

    make_unrelated_video(unrelated_vid)
    make_unrelated_image(unrelated_img)
    make_unrelated_audio(unrelated_aud)

    # ────────────────────────────────────────────────────────────────────────
    # Test A: WhatsApp Investment Scam Sample
    # ────────────────────────────────────────────────────────────────────────
    head("TEST A: Prepared WhatsApp Investment Scam Sample")
    case_a = "CASE-2026-001"
    res_a = upload_file(case_a, sample_scam)
    ref_a = res_a["evidence"]["evidence_ref"]
    sha_a = res_a["evidence"]["sha256"]
    print(f"Uploaded Test A: {ref_a} (SHA-256: {sha_a[:12]}...)")
    poll_job(ref_a)

    ent_a = requests.get(f"{API}/evidence/{ref_a}/entities").json()
    orig_a = requests.get(f"{API}/evidence/{ref_a}/origin").json()
    graph_a = requests.get(f"{API}/evidence/{ref_a}/graph").json()
    # Check executive dossier PDF and report HTML
    doss_a = requests.get(f"{API}/evidence/{ref_a}/executive-dossier")
    rep_a = requests.get(f"{API}/evidence/{ref_a}/report").json()

    check("Test A completed analysis", True, f"ref={ref_a}")
    check("Test A has entities extracted", ent_a["count"] > 0, f"entities={ent_a['count']}")
    check("Test A has origin matches in corpus", orig_a["match_count"] > 0, f"matches={orig_a['match_count']}")
    check("Test A Executive Dossier is valid PDF", doss_a.status_code == 200 and doss_a.content.startswith(b"%PDF"))
    check("Test A report HTML generated", len(rep_a.get("html", "")) > 100)

    # ────────────────────────────────────────────────────────────────────────
    # Test B: Completely Unrelated Video Upload
    # ────────────────────────────────────────────────────────────────────────
    head("TEST B: Completely Unrelated Video (Geometric Bars & Sine Wave)")
    case_b = create_case("Unrelated Test Video Case", category="Independent Test")
    res_b = upload_file(case_b, unrelated_vid)
    ref_b = res_b["evidence"]["evidence_ref"]
    sha_b = res_b["evidence"]["sha256"]
    print(f"Uploaded Test B: {ref_b} (SHA-256: {sha_b[:12]}...)")
    poll_job(ref_b)

    ev_b = requests.get(f"{API}/evidence/{ref_b}").json()
    an_b = requests.get(f"{API}/evidence/{ref_b}/analysis").json()
    ent_b = requests.get(f"{API}/evidence/{ref_b}/entities").json()
    orig_b = requests.get(f"{API}/evidence/{ref_b}/origin").json()
    graph_b = requests.get(f"{API}/evidence/{ref_b}/graph").json()
    trace_b = requests.get(f"{API}/evidence/{ref_b}/provenance-trace").json()
    doss_b = requests.get(f"{API}/evidence/{ref_b}/executive-dossier")
    rep_b = requests.get(f"{API}/evidence/{ref_b}/report").json()

    # Assertions for Isolation
    check("Test B Evidence Ref is distinct from Test A", ref_b != ref_a, f"B={ref_b} vs A={ref_a}")
    check("Test B SHA-256 is distinct from Test A", sha_b != sha_a, f"B={sha_b[:10]} vs A={sha_a[:10]}")
    check("Test B metadata belongs to new video", ev_b["width"] == 640 and ev_b["height"] == 360, f"{ev_b['width']}x{ev_b['height']}")
    check("Test B origin trace does NOT falsely match WhatsApp scam", orig_b["match_count"] == 0, f"matches={orig_b['match_count']}")
    check("Test B origin empty_reason is honest", "No matching reference found" in (orig_b.get("empty_reason") or ""), orig_b.get("empty_reason"))
    
    # Graph isolation
    b_node_labels = [n.get("label", "") for n in graph_b.get("nodes", [])]
    has_scam_in_graph_b = any("Nirmala" in l or "WhatsApp" in l or "21,000" in l or "Shaktikanta" in l for l in b_node_labels)
    check("Test B graph does NOT leak WhatsApp scam nodes", not has_scam_in_graph_b, f"nodes={len(b_node_labels)}")

    # Campaign / Lead / Report isolation
    rep_b_html = rep_b.get("html", "")
    has_scam_in_report_b = ("Nirmala Sitharaman" in rep_b_html or "Shaktikanta Das" in rep_b_html or "₹21,000" in rep_b_html)
    check("Test B Executive Dossier is valid PDF", doss_b.status_code == 200 and doss_b.content.startswith(b"%PDF"))
    check("Test B Forensic Report does NOT leak scam victim/entities", not has_scam_in_report_b)

    # ────────────────────────────────────────────────────────────────────────
    # Test C: Unrelated Image with Distinct Text/Entities
    # ────────────────────────────────────────────────────────────────────────
    head("TEST C: Unrelated Image (Acme Cyber Summit Notice)")
    case_c = create_case("Acme Conference Event Notice", category="Document / Image")
    res_c = upload_file(case_c, unrelated_img)
    ref_c = res_c["evidence"]["evidence_ref"]
    sha_c = res_c["evidence"]["sha256"]
    print(f"Uploaded Test C: {ref_c} (SHA-256: {sha_c[:12]}...)")
    poll_job(ref_c)

    ev_c = requests.get(f"{API}/evidence/{ref_c}").json()
    an_c = requests.get(f"{API}/evidence/{ref_c}/analysis").json()
    ent_c = requests.get(f"{API}/evidence/{ref_c}/entities").json()
    orig_c = requests.get(f"{API}/evidence/{ref_c}/origin").json()
    graph_c = requests.get(f"{API}/evidence/{ref_c}/graph").json()
    trace_c = requests.get(f"{API}/evidence/{ref_c}/provenance-trace").json()

    check("Test C Evidence Ref is distinct from A & B", ref_c not in (ref_a, ref_b))
    check("Test C SHA-256 is distinct from A & B", sha_c not in (sha_a, sha_b))
    check("Test C media_kind is image", ev_c["media_kind"] == "image")
    check("Test C origin does NOT match WhatsApp scam", orig_c["match_count"] == 0)

    # Entity verification
    c_entity_texts = [e["value"].lower() for e in ent_c.get("entities", [])] + [e["raw_text"].lower() for e in ent_c.get("entities", [])]
    has_scam_entity_c = any("nirmala" in t or "rbi" in t or "21000" in t for t in c_entity_texts)
    check("Test C extracted entities do NOT contain WhatsApp scam data", not has_scam_entity_c)

    # ────────────────────────────────────────────────────────────────────────
    # Test D: Unrelated Audio File
    # ────────────────────────────────────────────────────────────────────────
    head("TEST D: Unrelated Audio File (Acoustic Sine Sweep)")
    case_d = create_case("Acoustic Sensor Audio Intake", category="Audio Forensics")
    res_d = upload_file(case_d, unrelated_aud)
    ref_d = res_d["evidence"]["evidence_ref"]
    sha_d = res_d["evidence"]["sha256"]
    print(f"Uploaded Test D: {ref_d} (SHA-256: {sha_d[:12]}...)")
    poll_job(ref_d)

    ev_d = requests.get(f"{API}/evidence/{ref_d}").json()
    an_d = requests.get(f"{API}/evidence/{ref_d}/analysis").json()
    orig_d = requests.get(f"{API}/evidence/{ref_d}/origin").json()
    trace_d = requests.get(f"{API}/evidence/{ref_d}/provenance-trace").json()

    check("Test D Evidence Ref is distinct from A, B, C", ref_d not in (ref_a, ref_b, ref_c))
    check("Test D SHA-256 is distinct from A, B, C", sha_d not in (sha_a, sha_b, sha_c))
    check("Test D media_kind is audio", ev_d["media_kind"] == "audio")
    check("Test D has audio stream flagged", ev_d["has_audio"] is True)

    # Audio signals computed
    d_sigs = an_d.get("signals", [])
    d_sig_keys = [s["key"] for s in d_sigs]
    check("Test D contains acoustic physical signals", any("acoustic" in k or "silence" in k or "flatness" in k or "pitch" in k for k in d_sig_keys), f"keys={d_sig_keys}")

    # Provenance Trace verification
    d_stages = {s["stage"]: s for s in trace_d.get("stages", [])}
    check("Test D Neural ViT stage marked NOT_APPLICABLE", d_stages.get("NEURAL_SCORE", {}).get("source") == "NOT_APPLICABLE")
    check("Test D OCR stage marked NOT_APPLICABLE", d_stages.get("OCR", {}).get("source") == "NOT_APPLICABLE")
    check("Test D Recapture stage marked NOT_APPLICABLE", d_stages.get("RECAPTURE", {}).get("source") == "NOT_APPLICABLE")
    check("Test D Provenance Trace confirms 100% isolation", trace_d.get("all_stages_isolated") is True)

    # ────────────────────────────────────────────────────────────────────────
    # Summary
    # ────────────────────────────────────────────────────────────────────────
    head("TEST SUMMARY")
    print(f"Total assertions: {len(PASS) + len(FAIL)}")
    print(f"Passed: {len(PASS)}")
    print(f"Failed: {len(FAIL)}")
    if FAIL:
        print("\nFailed checks:")
        for f in FAIL:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("\nALL ISOLATION AND DYNAMIC ANALYSIS TESTS PASSED!")


if __name__ == "__main__":
    main()
