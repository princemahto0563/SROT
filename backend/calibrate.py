#!/usr/bin/env python3
"""
Measure the perceptual-hash match threshold instead of guessing it.

Builds two populations from real media and measures BOTH quantities the production
matcher uses:

  TRUE DERIVATIVES   the seized copy vs each reference-corpus copy of the same source
  UNRELATED CONTROLS the seized copy vs synthetic clips of entirely different content

For each it reports the minimum multi-view Hamming distance AND how many query frames
independently corroborate a match at that distance. Distance alone does not separate
the populations — a degenerate control (colour bars) can produce one lucky frame pair
close to the threshold. Corroboration is what actually separates them.

If either measure fails to separate the two populations, the script says so and exits
non-zero rather than recommending a threshold. That is the honest outcome, and it is
what you should expect on harder material than this demonstration corpus.

    python calibrate.py
"""
from __future__ import annotations
import subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.db import CORPUS_DIR, WORK_DIR                     # noqa: E402
from app.services import fingerprint as fp_svc, frames as frame_svc, mediainfo  # noqa: E402

SEED = Path(CORPUS_DIR) / "_seed"
WORK = Path(WORK_DIR) / "_calibration"

CONTROLS = {
    "control_testsrc": "testsrc2=s=720x1280:r=24",
    "control_smptebars": "smptebars=s=720x1280:r=24",
    "control_gradient": "gradients=s=720x1280:speed=0.3:n=4:c0=0x882200:c1=0x00aa88:c2=0xffee00",
    "control_mandelbrot": "mandelbrot=s=720x1280:r=24",
    "control_life": "life=s=720x1280:r=24:mold=10",
    "control_rgbtest": "rgbtestsrc=s=720x1280:r=24",
    "control_testpattern": "testsrc=s=720x1280:r=24",
    "control_black": "color=c=black:s=720x1280:r=24",
    "control_grey": "color=c=gray:s=720x1280:r=24",
}


def build_controls() -> dict[str, Path]:
    WORK.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, src in CONTROLS.items():
        p = WORK / f"{name}.mp4"
        if not p.exists():
            r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                                "-f", "lavfi", "-i", src, "-c:v", "libx264", "-preset", "veryfast",
                                "-pix_fmt", "yuv420p", "-t", "6", str(p)], capture_output=True)
            if r.returncode != 0:
                print(f"  · skipping {name}: ffmpeg source unavailable")
                continue
        out[name] = p
    return out


def views_for(path: Path, tag: str, n: int = 8) -> list[dict[str, str]]:
    d = WORK / "frames" / tag
    if not (d.exists() and any(d.glob("*.jpg"))):
        d.mkdir(parents=True, exist_ok=True)
        frame_svc.extract_frames(path, d, mediainfo.probe_video(path).get("duration_s"),
                                 max_frames=n)
    paths = sorted(str(p) for p in d.glob("*.jpg"))
    return fp_svc.frame_views(fp_svc.hash_frames(paths))


def main() -> int:
    seized = SEED / "WhatsApp_Video_2026-08-17_forwarded.mp4"
    if not seized.exists():
        print("Run `python seed.py` first — no demonstration media on disk.")
        return 1

    q = views_for(seized, "query")
    print(f"query: {seized.name}  ({len(q)} frames, {len(fp_svc.VIEWS)} views each)")
    print(f"configured rule: distance <= {fp_svc.MATCH_THRESHOLD} bits AND "
          f">= {fp_svc.MIN_CORROBORATING_FRAMES} corroborating frames\n")

    hdr = f"  {'target':<24}{'min bits':>9}{'corroborating':>15}{'qualifies':>11}"
    true_d: list[tuple[int, int]] = []
    controls: list[tuple[int, int]] = []

    print("TRUE DERIVATIVES (same source, different transformations)")
    print(hdr)
    for p in sorted(Path(CORPUS_DIR).glob("*.mp4")):
        m = fp_svc.best_match_views(q, views_for(p, f"corpus_{p.stem}"))
        true_d.append((m["hamming"], m["matched_frames"]))
        corr = f"{m['matched_frames']}/{m['total_frames']}"
        print(f"  {p.stem:<24}{m['hamming']:>9}{corr:>15}"
              f"{('yes' if fp_svc.qualifies(m) else 'NO'):>11}")

    print("\nUNRELATED CONTROLS (different content entirely)")
    print(hdr)
    for name, p in build_controls().items():
        m = fp_svc.best_match_views(q, views_for(p, name))
        controls.append((m["hamming"], m["matched_frames"]))
        corr = f"{m['matched_frames']}/{m['total_frames']}"
        print(f"  {name:<24}{m['hamming']:>9}{corr:>15}"
              f"{('LEAKED' if fp_svc.qualifies(m) else 'no'):>11}")

    if not true_d or not controls:
        print("\nNot enough samples to calibrate.")
        return 1

    t_bits = [b for b, _ in true_d]; c_bits = [b for b, _ in controls]
    t_corr = [c for _, c in true_d];  c_corr = [c for _, c in controls]

    print(f"\ntrue derivatives : {min(t_bits)}–{max(t_bits)} bits, "
          f"{min(t_corr)}–{max(t_corr)} corroborating frames   (n={len(true_d)})")
    print(f"unrelated        : {min(c_bits)}–{max(c_bits)} bits, "
          f"{min(c_corr)}–{max(c_corr)} corroborating frames   (n={len(controls)})")

    failures = 0

    # 1. every true derivative must be accepted
    missed = [i for i, (b, c) in enumerate(true_d)
              if not fp_svc.qualifies({"hamming": b, "matched_frames": c})]
    if missed:
        print(f"\nFAIL: {len(missed)} true derivative(s) would NOT be matched by the "
              f"configured rule — the threshold is too strict.")
        failures += 1
    else:
        print("\nOK: every true derivative is accepted by the configured rule.")

    # 2. no control may be accepted
    leaked = [i for i, (b, c) in enumerate(controls)
              if fp_svc.qualifies({"hamming": b, "matched_frames": c})]
    if leaked:
        print(f"FAIL: {len(leaked)} unrelated control(s) would be reported as a MATCH — "
              f"the rule admits false positives.")
        failures += 1
    else:
        print("OK: no unrelated control is accepted by the configured rule.")

    # 3. report the margin actually available
    if max(t_corr) < min(c_corr):
        print("FAIL: corroboration does not separate the populations.")
        failures += 1
    else:
        print(f"OK: corroboration separates the populations — true derivatives reach "
              f"{min(t_corr)}+ frames, controls at most {max(c_corr)}.")
        print(f"    distance margin: true derivatives <= {max(t_bits)} bits, "
              f"controls >= {min(c_bits)} bits.")

    if failures:
        print("\nRE-CALIBRATION REQUIRED. SROT must not report matches on this "
              "material with the current settings.")
        return 2
    print("\nConfigured matching rule validated against both populations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
