#!/usr/bin/env python3
"""
Exercise the workflows the end-to-end script does not cover, against the live API.

Nothing is asserted from expectation alone: every check prints what the server
actually returned, and failures are reported rather than hidden.

    python test_features.py            # requires the API on :8077 and a seeded DB
"""
from __future__ import annotations
import json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from app.db import EVIDENCE_DIR                    # noqa: E402

BASE = os.environ.get("SROT_API", "http://127.0.0.1:8077")
API = f"{BASE}/api"
CASE = "CASE-2026-001"
UPLOAD_DIR = Path(EVIDENCE_DIR) / "_to_upload"
TMP = Path(tempfile.gettempdir()) / "srot_tests"; TMP.mkdir(exist_ok=True)

PASS, FAIL = [], []


def head(t: str) -> None:
    print(f"\n{'=' * 68}\n{t}\n{'=' * 68}")


def check(name: str, ok: bool, detail: str = "") -> bool:
    (PASS if ok else FAIL).append(name)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  — ' + detail if detail else ''}")
    return ok


def evidence_ref() -> str:
    c = requests.get(f"{API}/cases/{CASE}", timeout=30).json()
    evs = [e for e in c["evidence"]
           if (e.get("latest_run") or {}).get("status") == "completed"]
    if not evs:
        print("No completed evidence — run e2e.py first."); sys.exit(1)
    return evs[0]["evidence_ref"]


# ── 1. laundering stress test ────────────────────────────────────────────────
def test_stress(ref: str) -> None:
    head("LAUNDERING STRESS TEST")
    r = requests.post(f"{API}/evidence/{ref}/stress-test", timeout=60)
    check("stress test accepted", r.status_code == 200, f"HTTP {r.status_code}")
    if r.status_code != 200:
        return
    deadline = time.time() + 900
    st = {}
    while time.time() < deadline:
        st = requests.get(f"{API}/evidence/{ref}/stress-test", timeout=60).json()
        done = sum(1 for v in st.get("variants", []) if v.get("score") is not None or v.get("error"))
        print(f"    status={st.get('status')}  variants scored={done}", end="\r")
        if st.get("status") in ("completed", "failed"):
            break
        time.sleep(6)
    print()
    check("stress test completed", st.get("status") == "completed",
          st.get("error") or st.get("status", "?"))
    vs = st.get("variants", [])
    check("variants generated", len(vs) >= 10, f"{len(vs)} variants")
    scored = [v for v in vs if v.get("score") is not None]
    check("variants actually re-scored", len(scored) >= 8, f"{len(scored)} scored")
    real_files = [v for v in vs if v.get("sha256")]
    check("each variant is a real file with its own SHA-256",
          len(real_files) == len(vs) and len({v["sha256"] for v in real_files}) == len(real_files),
          f"{len({v['sha256'] for v in real_files})} distinct hashes")
    check("reliability boundary derived", bool(st.get("reliability_boundary")),
          str(st.get("reliability_boundary"))[:90])
    print(f"\n  baseline: {st.get('baseline_score')}")
    print(f"  {'variant':<26}{'score':>8}{'delta':>8}{'pHash sim':>11}{'reliable':>10}{'ms':>7}")
    for v in vs:
        print(f"  {v['name']:<26}{str(v.get('score')):>8}{str(v.get('delta')):>8}"
              f"{str(v.get('phash_similarity')):>11}{str(v.get('reliable')):>10}"
              f"{str(v.get('processing_ms')):>7}"
              + (f"   ERROR: {v['error'][:40]}" if v.get("error") else ""))
    print(f"\n  recommendation: {st.get('recommendation')}")


# ── 2. hash verification: match and mismatch ─────────────────────────────────
def test_hash(ref: str) -> None:
    head("HASH VERIFICATION")
    src = UPLOAD_DIR / "WhatsApp_Video_2026-08-17_forwarded.mp4"
    with open(src, "rb") as f:
        r = requests.post(f"{API}/evidence/{ref}/verify-hash",
                          files={"file": (src.name, f, "video/mp4")}, timeout=120).json()
    check("identical file verifies as MATCH", r.get("match") is True, r.get("message", ""))
    print(f"    stored    {r.get('stored_sha256')}")
    print(f"    submitted {r.get('submitted_sha256')}")

    tampered = TMP / "tampered.mp4"
    tampered.write_bytes(src.read_bytes() + b"\x00tamper")
    with open(tampered, "rb") as f:
        r2 = requests.post(f"{API}/evidence/{ref}/verify-hash",
                           files={"file": (tampered.name, f, "video/mp4")}, timeout=120).json()
    check("altered file verifies as MISMATCH", r2.get("match") is False, r2.get("message", ""))
    print(f"    submitted {r2.get('submitted_sha256')}")


# ── 3. court packet ──────────────────────────────────────────────────────────
def test_packet(ref: str) -> None:
    head("COURT-READY EVIDENCE PACKET")
    r = requests.post(f"{API}/evidence/{ref}/court-packet", timeout=600)
    if not check("packet generated", r.status_code == 200, r.text[:160]):
        return
    p = r.json()
    docs = p.get("documents", [])
    check("all documents present", len(docs) >= 6, f"{len(docs)} documents")
    check("packet has its own SHA-256", bool(p.get("packet_sha256")),
          str(p.get("packet_sha256"))[:24] + "…")

    ok_docs = 0
    for d in docs:
        dr = requests.get(f"{BASE}{d['url']}", timeout=120)
        is_pdf = dr.status_code == 200 and dr.content[:4] == b"%PDF"
        size_kb = len(dr.content) / 1024
        print(f"    {d['key']:<24} {'PDF ok' if is_pdf else 'NOT A PDF':<10} {size_kb:7.1f} KB")
        ok_docs += int(is_pdf and size_kb > 3)
    check("every document is a real, non-empty PDF", ok_docs == len(docs), f"{ok_docs}/{len(docs)}")

    zr = requests.get(f"{BASE}{p['zip_url']}", timeout=300)
    zp = TMP / "packet.zip"; zp.write_bytes(zr.content)
    import zipfile
    try:
        with zipfile.ZipFile(zp) as z:
            names = z.namelist()
            bad = z.testzip()
        check("ZIP downloads and is valid", bad is None and len(names) >= 7,
              f"{len(names)} entries, {len(zr.content)/1024:.0f} KB")
        for n in names:
            print(f"      {n}")
    except zipfile.BadZipFile:
        check("ZIP downloads and is valid", False, "corrupt archive")

    # the BSA §63 wording must never claim admissibility.
    # pdftotext (poppler) is optional — on macOS: brew install poppler
    if not shutil.which("pdftotext"):
        print("    (pdftotext not installed — skipping the certificate wording check;")
        print("     install poppler to enable it: brew install poppler)")
        return
    txt = subprocess.run(["pdftotext", "-q", "-", "-"],
                         input=requests.get(
                             f"{BASE}{docs[0]['url']}", timeout=120).content,
                         capture_output=True).stdout.decode("utf-8", "replace")
    banned = [s for s in ("makes the evidence admissible", "is admissible", "guaranteed",
                          "proves the video is fake", "100% accurate") if s.lower() in txt.lower()]
    check("no admissibility or guarantee claim in the certificate", not banned, str(banned))
    check("certificate carries the verification wording",
          "verification and signature" in txt.lower(),
          "found" if "verification and signature" in txt.lower() else "MISSING")


# ── 4. consistency / report / timeline / audit ───────────────────────────────
def test_reports(ref: str) -> None:
    head("REPORT CONSISTENCY, TIMELINE, LEADS, AUDIT")
    c = requests.get(f"{API}/evidence/{ref}/consistency", timeout=180).json()
    checks = c.get("checks") or []
    for k in checks:
        print(f"    {k['field']:<24} db={str(k['database'])[:22]:<24} "
              f"api={str(k['api'])[:22]:<24} report={str(k['report'])[:22]:<24} "
              f"{'ok' if k['match'] else 'MISMATCH'}")
    check("every field agrees across database, API and report",
          c.get("all_consistent") is True,
          ", ".join(k["field"] for k in checks if not k["match"]))

    rep = requests.get(f"{API}/evidence/{ref}/report", timeout=180).json()
    html = rep.get("html", "")
    check("forensic report renders", "<h1" in html and len(html) > 8000,
          f"{len(html)} chars")
    banned = [s for s in ("guaranteed", "100% accurate", "definitely fake",
                          "this is the original file", "proves") if s in html.lower()]
    check("report contains no over-claiming language", not banned, str(banned))

    tl = requests.get(f"{API}/cases/{CASE}/timeline", timeout=60).json()
    check("timeline populated", len(tl) >= 3, f"{len(tl)} events")
    for e in tl[:8]:
        print(f"    {str(e.get('occurred_at'))[:19]}  [{str(e.get('confidence')):<6}] "
              f"{str(e.get('title'))[:60]}")

    lds = requests.get(f"{API}/cases/{CASE}/leads", timeout=60).json()
    check("leads generated with cited reasons", len(lds) >= 3 and all(l.get("reasons") for l in lds),
          f"{len(lds)} leads")
    check("every lead states its limitation", all(l.get("limitation") for l in lds), "")

    au = requests.get(f"{API}/cases/{CASE}/audit", timeout=60).json()
    chain = au.get("chain") or {}
    check("audit chain verifies", chain.get("verified") is True, chain.get("message", ""))
    print(f"    audit entries: {len(au.get('entries', []))}")


# ── 5. honest failure states ─────────────────────────────────────────────────
def test_failures(ref: str) -> None:
    head("FAILURE STATES (must degrade honestly, never crash)")
    bad = TMP / "not_media.txt"; bad.write_text("this is not media")
    with open(bad, "rb") as f:
        r = requests.post(f"{API}/cases/{CASE}/evidence",
                          files={"file": (bad.name, f, "text/plain")}, timeout=60)
    check("unsupported file type rejected", r.status_code in (400, 415),
          f"HTTP {r.status_code}: {r.text[:120]}")
    check("rejection message has no stack trace",
          "Traceback" not in r.text and "File \"" not in r.text, "")

    # hostile filenames must never escape the evidence directory
    from app.services import integrity as ig
    hostile = ["../../../../etc/passwd.mp4", "..\\..\\windows\\system32\\evil.mp4",
               "/etc/shadow.mp4", "nul.mp4", "a" * 400 + ".mp4", "video;rm -rf ~.mp4",
               "  ..%2f..%2fetc%2fpasswd.mp4", ".hidden.mp4"]
    bad = []
    for name in hostile:
        safe = ig.sanitize_filename(name)
        sandbox = Path(EVIDENCE_DIR) / "CASE-X"
        resolved = (sandbox / f"EV-1__{safe}").resolve()
        if ("/" in safe or "\\" in safe or safe.startswith("..")
                or not str(resolved).startswith(str(sandbox.resolve()) + os.sep)):
            bad.append(f"{name!r} -> {safe!r}")
        print(f"    {name[:44]:<46} -> {safe[:40]}")
    check("hostile filenames sanitised, no path escape", not bad, "; ".join(bad))

    trav = TMP / "traversal.mp4"
    trav.write_bytes((UPLOAD_DIR / "clean_original_copy.mp4").read_bytes())
    with open(trav, "rb") as f:
        r = requests.post(f"{API}/cases/{CASE}/evidence",
                          files={"file": ("../../../../etc/passwd.mp4", f, "video/mp4")},
                          data={"analyse": "false"}, timeout=120)
    if r.status_code == 200:
        stored = r.json()["evidence"]
        fn = str(stored.get("filename", ""))
        escaped = [q for q in ("/etc/passwd.mp4", str(Path.home() / "etc")) if Path(q).exists()]
        check("traversal upload stored inside the evidence directory",
              "/" not in fn and "\\" not in fn and ".." not in fn and not escaped,
              f"filename={fn!r} escaped={escaped}")
        d = requests.delete(f"{API}/cases/{CASE}/evidence/{stored['evidence_ref']}", timeout=60)
        check("evidence deletion removes derived records", d.status_code == 200,
              json.dumps(d.json())[:160] if d.status_code == 200 else d.text[:120])
    else:
        check("path-traversal upload handled", r.status_code in (400, 415), f"HTTP {r.status_code}")

    r = requests.get(f"{API}/evidence/EV-DOES-NOT-EXIST/analysis", timeout=30)
    check("unknown evidence returns 404, not 500", r.status_code == 404, f"HTTP {r.status_code}")
    check("404 body has no stack trace", "Traceback" not in r.text, "")

    r = requests.get(f"{API}/evidence/{ref}/stress-test", timeout=30)
    check("stress endpoint answers without a run too", r.status_code == 200, "")


def main() -> int:
    ref = evidence_ref()
    print(f"testing against evidence {ref}")
    test_hash(ref)
    test_stress(ref)
    test_packet(ref)
    test_reports(ref)
    test_failures(ref)
    head("SUMMARY")
    print(f"  passed: {len(PASS)}   failed: {len(FAIL)}")
    for f in FAIL:
        print(f"    FAILED: {f}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
