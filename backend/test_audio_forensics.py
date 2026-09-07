"""
Unit test suite for SROT Audio Forensics Engine
"""

import math
import os
from pathlib import Path
import sys
import tempfile
import wave
import numpy as np

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.audio_forensics import (
    probe_audio_stream,
    analyze_audio_forensics,
)


def create_test_wav(duration_s: float = 1.0, sr: int = 16000, signal_type: str = "tone") -> Path:
    """Creates a temporary test WAV file for unit tests."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    if signal_type == "tone":
        # 440 Hz sine wave
        samples = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    elif signal_type == "hard_gated":
        # Tone with hard silence cuts
        samples = (0.5 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        samples[int(sr * 0.2):int(sr * 0.3)] = 0.0
        samples[int(sr * 0.5):int(sr * 0.6)] = 0.0
        samples[int(sr * 0.8):int(sr * 0.9)] = 0.0
    elif signal_type == "noise":
        # White noise
        samples = np.random.uniform(-0.5, 0.5, len(t)).astype(np.float32)
    elif signal_type == "clipped":
        # Severely clipped sine wave
        samples = np.clip(2.0 * np.sin(2 * np.pi * 300 * t), -0.999, 0.999).astype(np.float32)
    else:
        samples = np.zeros(len(t), dtype=np.float32)

    raw_int16 = (samples * 32767).astype(np.int16).tobytes()
    with wave.open(str(tmp_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(raw_int16)

    return tmp_path


def run_tests():
    passed = 0
    total = 0

    def check(name: str, cond: bool, detail: str = ""):
        nonlocal passed, total
        total += 1
        if cond:
            passed += 1
            print(f"  [PASS] {name} {(' — ' + detail) if detail else ''}")
        else:
            print(f"  [FAIL] {name} {(' — ' + detail) if detail else ''}")

    print("\n====================================================================")
    print("AUDIO FORENSICS TEST SUITE")
    print("====================================================================")

    # 1. Missing file handling
    res1 = analyze_audio_forensics(Path("/non/existent/audio.wav"))
    check("1. Missing file handling", res1["status"] == "INSUFFICIENT_EVIDENCE", f"status={res1['status']}")

    # 2. Pure tone audio analysis
    tone_wav = create_test_wav(duration_s=1.0, signal_type="tone")
    try:
        res2 = analyze_audio_forensics(tone_wav)
        check("2. Pure tone analysis succeeds", res2["has_audio"] is True)
        check("2b. F0 pitch around 440 Hz", res2["metrics"]["mean_f0_hz"] is not None and 400 < res2["metrics"]["mean_f0_hz"] < 480, f"f0={res2['metrics']['mean_f0_hz']}")
        check("2c. Waveform points generated", len(res2["waveform_preview"]) == 120)
    finally:
        if tone_wav.exists():
            tone_wav.unlink()

    # 3. Hard-gated silence transitions
    gated_wav = create_test_wav(duration_s=1.5, signal_type="hard_gated")
    try:
        res3 = analyze_audio_forensics(gated_wav)
        check("3. Hard-gate silence analysis", res3["metrics"]["hard_gate_transitions"] > 0, f"transitions={res3['metrics']['hard_gate_transitions']}")
        check("3b. Silence indicator flagged", any(i["key"] == "hard_silence_gating" for i in res3["indicators"]))
    finally:
        if gated_wav.exists():
            gated_wav.unlink()

    # 4. White noise spectral flatness
    noise_wav = create_test_wav(duration_s=1.0, signal_type="noise")
    try:
        res4 = analyze_audio_forensics(noise_wav)
        check("4. Noise spectral flatness elevated", res4["metrics"]["spectral_flatness"] > 0.40, f"flatness={res4['metrics']['spectral_flatness']}")
        check("4b. Elevated flatness indicator", any(i["key"] == "elevated_spectral_flatness" for i in res4["indicators"]))
    finally:
        if noise_wav.exists():
            noise_wav.unlink()

    # 5. Clipped audio detection
    clipped_wav = create_test_wav(duration_s=1.0, signal_type="clipped")
    try:
        res5 = analyze_audio_forensics(clipped_wav)
        check("5. Clipping ratio detected", res5["metrics"]["clipping_ratio"] > 0.05, f"clip_ratio={res5['metrics']['clipping_ratio']}")
        check("5b. Digital clipping indicator", any(i["key"] == "digital_clipping" for i in res5["indicators"]))
    finally:
        if clipped_wav.exists():
            clipped_wav.unlink()

    # 6. Absence of overclaiming terminology
    all_summaries = [res2["assessment"], res3["assessment"], res4["assessment"], res5["assessment"]]
    banned_words = ["ai voice", "100% fake", "guaranteed synthetic", "proves manipulation"]
    no_banned = all(not any(b in s.lower() for b in banned_words) for s in all_summaries)
    check("6. Zero overclaiming language in assessments", no_banned)

    print(f"\nRESULTS: {passed}/{total} checks passed.\n")
    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
