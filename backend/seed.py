#!/usr/bin/env python3
"""
Seed the SROT demo: generate a REAL synthetic media file, derive REAL corpus copies
from it with real FFmpeg transformations, register them, and fingerprint them.

Nothing here is a placeholder record: every corpus item is a file on disk, and every
similarity SROT later reports is computed from these actual files.

    python seed.py            # build corpus + demo case
    python seed.py --reset    # wipe the database and media first
"""
from __future__ import annotations
import argparse, datetime as dt, os, shutil, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.db import (init_db, SessionLocal, CORPUS_DIR, EVIDENCE_DIR, WORK_DIR,
                    PACKET_DIR, DB_PATH)
from app.models import (Case, Evidence, CorpusItem, Fingerprint, FingerprintLedger,
                        AnalysisRun, utcnow)
from app.services import integrity, fingerprint as fp_svc, audit as audit_svc
from app.services import fonts as font_svc

# Resolved at run time — a hardcoded Linux font path breaks seeding on macOS.
FONT = os.environ.get("SROT_FONT") or font_svc.find_font()
FONT_ARG = font_svc.escape_for_filter(FONT)
SEED_DIR = Path(CORPUS_DIR) / "_seed"
BASE = SEED_DIR / "seed_master.mp4"

# Demonstration identifiers. All fictional. RFC-safe / clearly non-real values.
DEMO_UPI = "quickprofit.demo@upi"
DEMO_PHONE = "+91 98765 43210"
DEMO_HANDLE = "@sourcealpha01"
DEMO_URL = "invest-demo.example"


def sh(cmd: list[str], timeout: int = 300) -> None:
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd[:6])}…\n"
                           f"{r.stderr.decode('utf-8', 'replace')[:500]}")


def esc(t: str) -> str:
    return t.replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")


def _text(t: str, size: int, y: str, colour: str = "white",
          start: float | None = None, end: float | None = None, x: str = "(w-text_w)/2") -> str:
    f = (f"drawtext=fontfile={FONT_ARG}:text='{esc(t)}':fontcolor={colour}:fontsize={size}"
         f":x={x}:y={y}:box=1:boxcolor=black@0.88:boxborderw=16")
    if start is not None and end is not None:
        f += f":enable='between(t,{start},{end})'"
    return f


def build_master() -> Path:
    """A 12-second synthetic 'investment scam' clip with legible on-screen identifiers."""
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    if BASE.exists():
        return BASE
    vf = ",".join([
        _text("GUARANTEED RETURNS", 64, "h*0.18", "#FFD84D", 0, 12),
        _text("Double your money in 30 days", 40, "h*0.30", "white", 0, 12),
        _text("SYNTHETIC DEMONSTRATION MEDIA", 26, "h*0.90", "#9BE7FF", 0, 12),
        _text(f"UPI  {DEMO_UPI}", 46, "h*0.46", "#FFFFFF", 1.0, 9),
        _text(f"Call {DEMO_PHONE}", 46, "h*0.58", "#FFFFFF", 3.0, 12),
        _text(DEMO_URL, 44, "h*0.70", "#FFFFFF", 5.0, 12),
        _text("LIMITED SLOTS", 52, "h*0.40", "#FF8A80", 8.5, 12),
    ])
    sh(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "gradients=s=720x1280:d=12:speed=0.05:n=3:c0=0x101820:c1=0x243447:c2=0x0d1b2a",
        "-vf", vf, "-r", "24", "-c:v", "libx264", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-t", "12", str(BASE)])
    return BASE


# (key, label, source_kind, hours_before_seizure, ffmpeg -vf, transform description)
CORPUS_SPEC = [
    ("copy_a", "forum_post_8841", "forum", 96,
     "null", "unmodified re-upload of the source media"),
    ("copy_b", "@chd_alerts_now", "channel", 70,
     "scale=-2:960", "downscaled to 960p and re-encoded"),
    ("copy_c", "@city_updates_", "channel", 62,
     "crop=iw*0.90:ih*0.90,scale=-2:854", "cropped 10% and downscaled"),
    ("copy_d", "@news_pulse_ch", "aggregator", 40,
     "drawbox=x=0:y=ih-70:w=iw:h=70:color=black@0.7:t=fill,"
     "drawtext=fontfile=" + FONT_ARG + ":text='NEWSPULSE':fontcolor=white:fontsize=34:x=20:y=h-52",
     "watermark band burned in"),
    ("copy_e", "mirror_repost_77", "mirror", 20,
     "scale=-2:640", "heavily downscaled mirror upload"),
]


def build_corpus_files() -> list[dict]:
    out = []
    for key, label, kind, hours, vf, transform in CORPUS_SPEC:
        dst = Path(CORPUS_DIR) / f"{key}.mp4"
        if not dst.exists():
            cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(BASE)]
            if vf != "null":
                cmd += ["-vf", vf]
            cmd += ["-c:v", "libx264", "-preset", "veryfast", "-b:v", "1200k",
                    "-pix_fmt", "yuv420p", "-an", str(dst)]
            sh(cmd)
        out.append({"key": key, "label": label, "kind": kind, "hours": hours,
                    "path": dst, "transform": transform})
    return out


def build_seized_copy() -> Path:
    """
    The copy that reaches the investigator: screen-recorded, letterboxed, with a
    persistent interface band carrying the original poster's handle — and with all
    metadata stripped and the filename changed. This is the demo's whole point.
    """
    dst = SEED_DIR / "WhatsApp_Video_2026-08-17_forwarded.mp4"
    if dst.exists():
        return dst
    status = (f"drawbox=x=0:y=0:w=iw:h=96:color=black@0.92:t=fill,"
              f"drawtext=fontfile={FONT_ARG}:text='{esc(DEMO_HANDLE)}':fontcolor=white:fontsize=34"
              f":x=24:y=18,"
              f"drawtext=fontfile={FONT_ARG}:text='{esc('Forwarded many times')}':fontcolor=0xB8C4D0"
              f":fontsize=24:x=24:y=58,"
              f"drawtext=fontfile={FONT_ARG}:text='{esc('9:41')}':fontcolor=white:fontsize=26"
              f":x=w-90:y=22")
    vf = f"scale=-2:900,pad=iw:ih+150:0:96:black,{status},gblur=sigma=0.4"
    sh(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(BASE),
        "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-b:v", "700k",
        "-pix_fmt", "yuv420p", "-an",
        "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:v", "+bitexact",
        str(dst)])
    return dst


def hash_media(path: Path, scratch: Path, max_frames: int = 12) -> list[dict]:
    """
    Real perceptual hashes over real sampled frames, one hash per normalised view.
    Returns hash_frames() records: {"frame_index", "phash", "dhash", "whash", "views"}.
    """
    from app.services import frames as frame_svc, mediainfo
    scratch.mkdir(parents=True, exist_ok=True)
    probe = mediainfo.probe_video(path)
    recs = frame_svc.extract_frames(path, scratch, probe.get("duration_s"), max_frames=max_frames)
    return fp_svc.hash_frames([r["path"] for r in recs])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()

    if args.reset:
        for p in (DB_PATH,):
            Path(p).unlink(missing_ok=True)
        for d in (EVIDENCE_DIR, WORK_DIR, PACKET_DIR, CORPUS_DIR):
            shutil.rmtree(d, ignore_errors=True); Path(d).mkdir(parents=True, exist_ok=True)
        print("· reset: database and media cleared")

    init_db()
    db = SessionLocal()
    try:
        if db.query(CorpusItem).count() > 0:
            print("· corpus already seeded — nothing to do (use --reset to rebuild)")
            return

        print("· generating synthetic master media with FFmpeg …")
        build_master()
        print("· deriving reference-corpus copies (real transformations) …")
        items = build_corpus_files()
        seized = build_seized_copy()

        now = utcnow()
        print("· registering and fingerprinting corpus …")
        for it in items:
            observed = now - dt.timedelta(hours=it["hours"])
            ci = CorpusItem(label=it["label"], source_kind=it["kind"],
                            filename=it["path"].name, stored_path=str(it["path"]),
                            observed_at=observed,
                            sha256=integrity.sha256_file(it["path"]),
                            is_synthetic=True, transform=it["transform"],
                            note="SYNTHETIC DEMONSTRATION RECORD — generated for the SROT prototype.")
            db.add(ci); db.commit(); db.refresh(ci)
            hashes = hash_media(it["path"], Path(WORK_DIR) / "corpus" / it["key"])
            for fh in hashes:
                for view, hx in (fh.get("views") or {}).items():
                    db.add(Fingerprint(corpus_id=ci.id, hash_type=fp_svc.view_hash_type(view),
                                       hash_hex=hx, frame_index=fh["frame_index"]))
            db.commit()
            print(f"    {ci.label:22} {len(hashes):2d} frame hashes  observed {observed:%d %b %H:%M}")

        # ── a second, older case so cross-case linking has something real to find ──
        print("· seeding a prior case for cross-case linking …")
        prior = Case(case_ref="CASE-2026-002", title="Circulating investment inducement clip (prior case)",
                     category="Synthetic media", officer="Investigating Officer (demo)",
                     summary="Earlier complaint involving visually similar media. "
                             "SYNTHETIC DEMONSTRATION CASE.")
        db.add(prior); db.commit(); db.refresh(prior)
        prior_hashes = hash_media(items[1]["path"], Path(WORK_DIR) / "corpus" / "prior")
        db.add_all([FingerprintLedger(perceptual_hash=hx, hash_type=fp_svc.view_hash_type(view),
                                      case_ref=prior.case_ref, evidence_ref="EV-CASE-2026-002-001",
                                      filename=items[1]["path"].name, frame_index=fh["frame_index"])
                    for fh in prior_hashes for view, hx in (fh.get("views") or {}).items()])
        db.commit()

        # ── the live demo case, with the seized copy pre-staged for upload ──
        demo = Case(case_ref="CASE-2026-001",
                    title="Suspicious investment inducement video",
                    category="Synthetic media / financial inducement",
                    officer="Investigating Officer (demo)",
                    summary="A short video circulating on public channels promotes a guaranteed-return "
                            "investment scheme. The copy received with the complaint carries no metadata "
                            "and a changed filename. Submitted for authenticity assessment and source "
                            "tracing. SYNTHETIC DEMONSTRATION CASE.")
        db.add(demo); db.commit(); db.refresh(demo)
        audit_svc.record(db, case_id=demo.id, action=f"Case {demo.case_ref} opened",
                         component="case manager", payload={"seeded": True})

        staged = Path(EVIDENCE_DIR) / "_to_upload"
        staged.mkdir(parents=True, exist_ok=True)
        shutil.copy2(seized, staged / seized.name)
        shutil.copy2(items[0]["path"], staged / "clean_original_copy.mp4")

        print(f"\n✓ Seeded {len(items)} corpus items, 2 cases, "
              f"{db.query(FingerprintLedger).count()} ledger entries")
        print(f"✓ Demo file ready to upload: {staged / seized.name}")
        print(f"  (a clean copy is also staged: {staged / 'clean_original_copy.mp4'})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
