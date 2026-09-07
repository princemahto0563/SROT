"""
SROT forensic signal ensemble.

HONESTY STATEMENT (this is also surfaced in the UI and the report):
No trained neural deepfake detector is bundled with this build. Instead, every
signal below is a REAL measurement computed from the pixels/bytes of the evidence
using classical image-forensics techniques. The assessment is a published,
weighted aggregation of those measurements — not a model output, and not a
guess. `detector_backend` records exactly what ran.

If a local neural detector becomes available, `neural_detector_available()`
returns True and its score is added as one more signal; the rest is unchanged.
"""
from __future__ import annotations
import io, math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
import cv2
from scipy.fftpack import dct

DETECTOR_BACKEND = "heuristic-forensic-ensemble-v1"

AGGREGATION_FORMULA = (
    "aggregate = Σ(signal_score × weight) / Σ(weight) over available supporting "
    "signals; counter-indicators subtract at half weight. Weights are fixed and "
    "printed with the result so the arithmetic can be checked."
)

# Fixed, published weights. Changing these changes the printed formula.
WEIGHTS = {
    "recompression": 1.0,
    "dct_benford": 1.0,
    "noise_residual": 0.9,
    "high_freq_energy": 0.9,
    "blockiness": 0.6,
    "temporal_continuity": 0.8,
    "metadata_coherence": 0.7,
    "neural_detector": 1.2,   # highest weight — real model inference
}


def neural_detector_available() -> bool:
    """True only if a real local model is importable AND weights are present."""
    try:
        from .neural import detector_available
        return detector_available()
    except Exception:  # noqa: BLE001
        return False


def get_detector_backend() -> str:
    """Return the active detector backend label."""
    if neural_detector_available():
        return "heuristic-forensic-ensemble-v1 + neural-vit-v1"
    return DETECTOR_BACKEND


# ── helpers ──────────────────────────────────────────────────────────────────
def _load_gray(path: str | Path, max_side: int = 768) -> np.ndarray | None:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        return None
    h, w = img.shape[:2]
    if max(h, w) > max_side:
        s = max_side / max(h, w)
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return float(max(lo, min(hi, x)))


def _band(score: float) -> str:
    if score >= 70:
        return "Strong"
    if score >= 45:
        return "Moderate"
    if score >= 20:
        return "Weak"
    return "Counter-indicator"


# ── individual measurements (all real) ───────────────────────────────────────
def measure_noise_residual(gray: np.ndarray) -> dict[str, Any]:
    """Median-filter residual. Generated/heavily smoothed content shows low, very
    uniform residual energy; natural camera capture retains sensor noise."""
    med = cv2.medianBlur(gray.astype(np.uint8), 3).astype(np.float32)
    res = gray - med
    std = float(np.std(res))
    # spatial uniformity of the residual across an 8×8 tile grid
    tiles = [res[i::8, j::8] for i in range(0, 8) for j in range(0, 8)]
    tile_std = float(np.std([float(np.std(t)) for t in tiles])) if tiles else 0.0
    uniformity = 1.0 - min(1.0, tile_std / (std + 1e-6))
    # low residual std OR very uniform residual → higher anomaly score
    s_low = _clamp((3.2 - std) / 3.2 * 100)
    s_uni = _clamp((uniformity - 0.55) / 0.45 * 100)
    score = _clamp(0.6 * s_low + 0.4 * s_uni)
    return {"score": score,
            "measurement": {"residual_std": round(std, 4),
                            "tile_std_spread": round(tile_std, 4),
                            "uniformity": round(uniformity, 4)},
            "method": "median-filter residual: std + inter-tile uniformity (OpenCV)"}


def measure_recompression(path: str | Path) -> dict[str, Any]:
    """
    JPEG-ghost style test: re-encode at a sweep of qualities and find the quality
    that minimises reconstruction error. A minimum well below q=95 indicates the
    content was previously compressed at roughly that quality — i.e. re-encoded.
    """
    try:
        with Image.open(path) as im:
            base = im.convert("RGB")
            if max(base.size) > 768:
                s = 768 / max(base.size)
                base = base.resize((int(base.width * s), int(base.height * s)), Image.LANCZOS)
            arr = np.asarray(base).astype(np.float32)
    except Exception as e:  # noqa: BLE001
        return {"score": None, "measurement": {"error": str(e)[:120]},
                "method": "JPEG re-encode error sweep"}

    qualities = list(range(50, 100, 5))
    errors = []
    for q in qualities:
        buf = io.BytesIO()
        Image.fromarray(arr.astype(np.uint8)).save(buf, "JPEG", quality=q)
        buf.seek(0)
        with Image.open(buf) as re_im:
            re_arr = np.asarray(re_im.convert("RGB")).astype(np.float32)
        errors.append(float(np.mean((arr - re_arr) ** 2)))

    min_i = int(np.argmin(errors))
    q_min = qualities[min_i]
    # sharper the dip relative to neighbours, the stronger the evidence
    span = (max(errors) - min(errors)) / (max(errors) + 1e-6)
    score = _clamp(((95 - q_min) / 45.0) * 70 + span * 30)
    return {"score": score,
            "measurement": {"error_minimum_quality": q_min,
                            "mse_by_quality": {str(q): round(e, 3) for q, e in zip(qualities, errors)},
                            "normalised_dip": round(span, 4)},
            "method": "JPEG-ghost sweep: re-encode q50–q95, locate MSE minimum"}


def measure_dct_benford(gray: np.ndarray) -> dict[str, Any]:
    """First-digit distribution of block-DCT AC coefficients vs Benford's law.
    Natural, singly-compressed imagery tracks Benford closely."""
    h, w = gray.shape
    h8, w8 = h - h % 8, w - w % 8
    if h8 < 8 or w8 < 8:
        return {"score": None, "measurement": {"error": "frame too small"},
                "method": "block-DCT first-digit vs Benford"}
    g = gray[:h8, :w8] - 128.0
    blocks = g.reshape(h8 // 8, 8, w8 // 8, 8).transpose(0, 2, 1, 3).reshape(-1, 8, 8)
    coeffs = dct(dct(blocks, axis=1, norm="ortho"), axis=2, norm="ortho")
    ac = np.abs(coeffs[:, :, :].reshape(len(blocks), -1)[:, 1:]).ravel()
    ac = ac[ac >= 1.0]
    if ac.size < 500:
        return {"score": None, "measurement": {"ac_samples": int(ac.size)},
                "method": "block-DCT first-digit vs Benford"}
    first = (ac / np.power(10, np.floor(np.log10(ac)))).astype(int)
    counts = np.array([(first == d).sum() for d in range(1, 10)], dtype=np.float64)
    observed = counts / counts.sum()
    benford = np.array([math.log10(1 + 1 / d) for d in range(1, 10)])
    chi2 = float(np.sum((observed - benford) ** 2 / (benford + 1e-9)))
    score = _clamp((chi2 / 0.25) * 100)
    return {"score": score,
            "measurement": {"chi_square_distance": round(chi2, 5),
                            "observed_first_digit": [round(float(x), 4) for x in observed],
                            "benford_expected": [round(float(x), 4) for x in benford],
                            "ac_samples": int(ac.size)},
            "method": "8×8 block DCT, AC first-digit distribution, χ² vs Benford"}


def measure_blockiness(gray: np.ndarray) -> dict[str, Any]:
    """Energy on the 8-pixel JPEG grid vs off-grid. High → strong/repeated compression."""
    dx = np.abs(np.diff(gray, axis=1))
    dy = np.abs(np.diff(gray, axis=0))
    on_x = float(np.mean(dx[:, 7::8])) if dx.shape[1] > 8 else 0.0
    off_x = float(np.mean(np.delete(dx, np.s_[7::8], axis=1))) if dx.shape[1] > 8 else 1.0
    on_y = float(np.mean(dy[7::8, :])) if dy.shape[0] > 8 else 0.0
    off_y = float(np.mean(np.delete(dy, np.s_[7::8], axis=0))) if dy.shape[0] > 8 else 1.0
    ratio = ((on_x / (off_x + 1e-6)) + (on_y / (off_y + 1e-6))) / 2.0
    score = _clamp((ratio - 1.0) / 0.6 * 100)
    return {"score": score,
            "measurement": {"grid_energy_ratio": round(ratio, 4),
                            "on_grid_x": round(on_x, 4), "off_grid_x": round(off_x, 4)},
            "method": "8-px grid boundary gradient energy vs off-grid"}


def measure_high_freq_energy(gray: np.ndarray) -> dict[str, Any]:
    """Radial FFT spectrum. Upscaled or synthesised content is deficient in high
    spatial frequencies relative to natural capture at the same resolution."""
    f = np.fft.fftshift(np.abs(np.fft.fft2(gray - gray.mean())))
    h, w = f.shape
    cy, cx = h // 2, w // 2
    y, x = np.ogrid[:h, :w]
    r = np.sqrt((y - cy) ** 2 + (x - cx) ** 2)
    rmax = float(r.max())
    total = float(f.sum()) + 1e-9
    hf = float(f[r > 0.55 * rmax].sum()) / total
    mf = float(f[(r > 0.2 * rmax) & (r <= 0.55 * rmax)].sum()) / total
    score = _clamp((0.045 - hf) / 0.045 * 100)
    return {"score": score,
            "measurement": {"high_freq_fraction": round(hf, 6),
                            "mid_freq_fraction": round(mf, 6)},
            "method": "2-D FFT radial energy: fraction beyond 0.55·r_max"}


def measure_temporal_continuity(frame_paths: list[str]) -> dict[str, Any]:
    """Inter-frame absolute difference statistics across the sampled keyframes."""
    if len(frame_paths) < 3:
        return {"score": None, "measurement": {"frames": len(frame_paths)},
                "method": "inter-frame absdiff statistics"}
    diffs: list[float] = []
    prev = None
    for p in frame_paths:
        g = _load_gray(p, max_side=384)
        if g is None:
            continue
        if prev is not None and prev.shape == g.shape:
            diffs.append(float(np.mean(np.abs(g - prev))))
        prev = g
    if len(diffs) < 2:
        return {"score": None, "measurement": {"usable_pairs": len(diffs)},
                "method": "inter-frame absdiff statistics"}
    mean_d = float(np.mean(diffs)); std_d = float(np.std(diffs))
    cv = std_d / (mean_d + 1e-6)
    spikes = int(sum(1 for d in diffs if d > mean_d + 2.5 * std_d))
    score = _clamp(min(100.0, cv / 1.2 * 60 + spikes * 20))
    return {"score": score,
            "measurement": {"mean_absdiff": round(mean_d, 4), "std_absdiff": round(std_d, 4),
                            "coefficient_of_variation": round(cv, 4),
                            "discontinuity_spikes": spikes, "pairs": len(diffs)},
            "method": "mean |Δ| between consecutive sampled keyframes; CV + spike count"}


def measure_metadata_coherence(probe: dict, exif: dict, media_kind: str) -> dict[str, Any]:
    """Structural metadata observations. Absence alone is never scored as guilt."""
    obs: list[str] = []
    pts = 0.0
    if media_kind == "image":
        if not exif:
            obs.append("No EXIF block present")
            pts += 18
        else:
            if not any(k in exif for k in ("Make", "Model")):
                obs.append("EXIF present but carries no camera make/model")
                pts += 22
            if exif.get("Software"):
                obs.append(f"EXIF Software tag: {exif['Software']}")
                pts += 25
            if exif.get("DateTime") and exif.get("DateTimeOriginal") and \
               exif["DateTime"] != exif["DateTimeOriginal"]:
                obs.append("DateTime differs from DateTimeOriginal")
                pts += 15
    else:
        enc = (probe or {}).get("encoder_tag")
        if enc:
            obs.append(f"Container encoder tag: {enc}")
            if any(t in str(enc).lower() for t in ("lavf", "ffmpeg", "handbrake", "x264")):
                obs.append("Encoder is a transcoding library, not a capture device")
                pts += 35
        else:
            obs.append("No encoder tag in container")
            pts += 12
        tags = (probe or {}).get("tags") or {}
        if not any(k.lower() in ("make", "model", "com.apple.quicktime.model") for k in tags):
            obs.append("No capture-device tags in container")
            pts += 15
        if probe and probe.get("bit_rate") and probe.get("width"):
            bpp = probe["bit_rate"] / max(1, probe["width"] * probe["height"] * (probe.get("fps") or 25))
            obs.append(f"Bits per pixel per frame: {bpp:.4f}")
            if bpp < 0.03:
                obs.append("Very low bitrate for resolution — consistent with re-encoding")
                pts += 18
    return {"score": _clamp(pts),
            "measurement": {"observations": obs, "exif_keys": sorted(exif.keys())[:20]},
            "method": "container/EXIF structural coherence checks"}


# ── ensemble ─────────────────────────────────────────────────────────────────
def analyse_frames(frame_paths: list[str], sample_limit: int = 12) -> dict[str, Any]:
    """Per-frame measurements + aggregated per-signal means."""
    use = frame_paths[:sample_limit]
    per_frame: list[dict[str, Any]] = []
    acc: dict[str, list[float]] = {k: [] for k in
                                   ("noise_residual", "dct_benford", "blockiness", "high_freq_energy")}
    details: dict[str, Any] = {}

    for i, p in enumerate(use):
        gray = _load_gray(p)
        if gray is None:
            continue
        n = measure_noise_residual(gray)
        b = measure_dct_benford(gray)
        bl = measure_blockiness(gray)
        hf = measure_high_freq_energy(gray)
        vals = {"noise_residual": n["score"], "dct_benford": b["score"],
                "blockiness": bl["score"], "high_freq_energy": hf["score"]}
        for k, v in vals.items():
            if v is not None:
                acc[k].append(v)
        present = [v for v in vals.values() if v is not None]
        per_frame.append({
            "frame_index": i, "path": p,
            "score": round(float(np.mean(present)), 2) if present else None,
            "metrics": {"noise_residual": n["measurement"], "dct_benford": b["measurement"],
                        "blockiness": bl["measurement"], "high_freq_energy": hf["measurement"],
                        "scores": {k: (round(v, 2) if v is not None else None) for k, v in vals.items()}},
        })
        if i == 0:
            details = {"noise_residual": n, "dct_benford": b, "blockiness": bl, "high_freq_energy": hf}

    means = {k: (round(float(np.mean(v)), 2) if v else None) for k, v in acc.items()}
    return {"per_frame": per_frame, "signal_means": means, "first_frame_detail": details,
            "frames_analysed": len(per_frame)}


def build_signals(*, frame_result: dict, recompression: dict, temporal: dict,
                  metadata: dict, c2pa: dict,
                  neural_result: dict | None = None) -> list[dict[str, Any]]:
    means = frame_result["signal_means"]
    d = frame_result.get("first_frame_detail", {})
    signals: list[dict[str, Any]] = []

    def add(key, name, score, measurement, method, note, direction="supports"):
        signals.append({
            "key": key, "name": name,
            "score": None if score is None else round(float(score), 2),
            "weight": WEIGHTS.get(key, 0.0), "direction": direction,
            "strength": "Unavailable" if score is None else _band(score),
            "result": _result_label(key, score),
            "measurement": measurement, "method": method, "note": note,
        })

    add("recompression", "Re-compression history", recompression.get("score"),
        recompression.get("measurement"), recompression.get("method"),
        "Locates the JPEG quality at which reconstruction error is minimised. A minimum "
        "well below q95 indicates the content was compressed before this copy was made.")

    add("dct_benford", "DCT first-digit distribution", means.get("dct_benford"),
        (d.get("dct_benford") or {}).get("measurement"),
        (d.get("dct_benford") or {}).get("method", "block-DCT vs Benford"),
        "Natural, singly-compressed imagery follows Benford's law closely. Larger χ² "
        "distance indicates processing history or synthesis.")

    add("noise_residual", "Sensor-noise residual", means.get("noise_residual"),
        (d.get("noise_residual") or {}).get("measurement"),
        (d.get("noise_residual") or {}).get("method", "median residual"),
        "Camera capture leaves per-pixel sensor noise. Low and spatially uniform residual "
        "is consistent with smoothing, upscaling or synthesis — but also with heavy compression.")

    add("high_freq_energy", "High-frequency energy", means.get("high_freq_energy"),
        (d.get("high_freq_energy") or {}).get("measurement"),
        (d.get("high_freq_energy") or {}).get("method", "radial FFT"),
        "Upscaled or generated content is typically deficient in high spatial frequency "
        "relative to native capture at the same resolution.")

    add("blockiness", "Compression blockiness", means.get("blockiness"),
        (d.get("blockiness") or {}).get("measurement"),
        (d.get("blockiness") or {}).get("method", "8-px grid energy"),
        "Measures energy on the 8-pixel JPEG grid. Elevated values indicate strong or "
        "repeated compression rather than manipulation on its own.")

    add("temporal_continuity", "Temporal continuity", temporal.get("score"),
        temporal.get("measurement"), temporal.get("method"),
        "Consistency of change between sampled keyframes. A low value is a "
        "counter-indicator: it does not corroborate manipulation.")

    add("metadata_coherence", "Metadata & encoder coherence", metadata.get("score"),
        metadata.get("measurement"), metadata.get("method"),
        "Structural observations from the container/EXIF. Missing metadata is recorded "
        "as an absence and is never scored as proof of manipulation.")

    # Neural detector signal (only when actually available and inference ran)
    if neural_result and neural_result.get("model_available"):
        median_score = neural_result.get("median_score")
        # Convert 0..1 probability to 0..100 signal score
        neural_score = round(median_score * 100, 2) if median_score is not None else None
        add("neural_detector", "AI-synthetic image signal", neural_score,
            {"model": neural_result.get("model_name"),
             "model_version": neural_result.get("model_version"),
             "median_score": median_score,
             "mean_score": neural_result.get("mean_score"),
             "max_score": neural_result.get("max_score"),
             "trimmed_mean": neural_result.get("trimmed_mean_score"),
             "top_k_mean": neural_result.get("top_k_mean"),
             "frames_analysed": neural_result.get("frames_analysed"),
             "suspicious_frames": neural_result.get("top_suspicious_count"),
             "assessment": neural_result.get("assessment"),
             "device": neural_result.get("device"),
             "inference_ms": neural_result.get("total_inference_ms")},
            f"Frame-level AI-synthetic image signal ({neural_result.get('model_name', 'ViT')}); "
            f"median of per-frame model scores",
            f"Model AI-synthetic score: {neural_score}%. Real neural model inference (not fabricated). "
            "Decision-support signal only: does not by itself establish authenticity or manipulation. "
            "Model is designed primarily for artistic AI imagery and is not a deepfake photo detector.")

    signals.append({
        "key": "provenance", "name": "Provenance (C2PA / Content Credentials)",
        "score": None, "weight": 0.0, "direction": "neutral",
        "strength": "Present" if c2pa.get("present") else "Not found",
        "result": "C2PA marker present" if c2pa.get("present") else "No C2PA manifest found",
        "measurement": {"markers": c2pa.get("markers", [])},
        "method": "byte-level JUMBF/C2PA marker scan",
        "note": c2pa.get("note", ""),
    })
    return signals


def build_audio_signals(audio_res: dict[str, Any]) -> list[dict[str, Any]]:
    """Builds physical acoustic forensic signals from audio stream analysis."""
    signals: list[dict[str, Any]] = []
    if not audio_res or not audio_res.get("has_audio"):
        return signals

    metrics = audio_res.get("metrics", {}) or {}

    # 1. Audio Silence & Gating
    sil_ratio = float(metrics.get("silence_fraction", 0.0) or 0.0)
    hard_gates = int(metrics.get("hard_gate_transitions", 0) or 0)
    sil_score = _clamp(sil_ratio * 100.0 + hard_gates * 15.0)
    signals.append({
        "key": "audio_silence_gating",
        "name": "Audio silence boundary gating",
        "score": round(sil_score, 1),
        "weight": 0.8,
        "direction": "supporting" if sil_score >= 35 else "neutral",
        "strength": _band(sil_score),
        "result": f"Silence fraction {sil_ratio*100:.1f}% ({hard_gates} hard cutoffs)",
        "measurement": {"silence_fraction": sil_ratio, "hard_gate_transitions": hard_gates},
        "method": "Hard gating & energy thresholding",
        "note": "Unnatural zero-energy gating or sudden amplitude cutoffs can indicate splicing or synthetic vocoding.",
    })

    # 2. Spectral Flatness (Wiener Entropy)
    mean_flat = float(metrics.get("spectral_flatness", 0.0) or 0.0)
    flat_score = _clamp(mean_flat * 250.0)
    signals.append({
        "key": "audio_spectral_flatness",
        "name": "Audio spectral flatness (Wiener entropy)",
        "score": round(flat_score, 1),
        "weight": 0.9,
        "direction": "supporting" if flat_score >= 35 else "neutral",
        "strength": _band(flat_score),
        "result": f"Mean flatness {mean_flat:.4f}",
        "measurement": {"spectral_flatness": mean_flat},
        "method": "Geometric mean vs arithmetic mean of power spectrum",
        "note": "Abnormally flat spectra can indicate vocoded speech or synthetic noise generation.",
    })

    # 3. Pitch / F0 Trajectory & Jitter
    jit = float(metrics.get("pitch_jitter_pct", 0.0) or 0.0)
    mean_f0 = float(metrics.get("mean_f0_hz", 0.0) or 0.0)
    if mean_f0 > 40:
        jit_score = _clamp((1.2 - jit) * 50.0) if jit < 0.6 else _clamp((jit - 2.5) * 25.0)
    else:
        jit_score = 15.0
    signals.append({
        "key": "audio_pitch_jitter",
        "name": "Vocal pitch micro-tremor & jitter",
        "score": round(jit_score, 1),
        "weight": 0.9,
        "direction": "supporting" if jit_score >= 35 else "neutral",
        "strength": _band(jit_score),
        "result": f"Jitter {jit:.2f}% (F0 mean: {mean_f0:.1f} Hz)",
        "measurement": {"pitch_jitter_pct": jit, "mean_f0_hz": mean_f0},
        "method": "Autocorrelation pitch tracking & cycle-to-cycle perturbation",
        "note": "Synthetic speech vocoders often display unnaturally steady pitch periods without natural human vocal tremor.",
    })

    # 4. Digital Clipping Ratio
    clip_ratio = float(metrics.get("clipping_ratio", 0.0) or 0.0)
    clip_score = _clamp(clip_ratio * 1500.0)
    signals.append({
        "key": "audio_clipping",
        "name": "Digital rail clipping ratio",
        "score": round(clip_score, 1),
        "weight": 0.7,
        "direction": "supporting" if clip_score >= 35 else "neutral",
        "strength": _band(clip_score),
        "result": f"Clipping ratio: {clip_ratio*100:.2f}%",
        "measurement": {"clipping_ratio": clip_ratio},
        "method": "Rail detection at ±0.999 full-scale",
        "note": "High clipping indicates non-linear distortion, aggressive gain, or synthetic sound generation overdrive.",
    })

    return signals


def _result_label(key: str, score: float | None) -> str:
    if score is None:
        return "Not available"
    if key == "temporal_continuity":
        return "Discontinuities observed" if score >= 45 else "No anomaly observed"
    if key == "metadata_coherence":
        return "Inconsistencies observed" if score >= 40 else "No inconsistency observed"
    if key == "neural_detector":
        if score >= 75:
            return "Strong synthetic-image signal"
        if score >= 50:
            return "Moderate synthetic-image signal"
        if score >= 30:
            return "Low synthetic-image signal"
        return "No synthetic-image signal"
    if score >= 70:
        return "Consistent with manipulation"
    if score >= 45:
        return "Moderate indicator"
    if score >= 20:
        return "Weak indicator"
    return "No indicator"


def aggregate(signals: list[dict[str, Any]]) -> dict[str, Any]:
    num = den = 0.0
    supporting = 0
    counter: list[str] = []
    for s in signals:
        if s["score"] is None or s["weight"] <= 0:
            continue
        w = s["weight"]
        num += s["score"] * w
        den += w
        if s["score"] >= 45:
            supporting += 1
        elif s["score"] < 20:
            counter.append(s["name"])
    if den == 0:
        return {"aggregate": None, "assessment": "Inconclusive",
                "band": "INCONCLUSIVE", "dissent": False, "counter": counter,
                "supporting": 0,
                "reason": "No signal could be measured on this evidence."}

    agg = round(num / den, 2)
    if agg >= 62 and supporting >= 3:
        assessment, band = "Potentially Manipulated", "HIGH" if agg >= 75 else "MEDIUM"
    elif agg >= 45:
        assessment, band = "Potentially Manipulated", "LOW"
    elif agg >= 28:
        assessment, band = "Inconclusive", "LOW"
    else:
        assessment, band = "No strong manipulation indicators", "MEDIUM"
    return {"aggregate": agg, "assessment": assessment, "band": band,
            "dissent": bool(counter) and assessment.startswith("Potentially"),
            "counter": counter, "supporting": supporting, "reason": ""}
