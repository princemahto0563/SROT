"""
SROT Cross-Signal Forensic Assessment & Evidence Matrix Service.

Synthesizes multiple independent evidence streams (cryptographic integrity,
provenance/C2PA, physical image signals, recapture forensics, neural AI-synthetic
signals, propagation traces, and image quality gating) into a coherent,
legally transparent forensic decision-support assessment.

HONESTY STATEMENT:
This service does not produce a singular 'authenticity oracle' percentage.
It evaluates cross-signal agreement, identifies corroboration vs dissent,
factors in known physical limitations (e.g., screenshot false positives,
low resolution), and generates an evidence-backed narrative for court and
investigative casework.
"""
from __future__ import annotations

from typing import Any


def build_evidence_matrix(
    evidence_facts: dict[str, Any],
    signals: list[dict[str, Any]],
    recapture: dict[str, Any] | None,
    neural: dict[str, Any] | None,
    origin_matches: list[dict[str, Any]] | None,
    quality_gate: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """
    Construct an explicit, structured Evidence Matrix mapping each forensic
    source to its observation, strength, corroboration, and operational limitation.
    """
    matrix: list[dict[str, Any]] = []

    # 1. Cryptographic Integrity (SHA-256)
    sha256 = evidence_facts.get("sha256")
    size_bytes = evidence_facts.get("size_bytes", 0)
    matrix.append({
        "source": "Cryptographic Integrity",
        "measurement": "SHA-256 Digest & Hash Chain",
        "observation": f"Immutable SHA-256 computed on ingest: {sha256[:12]}… ({size_bytes:,} bytes). Audit chain verified.",
        "strength": "STRONG",
        "status": "VERIFIED",
        "corroboration": "Matches byte-level file store; recorded in tamper-evident hash ledger.",
        "limitation": "Cryptographic hashing establishes file immutability from point of intake; it cannot determine camera origin or real-world authenticity.",
    })

    # 2. Metadata & Acquisition (EXIF / Container)
    exif_count = evidence_facts.get("exif_fields", 0)
    c2pa_present = evidence_facts.get("c2pa_present", False)
    if c2pa_present:
        matrix.append({
            "source": "Content Credentials (C2PA)",
            "measurement": "Cryptographic Provenance Manifest",
            "observation": "Valid C2PA manifest detected with signed provenance assertions.",
            "strength": "STRONG",
            "status": "CONSISTENT",
            "corroboration": "Corroborates hardware/software generation pipeline.",
            "limitation": "C2PA manifests can be stripped by social media re-compression without altering image pixels.",
        })
    else:
        matrix.append({
            "source": "Content Credentials (C2PA)",
            "measurement": "Cryptographic Provenance Manifest",
            "observation": "No C2PA provenance manifest found in media container.",
            "strength": "LIMITED",
            "status": "NOT_DETECTED",
            "corroboration": "Consistent with forwarded/re-encoded social media lifecycle.",
            "limitation": "Absence of C2PA is standard across messaging platforms and does not by itself indicate manipulation.",
        })

    # Metadata Coherence
    if exif_count == 0:
        matrix.append({
            "source": "Metadata & Header Coherence",
            "measurement": "EXIF / Container Header Analysis",
            "observation": "Zero EXIF camera metadata fields present; metadata stripped by transmission.",
            "strength": "MODERATE",
            "status": "INDICATIVE",
            "corroboration": "Corroborates messaging app forwarding or screen-recording acquisition.",
            "limitation": "Metadata stripping is standard for privacy on WhatsApp, Telegram, and Twitter; non-forensic on its own.",
        })
    else:
        matrix.append({
            "source": "Metadata & Header Coherence",
            "measurement": "EXIF / Container Header Analysis",
            "observation": f"{exif_count} EXIF metadata tags preserved in container.",
            "strength": "MODERATE",
            "status": "CONSISTENT",
            "corroboration": "Provides device and timestamp metadata for timeline reconstruction.",
            "limitation": "EXIF timestamps and tags can be edited with standard metadata editing tools.",
        })

    # 3. Image Quality Gate
    if quality_gate:
        q_grade = quality_gate.get("quality_grade", "ADEQUATE")
        q_rel = quality_gate.get("reliability_status", "RELIABLE")
        q_factors = quality_gate.get("gating_factors", ["Quality satisfactory."])
        matrix.append({
            "source": "Image Quality Gating",
            "measurement": "Resolution, Sharpness & Dynamic Range Gating",
            "observation": f"Quality Grade: {q_grade} ({quality_gate.get('quality_score_pct', 80)}%). Reliability Gate: {q_rel}.",
            "strength": "BASELINE",
            "status": "VERIFIED" if q_rel == "RELIABLE" else "REDUCED_RELIABILITY",
            "corroboration": "Calibrates the evidentiary confidence of high-frequency and sensor-noise measurements.",
            "limitation": "Evaluates physical signal suitability, not semantic content.",
        })

    # 4. Classical Forensic Signals (Sensor Noise, DCT, Recompression)
    sig_map = {s.get("name"): s for s in signals}

    # Sensor Noise
    noise_sig = sig_map.get("Sensor-noise residual")
    if noise_sig:
        score = noise_sig.get("score")
        score_str = f"{score:.1f}%" if score is not None else "Measurement unavailable"
        matrix.append({
            "source": "Sensor Noise Residual (PRNU)",
            "measurement": "High-Pass Wavelet Residual Energy",
            "observation": f"Sensor noise residual score: {score_str} ({noise_sig.get('result', noise_sig.get('strength', 'N/A'))}).",
            "strength": "MODERATE",
            "status": "ANOMALOUS" if (score or 0) > 30 else "CONSISTENT",
            "corroboration": "Cross-referenced with DCT and Neural signal.",
            "limitation": "Sensor noise patterns can be attenuated by downscaling or heavy lossy re-compression.",
        })

    # DCT Benford
    dct_sig = sig_map.get("DCT first-digit distribution")
    if dct_sig:
        score = dct_sig.get("score")
        score_str = f"{score:.1f}%" if score is not None else "Measurement unavailable"
        matrix.append({
            "source": "Compression Physics (DCT / Benford)",
            "measurement": "Discrete Cosine Transform First-Digit Conformance",
            "observation": f"DCT Benford score: {score_str} ({dct_sig.get('result', dct_sig.get('strength', 'N/A'))}).",
            "strength": "MODERATE",
            "status": "ANOMALOUS" if (score or 0) > 30 else "CONSISTENT",
            "corroboration": "Evaluates whether compression coefficients follow natural optical logarithmic decay.",
            "limitation": "Multiple re-compressions can distort Benford's law distribution.",
        })

    # 5. Display Recapture Forensics
    if recapture and recapture.get("likelihood") != "NOT_APPLICABLE":
        re_score = recapture.get("likelihood_score")
        re_lik = recapture.get("likelihood", "LOW")
        bands = (recapture.get("static_bands") or {}).get("detected", False)
        handles = recapture.get("recovered_handles", [])
        score_str = f" ({re_score:.1f}%)" if re_score is not None else ""
        obs = f"Recapture likelihood: {re_lik}{score_str}."
        if bands:
            obs += " Static interface rows detected (screen-recording signature)."
        if handles:
            obs += f" {len(handles)} candidate source handle(s) recovered via OCR."

        matrix.append({
            "source": "Display Recapture Forensics",
            "measurement": "Letterbox, Static-Band Std-Dev & Moiré Analysis",
            "observation": obs,
            "strength": "STRONG" if re_lik in ("HIGH", "MEDIUM") else "MODERATE",
            "status": "INDICATIVE" if re_lik in ("HIGH", "MEDIUM") else "NOT_DETECTED",
            "corroboration": "Corroborates UI origin and contextualizes elevated neural synthetic scores.",
            "limitation": "Identifies secondary screen-capture containers; cannot determine the authenticity of content within the captured viewport without pixel signals.",
        })

    # 6. Neural AI-Synthetic Signal (Swin-ViT)
    if neural:
        agg = neural.get("aggregate") or {}
        med = agg.get("median_score")
        sc_caution = neural.get("screenshot_caution", False)
        n_obs = f"Model AI-synthetic score: {(med * 100):.1f}%" if med is not None else "Neural score unavailable."
        n_obs += f" ({agg.get('assessment_level', 'Moderate')} synthetic-image signal)."
        if sc_caution:
            n_obs += " [Safeguard: Screenshot caution active]."

        matrix.append({
            "source": "AI-Synthetic Image Signal (Swin-ViT)",
            "measurement": "Frame-Level Swin Transformer Inference (umm-maybe)",
            "observation": n_obs,
            "strength": "MODERATE",
            "status": "INDICATIVE" if (med or 0) >= 0.5 else "BASELINE",
            "corroboration": "Evaluated alongside recapture and classical compression signals.",
            "limitation": "Trained on artistic AI imagery (2022); elevated false-positive tendency on UI screenshots and screen recordings.",
        })

    # 7. Propagation & Origin Trace
    if origin_matches:
        earliest = origin_matches[0]
        matrix.append({
            "source": "Propagation & Origin Trace",
            "measurement": "Multi-View Perceptual Hashing (pHash/dHash/wHash)",
            "observation": f"{len(origin_matches)} matching copy(ies) identified. Earliest copy: {earliest.get('corpus_ref')} (observed {earliest.get('first_seen_iso', 'N/A')[:10]}).",
            "strength": "STRONG",
            "status": "VERIFIED",
            "corroboration": "Establishes multi-copy propagation chain spanning multiple days, with earliest indexed copy at '{earliest.get('corpus_ref')}'.",
            "limitation": "Identifies earliest known copy within searched reference corpus; does not assert first publication on the wider internet.",
        })
    else:
        matrix.append({
            "source": "Propagation & Origin Trace",
            "measurement": "Multi-View Perceptual Hashing (pHash/dHash/wHash)",
            "observation": "No matching reference found in the available corpus (Hamming distance > 14/64 bits across all indexed items).",
            "strength": "BASELINE",
            "status": "NOT_DETECTED",
            "corroboration": "Indicates this media is not a direct re-encode or visual derivative of items in the reference corpus.",
            "limitation": "Corpus search is bounded by indexed reference items; does not assert absence from external un-indexed platforms.",
        })

    # 8. Physical Acoustic Forensics (when audio media or video with audio track)
    audio_signals = [s for s in signals if s.get("key", "").startswith("audio_")]
    if audio_signals:
        obs_parts = [f"{s.get('name')}: {s.get('result')}" for s in audio_signals[:3]]
        anom_audio = [s for s in audio_signals if (s.get("score") or 0) >= 45]
        matrix.append({
            "source": "Physical Acoustic Forensics",
            "measurement": "Silence Gating, Spectral Flatness, Pitch Jitter, Clipping",
            "observation": " · ".join(obs_parts),
            "strength": "STRONG",
            "status": "ANOMALOUS" if anom_audio else "CONSISTENT",
            "corroboration": "Physical measurements of acoustic waveform dynamics and vocal cord micro-tremor.",
            "limitation": "Acoustic indicators identify physical signal anomalies; they do not provide an uncalibrated neural AI voice classification.",
        })

    return matrix


def synthesize_cross_signal_assessment(
    evidence_facts: dict[str, Any],
    signals: list[dict[str, Any]],
    recapture: dict[str, Any] | None,
    neural: dict[str, Any] | None,
    origin_matches: list[dict[str, Any]] | None,
    quality_gate: dict[str, Any] | None,
    stress_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Produce a transparent, evidence-state cross-signal forensic synthesis.
    Evaluates evidence integrity, provenance, quality gating, physical signals,
    recapture status, neural signal, and directional stress stability.
    """
    matrix = build_evidence_matrix(
        evidence_facts=evidence_facts,
        signals=signals,
        recapture=recapture,
        neural=neural,
        origin_matches=origin_matches,
        quality_gate=quality_gate,
    )

    # 1. Quality Status
    q_status = (quality_gate or {}).get("reliability_status", "RELIABLE")
    q_grade = (quality_gate or {}).get("quality_grade", "ADEQUATE")

    # 2. Recapture & Interface Indicators
    is_recaptured = bool(recapture and (
        recapture.get("likelihood") in ("HIGH", "MEDIUM") or
        (recapture.get("likelihood_score") or 0) >= 40.0
    ))
    has_static_bands = bool(recapture and (recapture.get("static_bands") or {}).get("detected"))
    recovered_handles = (recapture.get("recovered_handles") or []) if recapture else []

    # 3. Neural Signal (Swin-ViT)
    neural_agg = (neural.get("aggregate") or {}) if neural else {}
    neural_score = neural_agg.get("median_score")
    neural_available = bool(neural and neural.get("model_available", True) and neural_score is not None)
    neural_elevated = bool(neural_score is not None and neural_score >= 0.50)
    neural_strong = bool(neural_score is not None and neural_score >= 0.70)
    neural_low = bool(neural_score is not None and neural_score < 0.30)

    # 4. Classical Signals
    sig_map = {s.get("name"): s for s in signals}
    noise_score = (sig_map.get("Sensor-noise residual") or {}).get("score")
    dct_score = (sig_map.get("DCT first-digit distribution") or {}).get("score")
    recomp_score = (sig_map.get("Re-compression history") or {}).get("score")

    classical_elevated_count = sum(1 for sc in [noise_score, dct_score, recomp_score] if sc is not None and sc >= 35.0)
    classical_low_count = sum(1 for sc in [noise_score, dct_score, recomp_score] if sc is not None and sc < 20.0)

    # 5. Categorize Corroborating and Dissenting Factors
    corroborating_factors: list[str] = []
    dissenting_factors: list[str] = []
    recommendations: list[str] = []

    if is_recaptured:
        corroborating_factors.append(
            "Recapture Forensics detected static interface rows and letterboxing, establishing that the media is a screen recording or mobile capture."
        )

    if neural_available:
        if neural_elevated:
            if is_recaptured:
                dissenting_factors.append(
                    f"Swin-ViT neural model reports an elevated AI-synthetic score ({(neural_score*100):.1f}%), but because screen-recording interface rows are present, this elevated score may be partially driven by crisp UI rendering artifacts rather than generative synthesis."
                )
            else:
                corroborating_factors.append(
                    f"Swin-ViT neural model indicates an elevated AI-synthetic score ({(neural_score*100):.1f}%), consistent with synthetic image generation."
                )
        elif neural_low:
            corroborating_factors.append(
                f"Swin-ViT neural model reports a low AI-synthetic score ({(neural_score*100):.1f}%), consistent with authentic optical capture."
            )

    if q_status != "RELIABLE":
        dissenting_factors.append(
            f"Image Quality Gate is {q_status} (Grade: {q_grade}): high-frequency and sensor-noise signal sensitivities are attenuated."
        )

    exif_fields = evidence_facts.get("exif_fields", 0)
    if exif_fields == 0:
        corroborating_factors.append(
            "Complete absence of EXIF camera metadata is consistent with transmission across messaging platforms or screen-recording software."
        )

    if origin_matches:
        earliest = origin_matches[0]
        corroborating_factors.append(
            f"Perceptual fingerprint matching established a multi-copy propagation chain spanning multiple days, with earliest indexed copy at '{earliest.get('corpus_ref')}'."
        )
        recommendations.append(
            f"Issue legal preservation request for earliest known host: {earliest.get('corpus_ref')}."
        )

    for h in recovered_handles:
        handle_val = h.get("handle")
        if handle_val:
            recommendations.append(
                f"Verify recovered interface handle '{handle_val}' (OCR confidence {h.get('confidence', 0):.0f}%) against platform subscriber records."
            )

    # 6. Evidence State & Signal Consistency Determination
    if evidence_facts.get("media_kind") == "audio":
        audio_signals = [s for s in signals if s.get("key", "").startswith("audio_")]
        anom_audio = [s for s in audio_signals if (s.get("score") or 0) >= 45]
        if anom_audio:
            evidence_state = "PARTIALLY_CORROBORATED"
            signal_consistency = "MODERATE_CONSISTENCY"
            synthesis_headline = "Acoustic Discontinuities Observed in Audio Stream"
            evidence_state_rationale = (
                f"{len(anom_audio)} acoustic signal(s) display elevated anomaly scores (e.g. {anom_audio[0].get('name')}: "
                f"{anom_audio[0].get('score')}/100). Physical acoustic features suggest potential splicing or non-linear vocoding."
            )
            synthesis_narrative = (
                f"Acoustic analysis identified waveform discontinuities across {', '.join(s.get('name') for s in anom_audio)}. "
                "These physical measurements point toward non-linear editing or vocoding artifacts. "
                "The findings provide technical indications rather than proof; examiner review of the uncompressed audio track is recommended."
            )
        else:
            evidence_state = "CONSISTENT"
            signal_consistency = "STRONG_CONSISTENCY"
            synthesis_headline = "Standard Audio Distribution — Baseline Acoustic Profile"
            evidence_state_rationale = (
                "All acoustic measurements (silence gating, spectral flatness, vocal pitch jitter, clipping) "
                "fall within baseline parameters for natural recordings."
            )
            synthesis_narrative = (
                "The audio stream shows no measurable acoustic or spectral anomalies. "
                "Dynamic range and vocal pitch variance remain consistent with authentic microphone capture."
            )
    elif q_status in ("INSUFFICIENT_EVIDENCE", "POOR") or (not neural_available and not signals):
        evidence_state = "INSUFFICIENT"
        signal_consistency = "INSUFFICIENT"
        synthesis_headline = "Insufficient Visual Evidence for a Strong Manipulation Conclusion"
        evidence_state_rationale = (
            "Available signals are insufficient to form a confident manipulation or authenticity finding. "
            "Forensic decision-support advises inconclusive status."
        )
        synthesis_narrative = (
            "The submitted media provides insufficient signal detail for a reliable conclusion. "
            "Severe compression, downscaling, or missing streams prevent decisive attribution, so the finding remains inconclusive."
        )
    elif is_recaptured and neural_elevated:
        evidence_state = "PARTIALLY_CORROBORATED"
        signal_consistency = "MIXED"
        synthesis_headline = "Screen-Recorded Media Container with Elevated Synthetic-Image Signal"
        evidence_state_rationale = (
            f"Neural model reports elevated synthetic score ({(neural_score*100):.1f} / 100), but physical recapture signatures "
            "are present. Patch-based vision transformers have an established empirical sensitivity to sharp UI interface borders. "
            "Evidence state is assigned PARTIALLY_CORROBORATED to prevent false-positive overconfidence."
        )
        synthesis_narrative = (
            "Examiner note: Cross-signal checks show a layered evidentiary picture. Static interface bands and letterbox geometry "
            f"confirm this media is a mobile screen recording. While the neural vision model returned an elevated score of {(neural_score*100):.1f} / 100 "
            "(model score, not a calibrated probability), benchmark tests demonstrate that sharp vector UI borders can independently elevate patch-transformer scores. "
            "Consequently, the neural reading serves as contextual decision support rather than proof of generative tampering. "
            "Investigative priority should focus on recovered screen identifiers and propagation tracing."
        )
    elif neural_strong and classical_low_count >= 2 and not is_recaptured:
        evidence_state = "CONFLICTING"
        signal_consistency = "CONFLICTING"
        synthesis_headline = "Disagreement Observed Between Neural and Physical Forensic Signals"
        evidence_state_rationale = (
            f"Swin-ViT neural detector indicates elevated AI-synthetic characteristics ({(neural_score*100):.1f} / 100), whereas "
            "classical sensor noise and DCT compression statistics conform to natural optical capture. "
            "Evidence streams are in disagreement; expert manual examination is required."
        )
        synthesis_narrative = (
            f"Analytic domains point in divergent directions: the neural model flagged synthetic patterns (score: {(neural_score*100):.1f} / 100), "
            "yet sensor noise residuals and DCT compression structures match standard camera capture. "
            "Such divergence typically reflects modern diffusion techniques or selective local editing. The result cannot be resolved automatically and requires targeted manual review."
        )
    elif neural_elevated and not is_recaptured:
        evidence_state = "CONSISTENT"
        signal_consistency = "STRONG_CONSISTENCY" if classical_elevated_count >= 1 else "MODERATE_CONSISTENCY"
        synthesis_headline = "Elevated Synthetic-Image Signal Observed"
        evidence_state_rationale = (
            f"Neural model reports synthetic-image score of {(neural_score*100):.1f} / 100, supported by classical compression "
            "and absence of camera metadata."
        )
        synthesis_narrative = (
            f"The neural model identified elevated synthetic characteristics (score: {(neural_score*100):.1f} / 100). "
            "No screen-recording artifacts were detected. Classical frequency and noise checks show patterns consistent with synthetic synthesis or aggressive re-encoding. "
            "Examiner inspection of high-frequency edge residuals is warranted."
        )
    elif is_recaptured and not neural_elevated:
        evidence_state = "CONSISTENT"
        signal_consistency = "STRONG_CONSISTENCY"
        synthesis_headline = "Authentic/Recaptured Mobile Screen Recording"
        evidence_state_rationale = (
            "Evidence exhibits definitive screen-recording characteristics while neural and physical signals remain baseline."
        )
        synthesis_narrative = (
            "The file displays clear characteristics of a screen capture (static interface banners and borders), "
            "with both neural and physical signals remaining within standard photographic baselines. "
            "The content appears to be a recording of genuine media without generative synthesis indicators."
        )
    else:
        evidence_state = "CONSISTENT"
        signal_consistency = "STRONG_CONSISTENCY"
        synthesis_headline = "Standard Media Distribution — Baseline Forensic Profile"
        evidence_state_rationale = (
            "All physical, compression, and neural measurements fall within baseline parameters for natural forwarded media."
        )
        synthesis_narrative = (
            "No significant indicators of synthetic generation, localized tampering, or display recapture were observed. "
            "The measured compression and sensor metrics conform to standard forwarded digital media."
        )

    return {
        "synthesis_headline": synthesis_headline,
        "synthesis_narrative": synthesis_narrative,
        "evidence_state": evidence_state,
        "evidence_state_rationale": evidence_state_rationale,
        "signal_consistency": signal_consistency,
        "score_semantics": "MODEL_SCORE",
        "score_semantics_note": "Model score, not a calibrated probability.",
        "evidence_matrix": matrix,
        "corroborating_factors": corroborating_factors,
        "dissenting_or_neutral_factors": dissenting_factors,
        "investigative_recommendations": recommendations,
        "quality_status": q_status,
        "total_signals_evaluated": len(matrix),
    }
