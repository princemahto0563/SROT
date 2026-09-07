"""
SROT Audio Forensic Analysis Engine
====================================

Extracts transparent acoustic and spectral physical indicators from audio streams.

Forensic Rule:
  "SROT measures physical acoustic indicators (spectral flatness, silence gating discontinuities,
   vocal pitch jitter, spectral rolloff, clipping ratio). It does NOT fabricate an uncalibrated
   'AI voice probability'. Terms like 'AI voice detected' are strictly avoided in favor of
   verifiable acoustic observations."
"""

from __future__ import annotations
import math
from pathlib import Path
import subprocess
import tempfile
from typing import Any
import wave

import numpy as np
import scipy.signal


def _find_tool(name: str) -> str:
    import shutil
    found = shutil.which(name)
    if found:
        return found
    for candidate in (f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}", f"/usr/bin/{name}"):
        if Path(candidate).is_file():
            return candidate
    return name


def probe_audio_stream(media_path: str | Path) -> dict[str, Any]:
    """Inspects container for audio stream presence and basic codec parameters."""
    p = Path(media_path)
    if not p.exists():
        return {"available": False, "has_audio": False, "error": "File does not exist"}

    ffprobe_bin = _find_tool("ffprobe")
    cmd = [
        ffprobe_bin, "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels,bit_rate,duration",
        "-of", "json",
        str(p),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        import json
        info = json.loads(res.stdout or "{}")
        streams = info.get("streams", [])
        if not streams:
            return {"available": True, "has_audio": False, "reason": "No audio stream in container"}
        s = streams[0]
        return {
            "available": True,
            "has_audio": True,
            "codec": s.get("codec_name", "unknown"),
            "sample_rate": int(s.get("sample_rate", 0) or 0),
            "channels": int(s.get("channels", 0) or 0),
            "bitrate_kbps": round(float(s.get("bit_rate", 0) or 0) / 1000.0, 1) if s.get("bit_rate") else None,
            "duration_s": round(float(s.get("duration", 0) or 0), 2) if s.get("duration") else None,
        }
    except Exception as e:  # noqa: BLE001
        return {"available": False, "has_audio": False, "error": str(e)}


def extract_mono_pcm(media_path: str | Path, target_sr: int = 16000) -> tuple[np.ndarray | None, int, dict[str, Any]]:
    """Extracts uncompressed 16-bit mono PCM audio from video/audio file."""
    probe = probe_audio_stream(media_path)
    if not probe.get("has_audio"):
        return None, target_sr, probe

    ffmpeg_bin = _find_tool("ffmpeg")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
        tmp_path = Path(tmp.name)
        cmd = [
            ffmpeg_bin, "-y", "-i", str(media_path),
            "-vn", "-acodec", "pcm_s16le",
            "-ar", str(target_sr), "-ac", "1",
            str(tmp_path),
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            with wave.open(str(tmp_path), "rb") as wf:
                n_frames = wf.getnframes()
                raw_bytes = wf.readframes(n_frames)
                samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            return samples, target_sr, probe
        except Exception as e:  # noqa: BLE001
            return None, target_sr, {**probe, "error": f"FFmpeg extraction failed: {type(e).__name__}"}


def analyze_audio_forensics(media_path: str | Path) -> dict[str, Any]:
    """
    Performs multi-dimensional acoustic and spectral forensic analysis.
    
    Acoustic Dimensions:
      1. RMS Energy & Dynamic Range
      2. Zero-Crossing Rate (ZCR)
      3. Silence Intervals & Hard-Gating Discontinuities
      4. Spectral Centroid & Spectral Rolloff (85%)
      5. Spectral Flatness (Wiener Entropy)
      6. Pitch / F0 Trajectory & Jitter
      7. Frame-to-Frame Spectral Flux & Energy Transients
      8. Digital Clipping Ratio
    """
    samples, sr, stream_info = extract_mono_pcm(media_path)
    if samples is None or len(samples) < sr * 0.25:  # Require at least 250ms of audio
        return {
            "has_audio": bool(stream_info.get("has_audio")),
            "status": "INSUFFICIENT_EVIDENCE",
            "assessment": "Insufficient or absent audio track for acoustic analysis.",
            "stream_info": stream_info,
            "metrics": None,
            "waveform_preview": None,
            "indicators": [],
            "forensic_limitations": "Acoustic signals require at least 250ms of continuous decoded audio.",
        }

    duration_s = float(len(samples) / sr)
    
    # 1. RMS Energy & Clipping
    rms = float(np.sqrt(np.mean(samples ** 2)))
    rms_db = round(float(20.0 * math.log10(max(rms, 1e-7))), 2)
    clipping_count = int(np.sum(np.abs(samples) >= 0.995))
    clipping_ratio = round(float(clipping_count / len(samples)), 4)

    # 2. Zero-Crossing Rate
    zcr = float(np.mean(np.abs(np.diff(np.signbit(samples)))))

    # 3. Framing for Short-Time Analysis (25ms window, 10ms hop)
    win_len = int(sr * 0.025)
    hop_len = int(sr * 0.010)
    num_frames = (len(samples) - win_len) // hop_len
    if num_frames < 2:
        num_frames = 2
        
    frame_rms = []
    frame_zcr = []
    frame_centroids = []
    frame_rolloffs = []
    frame_flatness = []
    
    window = np.hanning(win_len)
    freqs = np.fft.rfftfreq(win_len, d=1.0 / sr)

    for i in range(num_frames):
        start = i * hop_len
        f_samples = samples[start:start + win_len] * window
        f_rms = np.sqrt(np.mean(f_samples ** 2))
        frame_rms.append(f_rms)
        frame_zcr.append(np.mean(np.abs(np.diff(np.signbit(f_samples)))))
        
        # FFT Magnitude Spectrum
        fft_mag = np.abs(np.fft.rfft(f_samples))
        total_power = np.sum(fft_mag) + 1e-9
        
        # Spectral Centroid
        centroid = float(np.sum(freqs * fft_mag) / total_power)
        frame_centroids.append(centroid)
        
        # Spectral Rolloff (85% energy)
        cum_power = np.cumsum(fft_mag)
        rolloff_idx = np.searchsorted(cum_power, 0.85 * total_power)
        rolloff = float(freqs[min(rolloff_idx, len(freqs) - 1)])
        frame_rolloffs.append(rolloff)
        
        # Spectral Flatness (Wiener Entropy = geometric_mean / arithmetic_mean)
        p_spec = (fft_mag ** 2) + 1e-12
        geom_m = np.exp(np.mean(np.log(p_spec)))
        arith_m = np.mean(p_spec)
        flatness = float(geom_m / arith_m)
        frame_flatness.append(flatness)

    frame_rms = np.array(frame_rms)
    frame_centroids = np.array(frame_centroids)
    frame_flatness = np.array(frame_flatness)
    
    # 4. Silence Intervals & Hard-Gate Discontinuity
    silence_threshold = 0.005  # -46 dBFS
    is_silent = frame_rms < silence_threshold
    silence_fraction = round(float(np.mean(is_silent)), 3)
    
    # Check for unnatural zero-decay hard silence gates (common in synthetic speech generators)
    rms_diffs = np.abs(np.diff(frame_rms))
    hard_gate_transitions = int(np.sum((is_silent[:-1] != is_silent[1:]) & (rms_diffs > 0.08)))

    # 5. Pitch (F0) & Pitch-Jitter Estimation via Autocorrelation
    f0_estimates = []
    # Pitch range: 60 Hz to 450 Hz
    min_lag = int(sr / 450)
    max_lag = int(sr / 60)
    
    for i in range(num_frames):
        if is_silent[i]:
            continue
        start = i * hop_len
        f_samples = samples[start:start + win_len]
        if np.max(np.abs(f_samples)) < 0.01:
            continue
        corr = scipy.signal.correlate(f_samples, f_samples, mode="full")[len(f_samples) - 1:]
        search_region = corr[min_lag:max_lag]
        if len(search_region) == 0:
            continue
        peak_idx = np.argmax(search_region) + min_lag
        if corr[0] > 0 and (corr[peak_idx] / corr[0]) > 0.35:
            f0 = sr / peak_idx
            f0_estimates.append(f0)

    if len(f0_estimates) >= 5:
        mean_f0 = round(float(np.mean(f0_estimates)), 1)
        std_f0 = round(float(np.std(f0_estimates)), 1)
        # Pitch jitter: cycle-to-cycle relative difference
        f0_diffs = np.abs(np.diff(f0_estimates))
        jitter_pct = round(float(np.mean(f0_diffs) / (mean_f0 + 1e-6) * 100.0), 2)
    else:
        mean_f0, std_f0, jitter_pct = None, None, None

    # 6. Spectral Discontinuity (Flux)
    spec_flux = round(float(np.std(frame_centroids)), 1)
    mean_flatness = round(float(np.mean(frame_flatness)), 4)
    mean_centroid = round(float(np.mean(frame_centroids)), 1)
    mean_rolloff = round(float(np.mean(frame_rolloffs)), 1)

    # 7. Forensic Indicator Rules & Assessment
    indicators = []
    
    if hard_gate_transitions >= 2:
        indicators.append({
            "key": "hard_silence_gating",
            "name": "Abrupt Silence Gating",
            "level": "ELEVATED",
            "observation": f"{hard_gate_transitions} abrupt energy transitions across silence boundaries (unnatural acoustic cutoff).",
            "limitation": "May occur in aggressive noise-gate plugins or aggressive lossy codecs.",
        })
        
    if jitter_pct is not None and jitter_pct < 0.35 and len(f0_estimates) > 20:
        indicators.append({
            "key": "synthetic_pitch_stability",
            "name": "Unnatural Pitch Rigidity",
            "level": "OBSERVED",
            "observation": f"Vocal jitter perturbation is low ({jitter_pct}%), indicating unnaturally rigid pitch contour.",
            "limitation": "Monotone human speakers or autotuned music vocals also exhibit low jitter.",
        })
        
    if mean_flatness > 0.42:
        indicators.append({
            "key": "elevated_spectral_flatness",
            "name": "Elevated Spectral Flatness",
            "level": "ELEVATED",
            "observation": f"Spectral Wiener entropy ({mean_flatness}) is elevated, indicating noise-like harmonic dispersion.",
            "limitation": "High ambient background noise or low-bitrate compression elevates spectral flatness.",
        })
        
    if clipping_ratio > 0.05:
        indicators.append({
            "key": "digital_clipping",
            "name": "Digital Clipping / Overdrive",
            "level": "OBSERVED",
            "observation": f"{clipping_ratio * 100:.1f}% of audio samples hit maximum quantization rail (+0 dBFS).",
            "limitation": "Microphone gain overdrive or improper digital mastering.",
        })

    # Synthesize Overall Assessment
    if len([i for i in indicators if i["level"] == "ELEVATED"]) >= 2:
        overall_status = "ELEVATED"
        assessment = "Multiple acoustic and spectral discontinuity indicators observed in the audio track."
    elif len(indicators) >= 1:
        overall_status = "OBSERVED"
        assessment = "Physical acoustic indicators noted for human forensic review; no conclusive synthetic anomaly."
    else:
        overall_status = "INCONCLUSIVE"
        assessment = "Acoustic spectrum, vocal pitch jitter, and silence decay curves appear within typical natural operational ranges."

    # Waveform preview envelope (downsample to 120 points for UI rendering)
    num_waveform_pts = 120
    chunk_size = max(1, len(samples) // num_waveform_pts)
    waveform_pts = []
    for i in range(num_waveform_pts):
        chunk = samples[i * chunk_size:(i + 1) * chunk_size]
        if len(chunk) > 0:
            waveform_pts.append(round(float(np.max(np.abs(chunk))), 3))
        else:
            waveform_pts.append(0.0)

    return {
        "has_audio": True,
        "status": overall_status,
        "assessment": assessment,
        "stream_info": stream_info,
        "metrics": {
            "duration_s": round(duration_s, 2),
            "rms_dbfs": rms_db,
            "zero_crossing_rate": round(zcr, 4),
            "silence_fraction": silence_fraction,
            "hard_gate_transitions": hard_gate_transitions,
            "mean_f0_hz": mean_f0,
            "pitch_std_hz": std_f0,
            "pitch_jitter_pct": jitter_pct,
            "spectral_centroid_hz": mean_centroid,
            "spectral_rolloff_hz": mean_rolloff,
            "spectral_flatness": mean_flatness,
            "spectral_flux": spec_flux,
            "clipping_ratio": clipping_ratio,
        },
        "waveform_preview": waveform_pts,
        "indicators": indicators,
        "forensic_limitations": "Acoustic measurements provide physical indicators and do NOT constitute an automated legal proof of voice cloning or deepfake synthesis.",
    }
