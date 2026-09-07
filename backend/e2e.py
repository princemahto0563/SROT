"""End-to-end walk of the whole pipeline against the running API."""
import json, os, time, sys, requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db import EVIDENCE_DIR                    # noqa: E402

B = os.environ.get("SROT_API", "http://127.0.0.1:8077") + "/api"
F = str(Path(EVIDENCE_DIR) / "_to_upload" / "WhatsApp_Video_2026-08-17_forwarded.mp4")
if not Path(F).exists():
    sys.exit(f"Demonstration media not found at {F}\nRun `python seed.py --reset` first.")
def p(t): print(f"\n{'='*68}\n{t}\n{'='*68}")

p("UPLOAD (metadata-stripped, renamed forward)")
with open(F,"rb") as fh:
    r = requests.post(f"{B}/cases/CASE-2026-001/evidence", files={"file": (Path(F).name, fh, "video/mp4")}, timeout=180)
r.raise_for_status(); up = r.json(); ev = up["evidence"]["evidence_ref"]
print("evidence_ref :", ev)
print("sha256       :", up["evidence"]["sha256"])
print("size         :", up["evidence"]["size_bytes"], "bytes")

p("JOB PROGRESS")
for i in range(240):
    j = requests.get(f"{B}/evidence/{ev}/job", timeout=30).json()
    if j["status"] in ("completed","failed"): break
    time.sleep(2)
print(json.dumps(j, indent=1))
if j["status"] != "completed": print(open("/tmp/srot.log").read()[-3000:]); sys.exit(1)

p("ANALYSIS")
a = requests.get(f"{B}/evidence/{ev}/analysis", timeout=60).json()
print("assessment   :", a["assessment"], "| band:", a["confidence_band"], "| score:", a["aggregate_score"])
print("backend      :", a["detector_backend"], "| neural loaded:", a["neural_detector_loaded"])
print("dissent      :", a["dissent"])
for s in a["signals"]:
    print(f"  {s['name'][:38]:38} {str(s['result'])[:28]:28} {str(s['score']):>7}  w={s['weight']}")

p("ORIGIN TRACE")
o = requests.get(f"{B}/evidence/{ev}/origin", timeout=60).json()
print("corpus size  :", o["corpus_size"], "| matches:", o["match_count"], "| max sim:", o["max_similarity"])
for m in o["matches"]:
    print(f"  {m['label']:22} sim={m['similarity']:6.2f}%  ham={m['hamming']:2d}/64  {m['observed_at'][:16]}  {'<-- EARLIEST' if m['is_earliest'] else ''}")
print("established  :", o["established"], "| span days:", o["propagation_span_days"])

p("RECAPTURE FORENSICS")
rc = requests.get(f"{B}/evidence/{ev}/recapture", timeout=60).json()
print("likelihood   :", rc["likelihood"], "score:", rc["score"])
print("metadata     :", rc["metadata_status"], "|", rc["provenance_status"])
print("letterbox    :", json.dumps(rc["letterbox"])[:150])
print("static bands :", json.dumps(rc["static_bands"])[:170])
print("handles      :", rc["recovered_handles"])
print("note         :", rc["note"])

p("OCR ENTITIES")
e = requests.get(f"{B}/evidence/{ev}/entities", timeout=60).json()
print("count:", e["count"], "| langs available:", e["ocr_languages_available"], "| scripts:", e["scripts_detected"])
for x in e["entities"][:14]:
    print(f"  {x['entity_type']:8} {x['value'][:36]:36} frame={x['frame_number']} bbox={x['bbox']} conf={x['ocr_confidence']}")

p("GRAPH / CAMPAIGN / LEADS")
g = requests.get(f"{B}/evidence/{ev}/graph", timeout=60).json(); print("graph stats:", g["stats"])
c = requests.get(f"{B}/cases/CASE-2026-001/campaign-matches", timeout=60).json()
print("campaign matches:", c["count"], [ (m["other_case_ref"], m["similarity"]) for m in c["matches"] ])
l = requests.get(f"{B}/cases/CASE-2026-001/leads", timeout=60).json()
for x in l[:4]: print(f"  #{x['rank']} [{x['priority']}] {x['title'][:70]}")
