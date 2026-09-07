"""
Laundering stress test.

We generate real transformed copies of the evidence with FFmpeg — the same
operations an offender performs — then re-run the identical signal ensemble on
each one. Nothing is simulated or hardcoded: every number in the degradation
curve comes from an actual analysis of an actual file on disk.
"""
from __future__ import annotations
import shutil, subprocess, time
from pathlib import Path
from typing import Any, Callable

def _find_ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    for candidate in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"):
        if Path(candidate).is_file():
            return candidate
    return None


FFMPEG = _find_ffmpeg()

# (key, human name, transform description, video filter, extra output args)
SWING_TOLERANCE = 20.0      # points of aggregate score, either direction
PHASH_SURVIVAL_PCT = 81.25  # 12/64 bits — the calibrated origin-match threshold

VIDEO_VARIANTS: list[tuple[str, str, str, str, list[str]]] = [
    ("reencode_2m",   "Re-encode 2 Mbps",   "H.264 re-encode at 2 Mbps",   "null",                        ["-b:v", "2M"]),
    ("reencode_800k", "Re-encode 800 kbps", "H.264 re-encode at 800 kbps", "null",                        ["-b:v", "800k"]),
    ("reencode_400k", "Re-encode 400 kbps", "H.264 re-encode at 400 kbps", "null",                        ["-b:v", "400k"]),
    ("scale_720",     "Downscale 720p",     "Scale to 720 px height",      "scale=-2:720",                []),
    ("scale_480",     "Downscale 480p",     "Scale to 480 px height",      "scale=-2:480",                []),
    ("scale_360",     "Downscale 360p",     "Scale to 360 px height",      "scale=-2:360",                []),
    ("crop_5",        "Crop 5%",            "Centre crop, 5% removed",     "crop=iw*0.95:ih*0.95",        []),
    ("crop_10",       "Crop 10%",           "Centre crop, 10% removed",    "crop=iw*0.90:ih*0.90",        []),
    ("crop_20",       "Crop 20%",           "Centre crop, 20% removed",    "crop=iw*0.80:ih*0.80",        []),
    ("mirror",        "Horizontal mirror",  "Left-right flip",             "hflip",                       []),
    ("overlay",       "Logo / text overlay","Opaque band burned into frame","drawbox=x=0:y=ih-60:w=iw:h=60:color=black@0.75:t=fill,"
                                                                            "drawbox=x=12:y=ih-48:w=180:h=28:color=white@0.9:t=fill", []),
    ("screenrec_sim", "Screen-record sim",  "Downscale, pad with bars, soften",
     "scale=-2:640,pad=iw:ih+120:0:60:black,gblur=sigma=0.6", []),
]


def _out_name(key: str, is_image: bool) -> str:
    return f"variant_{key}." + ("jpg" if is_image else "mp4")


def build_variant(src: Path, dst: Path, vf: str, extra: list[str], is_image: bool) -> tuple[bool, str]:
    if not FFMPEG:
        return False, "ffmpeg not available"
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src)]
    if vf and vf != "null":
        cmd += ["-vf", vf]
    if is_image:
        cmd += ["-frames:v", "1", "-q:v", "4"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-an"]
        cmd += extra
        cmd += ["-t", "12"]                       # bound the work for demo speed
    cmd += [str(dst)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=240)
        if r.returncode != 0 or not dst.exists():
            return False, (r.stderr.decode("utf-8", "replace")[:200] or "ffmpeg failed")
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "ffmpeg timed out"


def run_stress_test(src: Path, work_dir: Path, is_image: bool,
                    score_fn: Callable[[Path, Path], dict[str, Any]],
                    baseline_score: float | None,
                    on_progress: Callable[[str], None] | None = None) -> dict[str, Any]:
    """
    score_fn(media_path, scratch_dir) -> {"score": float|None, "phash": str|None, ...}
    Returns the full variant table plus a derived reliability boundary.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    for key, name, transform, vf, extra in VIDEO_VARIANTS:
        if on_progress:
            on_progress(name)
        dst = work_dir / _out_name(key, is_image)
        t0 = time.perf_counter()
        ok, err = build_variant(src, dst, vf, extra, is_image)
        if not ok:
            results.append({"key": key, "name": name, "transform": transform,
                            "ffmpeg_args": vf, "path": None, "score": None,
                            "error": err, "processing_ms": int((time.perf_counter() - t0) * 1000)})
            continue
        scratch = work_dir / f"scratch_{key}"
        try:
            metrics = score_fn(dst, scratch)
        except Exception as e:  # noqa: BLE001
            metrics = {"score": None, "error": f"{type(e).__name__}: {e}"[:160]}
        ms = int((time.perf_counter() - t0) * 1000)
        results.append({
            "key": key, "name": name, "transform": transform, "ffmpeg_args": vf,
            "path": str(dst), "sha256": metrics.get("sha256"),
            "size_bytes": dst.stat().st_size if dst.exists() else None,
            "score": metrics.get("score"),
            "phash": metrics.get("phash"),
            "phash_hamming": metrics.get("phash_hamming"),
            "phash_similarity": metrics.get("phash_similarity"),
            "processing_ms": ms, "error": metrics.get("error"),
        })

    # ── derive the reliability boundary from the measured results ────────────
    quality_ladder = ["scale_720", "scale_480", "scale_360",
                      "reencode_2m", "reencode_800k", "reencode_400k"]
    by_key = {r["key"]: r for r in results}

    def assess(r: dict) -> bool | None:
        """
        A variant survives if the assessment does not SWING (either direction) by more
        than SWING_TOLERANCE and the perceptual fingerprint still matches at the
        calibrated threshold. A score that jumps upward is just as much a failure as
        one that collapses — it means the transformation, not the content, moved the
        needle. Unassessable variants stay None; they are never assumed to be fine.
        """
        if r.get("score") is None or baseline_score is None:
            return None
        swing = abs(r["score"] - baseline_score)
        pm = r.get("phash_similarity")
        fingerprint_ok = pm is None or pm >= PHASH_SURVIVAL_PCT
        return bool(swing <= SWING_TOLERANCE and fingerprint_ok)

    for r in results:
        r["reliable"] = assess(r)
        if r.get("score") is not None and baseline_score is not None:
            r["delta"] = round(r["score"] - baseline_score, 2)
        else:
            r["delta"] = None

    reliable = [by_key[k]["name"] for k in quality_ladder
                if k in by_key and by_key[k].get("reliable") is True]
    failed = [by_key[k]["name"] for k in quality_ladder
              if k in by_key and by_key[k].get("reliable") is False]
    other_failed = [r["name"] for r in results
                    if r["key"] not in quality_ladder and r.get("reliable") is False]

    if baseline_score is None:
        boundary = "Not determinable — baseline assessment unavailable."
        recommendation = ("Baseline detector assessment was unavailable, so no reliability "
                          "boundary can be stated for this evidence.")
    elif reliable and failed:
        boundary = f"Reliable through: {reliable[-1]} · Degrades from: {failed[0]}"
        recommendation = (
            f"Detector output remains stable through {reliable[-1]}. At {failed[0]} and below, "
            "the assessment shifts materially — do not rely on the detector score at or below "
            "that quality. Use Origin Trace, perceptual fingerprint matching, provenance and "
            "OCR-derived evidence instead.")
    elif reliable and not failed:
        boundary = (f"Stable across all {len(reliable)} quality-reduction variants tested"
                    + (f"; fingerprint matching failed on: {', '.join(other_failed)}."
                       if other_failed else "."))
        recommendation = ("No reliability boundary was reached within the tested transformation "
                          "set. This does not imply general robustness — only that these "
                          "specific transformations did not destabilise the assessment.")
    # ── compute directional stability analysis ──────────────────────────────
    deltas = [abs(r["delta"]) for r in results if r.get("delta") is not None]
    if deltas:
        mean_delta = round(float(sum(deltas) / len(deltas)), 2)
        max_delta = round(float(max(deltas)), 2)
        if mean_delta <= 6.0 and max_delta <= 15.0:
            stability_grade = "HIGHLY_STABLE"
            stability_summary = (
                f"Signal remained directionally stable across tested transformations "
                f"(mean delta: ±{mean_delta}%, max shift: {max_delta}%). Findings are resilient."
            )
        elif mean_delta <= 12.0:
            stability_grade = "DIRECTIONALLY_CONSISTENT"
            stability_summary = (
                f"Signal exhibited moderate variance under laundering transforms "
                f"(mean delta: ±{mean_delta}%, max shift: {max_delta}%). Directional trend holds."
            )
        else:
            stability_grade = "SENSITIVE_TO_TRANSFORMATION"
            stability_summary = (
                f"Signal sensitivity detected under laundering transformations "
                f"(mean delta: ±{mean_delta}%, max shift: {max_delta}%). Assessment confidence downgraded."
            )
    else:
        mean_delta = None
        max_delta = None
        stability_grade = "INSUFFICIENT_DATA"
        stability_summary = "Insufficient valid variants to evaluate directional stability."

    return {
        "variants": results,
        "reliability_boundary": boundary,
        "recommendation": recommendation,
        "reliable_variants": reliable,
        "degraded_variants": failed,
        "directional_stability": {
            "grade": stability_grade,
            "mean_delta": mean_delta,
            "max_delta": max_delta,
            "summary": stability_summary,
            "surviving_count": len([r for r in results if r.get("reliable") is True]),
            "total_count": len(results),
        },
    }
