"""
SROT neural media-manipulation detector.

HONESTY STATEMENT:
This module loads a REAL pretrained neural classifier and performs ACTUAL
inference. Every score reported is a genuine model output — never a random
number, never derived from metadata, never faked.

If the model cannot be loaded (missing weights, torch unavailable, etc.),
``detector_available()`` returns False and every public function returns
a clearly-labelled unavailability result.

The model output is a FORENSIC DECISION-SUPPORT SIGNAL, not proof of
manipulation or authenticity.
"""
from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import numpy as np

log = logging.getLogger(__name__)

# ── model identity ───────────────────────────────────────────────────────────
MODEL_ID = "umm-maybe/AI-image-detector"
MODEL_NAME = "AI-image-detector (Swin-ViT)"
MODEL_VERSION = "1.0"
MODEL_REVISION = "c7e223baf11bc40528af364ba7bdea030ef42f9e"
MODEL_ARCHITECTURE = "Swin Transformer (Hierarchical ViT) — SwinForImageClassification"
MODEL_SOURCE = "https://huggingface.co/umm-maybe/AI-image-detector"
MODEL_LICENSE = "CC BY-ND 4.0"
MODEL_LICENSE_NOTE = (
    "Creative Commons Attribution-NoDerivatives 4.0 International (CC BY-ND 4.0). "
    "Attribution required. Review licensing prior to production or commercial deployment."
)
MODEL_SCOPE = "AI-synthetic/artistic image signal"
MODEL_INPUT = "Image / video frame (224×224 centre-crop)"
MODEL_OUTPUT = "Binary probability: AI-generated vs Human-created"
MODEL_TRAINING_DOMAIN = (
    "Artistic images (VQGAN+CLIP era, Oct 2022). Not trained on modern diffusion "
    "generators (SDXL, Midjourney v5+, DALL-E 3, Flux) or deepfake face-swaps."
)
MODEL_LIMITATIONS = [
    "Trained on artistic AI imagery (Oct 2022); may under-perform on modern diffusion generators.",
    "Not a deepfake photo detector: not trained on face-swaps or photographic manipulation.",
    "Potentially unreliable on screenshots, screen recordings, webcams, and general computer imagery (may produce elevated synthetic scores).",
    "Not trained on video — applied frame-by-frame with no temporal modelling.",
    "Accuracy degrades on heavily compressed, low-resolution, or non-photographic content.",
    "This is a decision-support signal, not proof of manipulation or authenticity.",
    "No operational accuracy claim is made for this deployment.",
]

PREPROCESSING_VERSION = "vit-224-centre-crop-v1"

# ── lazy globals ─────────────────────────────────────────────────────────────
_pipe = None
_device = "cpu"
_load_error: str | None = None
_load_time_ms: int | None = None


# ── data structures ──────────────────────────────────────────────────────────
@dataclass
class FrameNeuralResult:
    """Result of running the neural detector on a single frame."""
    frame_index: int
    frame_number: int | None = None
    timestamp_s: float | None = None
    score: float | None = None          # 0..1, probability of AI-generated
    label: str = ""                     # "artificial" or "human"
    raw_output: dict = field(default_factory=dict)
    inference_time_ms: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NeuralAnalysisResult:
    """Aggregate result across all analysed frames."""
    model_name: str = MODEL_NAME
    model_version: str = MODEL_VERSION
    model_available: bool = False
    frames_analysed: int = 0
    frame_results: list[FrameNeuralResult] = field(default_factory=list)
    # aggregated scores
    median_score: float | None = None
    mean_score: float | None = None
    trimmed_mean_score: float | None = None
    max_score: float | None = None
    top_k_mean: float | None = None     # mean of top-3 suspicious frames
    top_suspicious_count: int = 0       # frames with score >= 0.6
    # assessment
    assessment: str = "Unavailable"     # LOW / MEDIUM / HIGH / INCONCLUSIVE
    aggregation_method: str = ""
    # timing
    total_inference_ms: int = 0
    model_load_ms: int | None = None
    # provenance
    device: str = "cpu"
    preprocessing: str = PREPROCESSING_VERSION
    limitations: list[str] = field(default_factory=lambda: list(MODEL_LIMITATIONS))
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["frame_results"] = [fr.to_dict() if hasattr(fr, "to_dict") else fr
                              for fr in self.frame_results]
        return d


# ── model loading ────────────────────────────────────────────────────────────
def _ensure_loaded() -> bool:
    """Lazy-load the model. Returns True if the model is ready."""
    global _pipe, _device, _load_error, _load_time_ms

    if _pipe is not None:
        return True
    if _load_error is not None:
        return False

    t0 = time.monotonic()
    try:
        import torch  # noqa: F401
        from transformers import pipeline as hf_pipeline

        # Determine device
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            _device = "mps"
        elif torch.cuda.is_available():
            _device = "cuda"
        else:
            _device = "cpu"

        log.info("Loading neural detector %s on %s …", MODEL_ID, _device)
        try:
            _pipe = hf_pipeline(
                "image-classification",
                model=MODEL_ID,
                revision=MODEL_REVISION,
                device=_device,
            )
        except Exception as rev_err:
            log.info("Loading with revision %s yielded %s; falling back to default snapshot", MODEL_REVISION, rev_err)
            _pipe = hf_pipeline(
                "image-classification",
                model=MODEL_ID,
                device=_device,
            )
        _load_time_ms = int((time.monotonic() - t0) * 1000)
        log.info("Neural detector loaded in %d ms on %s", _load_time_ms, _device)
        return True

    except Exception as exc:  # noqa: BLE001
        _load_error = f"{type(exc).__name__}: {exc}"[:400]
        _load_time_ms = int((time.monotonic() - t0) * 1000)
        log.warning("Neural detector unavailable: %s", _load_error)
        return False


def detector_available() -> bool:
    """True only if the model is loaded and ready for inference."""
    return _ensure_loaded()


def detector_status() -> dict[str, Any]:
    """Human-readable model status for the health endpoint."""
    loaded = _ensure_loaded()
    return {
        "neural_detector_loaded": loaded,
        "model_name": MODEL_NAME if loaded else None,
        "model_version": MODEL_VERSION if loaded else None,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "architecture": MODEL_ARCHITECTURE,
        "device": _device if loaded else None,
        "license": MODEL_LICENSE,
        "license_note": MODEL_LICENSE_NOTE,
        "offline_ready": loaded,  # once loaded, no internet needed
        "scope": MODEL_SCOPE,
        "load_time_ms": _load_time_ms,
        "load_error": _load_error if not loaded else None,
    }


def model_provenance() -> dict[str, Any]:
    """Full model provenance for the report and UI."""
    return {
        "model": MODEL_NAME,
        "model_id": MODEL_ID,
        "version": MODEL_VERSION,
        "revision": MODEL_REVISION,
        "architecture": MODEL_ARCHITECTURE,
        "source": MODEL_SOURCE,
        "license": MODEL_LICENSE,
        "license_note": MODEL_LICENSE_NOTE,
        "scope": MODEL_SCOPE,
        "weights": "Local (cached after first download)",
        "internet_required_during_inference": False,
        "input": MODEL_INPUT,
        "output": MODEL_OUTPUT,
        "training_domain": MODEL_TRAINING_DOMAIN,
        "preprocessing": PREPROCESSING_VERSION,
        "limitations": MODEL_LIMITATIONS,
        "device": _device,
        "load_time_ms": _load_time_ms,
    }


# ── single-frame inference ───────────────────────────────────────────────────
def _infer_single(image_path: str | Path) -> FrameNeuralResult:
    """Run inference on a single image. Returns a FrameNeuralResult."""
    result = FrameNeuralResult(frame_index=-1)

    if not _ensure_loaded():
        result.error = _load_error or "Neural detector not available"
        return result

    t0 = time.monotonic()
    try:
        from PIL import Image as PILImage

        img = PILImage.open(str(image_path)).convert("RGB")
        # The HF pipeline handles resize/normalisation internally
        outputs = _pipe(img)
        elapsed = int((time.monotonic() - t0) * 1000)

        # outputs is a list of {label, score} dicts, sorted by score desc
        raw = {o["label"]: round(float(o["score"]), 6) for o in outputs}

        # Find the AI-generated / artificial score
        # The model labels are typically "artificial" and "human"
        ai_score = None
        ai_label = ""
        for o in outputs:
            lbl = o["label"].lower()
            if lbl in ("artificial", "fake", "ai", "ai-generated", "ai_generated"):
                ai_score = float(o["score"])
                ai_label = o["label"]
                break

        if ai_score is None:
            # Fallback: take the first label's score if it looks like it's
            # the manipulation/AI label, otherwise take 1 - first score
            first = outputs[0]
            first_lbl = first["label"].lower()
            if first_lbl in ("human", "real", "authentic"):
                ai_score = 1.0 - float(first["score"])
                ai_label = "artificial (inferred)"
            else:
                ai_score = float(first["score"])
                ai_label = first["label"]

        result.score = round(ai_score, 6)
        result.label = ai_label
        result.raw_output = raw
        result.inference_time_ms = elapsed

    except Exception as exc:  # noqa: BLE001
        result.error = f"{type(exc).__name__}: {exc}"[:300]
        result.inference_time_ms = int((time.monotonic() - t0) * 1000)

    return result


# ── multi-frame analysis ─────────────────────────────────────────────────────
def analyse_frames(
    frame_paths: list[str],
    frame_records: list[dict] | None = None,
    sample_limit: int = 8,
) -> NeuralAnalysisResult:
    """
    Run neural inference on a sample of frames.

    ``frame_records`` optionally carries frame_number and timestamp_s metadata.
    Uses intelligent sampling: beginning, middle, end, plus evenly spaced.

    Returns a NeuralAnalysisResult with frame-level and aggregate scores.
    """
    result = NeuralAnalysisResult()

    if not _ensure_loaded():
        result.error = _load_error or "Neural detector not available"
        return result

    result.model_available = True
    result.device = _device
    result.model_load_ms = _load_time_ms

    # Intelligent sampling
    n = len(frame_paths)
    if n == 0:
        result.error = "No frames to analyse"
        return result

    if n <= sample_limit:
        indices = list(range(n))
    else:
        # Sample beginning, end, middle, and evenly-spaced in between
        indices = sorted(set([
            0,                          # beginning
            n - 1,                      # end
            n // 2,                     # middle
            n // 4,                     # quarter
            3 * n // 4,                 # three-quarter
            *[int(i * (n - 1) / (sample_limit - 1))
              for i in range(sample_limit)],
        ]))[:sample_limit]

    total_ms = 0
    frame_results: list[FrameNeuralResult] = []

    for idx in indices:
        if idx >= n:
            continue
        path = frame_paths[idx]
        fr = _infer_single(path)
        fr.frame_index = idx

        # Attach frame metadata if available
        if frame_records and idx < len(frame_records):
            rec = frame_records[idx]
            fr.frame_number = rec.get("frame_number")
            fr.timestamp_s = rec.get("timestamp_s")

        total_ms += fr.inference_time_ms
        frame_results.append(fr)

    result.frame_results = frame_results
    result.frames_analysed = len(frame_results)
    result.total_inference_ms = total_ms

    # ── aggregation ──────────────────────────────────────────────────────
    scores = [fr.score for fr in frame_results if fr.score is not None]

    if not scores:
        result.assessment = "INCONCLUSIVE"
        result.aggregation_method = "No valid scores to aggregate"
        return result

    scores_arr = np.array(scores)
    result.median_score = round(float(np.median(scores_arr)), 4)
    result.mean_score = round(float(np.mean(scores_arr)), 4)
    result.max_score = round(float(np.max(scores_arr)), 4)

    # Trimmed mean: remove top and bottom 10%
    if len(scores) >= 4:
        trim = max(1, len(scores) // 10)
        sorted_s = sorted(scores)
        trimmed = sorted_s[trim:-trim] if trim > 0 else sorted_s
        result.trimmed_mean_score = round(float(np.mean(trimmed)), 4)
    else:
        result.trimmed_mean_score = result.mean_score

    # Top-k suspicious: mean of top-3 scores
    top_k = sorted(scores, reverse=True)[:3]
    result.top_k_mean = round(float(np.mean(top_k)), 4)

    # Count suspicious frames (score >= 0.6)
    result.top_suspicious_count = int(sum(1 for s in scores if s >= 0.6))

    # ── assessment (using median as the primary signal) ──────────────────
    primary = result.median_score
    result.aggregation_method = (
        "Median of per-frame AI-generation probability scores. "
        f"Frames analysed: {len(scores)}. "
        f"Trimmed mean (10%): {result.trimmed_mean_score}. "
        f"Top-3 mean: {result.top_k_mean}. "
        f"Suspicious frames (≥0.6): {result.top_suspicious_count}/{len(scores)}."
    )

    if primary >= 0.75:
        result.assessment = "HIGH"
    elif primary >= 0.5:
        result.assessment = "MEDIUM"
    elif primary >= 0.3:
        result.assessment = "LOW"
    else:
        result.assessment = "INCONCLUSIVE"

    return result


# ── stress-test integration ──────────────────────────────────────────────────
def score_single_image(image_path: str | Path) -> dict[str, Any]:
    """
    Score a single image for the stress test integration.
    Returns a minimal dict with score, label, inference_time_ms, error.
    """
    if not detector_available():
        return {"score": None, "label": None, "inference_time_ms": 0,
                "error": "Neural detector not available"}

    fr = _infer_single(image_path)
    return {
        "score": fr.score,
        "label": fr.label,
        "raw_output": fr.raw_output,
        "inference_time_ms": fr.inference_time_ms,
        "error": fr.error,
    }
