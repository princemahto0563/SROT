# SROT — Phase 3 Implementation & Forensic Hardening Report

**Date**: September 1, 2026  
**Platform**: SROT (Source Tracing & Recapture Origin Toolkit / Synthetic-Real Optical Trace)  
**Engineering Team**: LogicaLoom  
**Verification Status**: **100% PASS** across all forensic verification suites

---

## 1. Executive Summary

SROT has transitioned from an initial multi-signal detection prototype into a **full-featured, forensic-grade digital evidence analysis workstation**. Continuing from the verified Phase 2 baseline, Phase 3 focused on implementing the higher-order reasoning, interpretation, gating, and cross-signal synthesis layers necessary for expert forensic casework and court proceedings under the Bharatiya Sakshya Adhiniyam (BSA), 2023.

Crucially, SROT **does not collapse diverse forensic evidence into an opaque "AI Oracle" single score**. Instead, it models the complete investigative hierarchy:
$$\text{Evidence Ingest} \to \text{Cryptographic Integrity} \to \text{Quality Gating} \to \text{Physical Signals} \to \text{Neural Signals} \to \text{Recapture Safeguards} \to \text{Cross-Signal Synthesis} \to \text{Evidence Matrix} \to \text{Court Artifacts}$$

All additions adhere strictly to the **100% offline-first architecture**, running locally with zero cloud API dependencies.

---

## 2. Baseline State vs. Phase 3 Additions

### What Was Already Present (Phase 2 Baseline):
- Evidence ingestion with SHA-256 integrity and path-traversal prevention.
- Cryptographic hash-linked audit ledger (`audit.py`).
- 8 independent classical image forensic signals (DCT Benford, sensor noise, blockiness, recompression, high-frequency energy, temporal continuity, metadata coherence).
- On-device Swin Transformer (`umm-maybe/AI-image-detector`, pinned commit `c7e223baf11bc40528af364ba7bdea030ef42f9e`, `CC BY-ND 4.0`) running locally on Apple MPS/Metal and CPU fallback.
- Recapture forensics (letterboxing, static UI bands, FFT moiré, OCR handle extraction).
- Multi-view perceptual hashing (pHash, dHash, wHash) with calibrated matching rules (`calibrate.py`).
- Multilingual OCR entity extraction and NetworkX investigation graph.
- 12-variant FFmpeg laundering stress engine.

### What Was Added & Hardened in Phase 3:
1. **Cross-Signal Forensic Assessment Layer (`cross_signal.py`)**:
   - Synthesizes all independent evidence streams into an evidence-backed, human-readable narrative.
   - Evaluates signal corroboration vs. dissent.
   - Automatically handles the empirical Swin-ViT screenshot limitation: contextualizes elevated neural scores when static interface bands are present, preventing false-positive manipulation conclusions on mobile screen recordings.
2. **Explicit Evidence Matrix (`cross_signal.py`, API, UI, Reports)**:
   - Source-by-source mapping: $\text{Evidence Source} \to \text{Observation} \to \text{Strength} \to \text{Status} \to \text{Operational Limitation}$.
   - Directly integrated into `/api/evidence/{ref}/cross-signal-assessment`, the analysis screen, and generated court reports.
3. **Robustness & Directional Stability Stress Analysis (`stress.py`, `main.py`)**:
   - Added quantitative directional stability classification (`HIGHLY_STABLE`, `DIRECTIONALLY_CONSISTENT`, `SENSITIVE_TO_TRANSFORMATION`).
   - Computes mean shift ($\Delta$) and maximum shift across 12 re-encoded, rescaled, cropped, and filtered variants.
4. **Pre-Analysis Image Quality Gating (`quality.py`)**:
   - Quantitative evaluation of Resolution adequacy ($w \times h, \text{MP}$), Sharpness via Laplacian variance ($\sigma^2(\nabla^2 I)$), Dynamic Range & Exposure clipping, Compression blockiness ratio, and High-pass Noise floor.
   - Assigns reliability gates: `RELIABLE`, `REDUCED_RELIABILITY`, `INSUFFICIENT_EVIDENCE` to calibrate confidence on degraded media.
5. **Spatial Forensic Trace & Localization Visualizer (`visual_trace.py`)**:
   - 3 offline, scientifically grounded spatial visualizations:
     * **Sensor Noise Residual Map (`noise_residual`)**: High-pass spatial filter isolating PRNU noise variations and synthetic smooth patches.
     * **Error Level Analysis (`ela_residual`)**: Controlled JPEG recompression difference heatmap showing quantization inconsistencies.
     * **High-Frequency Gradient Map (`gradient_inconsistency`)**: Sobel edge magnitude distribution highlighting sharp UI vector edges vs optical roll-off.
   - Streaming endpoints at `/api/evidence/{ref}/traces/{trace_type}` with false-color colormap overlays.
6. **14-Section Forensic Investigation Report & Court Packet Generator (`report.py`)**:
   - Enhanced deterministic Jinja2 $\to$ WeasyPrint PDF report pipeline covering all 14 investigative sections.
   - Dynamic macOS Homebrew library fallback hook ensuring seamless WeasyPrint PDF generation without environment errors.
   - Generates 6 court-ready PDFs + tamper-evident ZIP archive with SHA-256 manifest.
7. **Frontend Forensic Workstation Polish (`frontend/`)**:
   - Integrated the Holistic Cross-Signal Synthesis banner, Evidence Matrix, Image Quality Gate card, and Interactive Trace Visualizer into `Analysis.tsx`.
   - Verified TypeScript compilation (`tsc -b && vite build`) with zero errors.

---

## 3. Files Modified & Created

| Category | File | Description of Changes |
|---|---|---|
| **Service (New)** | `backend/app/services/cross_signal.py` | Cross-signal forensic assessment layer and Evidence Matrix builder. |
| **Service (New)** | `backend/app/services/quality.py` | Physical image quality evaluator and reliability gating engine. |
| **Service (New)** | `backend/app/services/visual_trace.py` | Spatial forensic trace generator (Noise residual, ELA, Sobel gradient). |
| **Service (Modified)** | `backend/app/services/report.py` | Integrated Evidence Matrix, Quality Gate, and macOS WeasyPrint cffi loader hook. |
| **API (Modified)** | `backend/app/main.py` | Added `/api/evidence/{ref}/cross-signal-assessment`, `/api/evidence/{ref}/quality`, `/api/system/traces`, `/api/evidence/{ref}/traces/{trace_type}`. |
| **Frontend (Modified)** | `frontend/src/screens/Analysis.tsx` | Integrated Evidence Matrix, Quality Gating card, and Forensic Trace Visualizer. |
| **Documentation (Updated)** | `FILE-MANIFEST.md` | Updated file manifest with new services and components. |
| **Documentation (Created)** | `PHASE3-IMPLEMENTATION-REPORT.md` | Comprehensive Phase 3 audit and completion report. |

---

## 4. New API Endpoints

```http
GET /api/evidence/{evidence_ref}/cross-signal-assessment
```
- **Description**: Returns the holistic cross-signal narrative synthesis, corroborating/dissenting factors, investigative recommendations, and the complete 7-source Evidence Matrix.

```http
GET /api/evidence/{evidence_ref}/quality
```
- **Description**: Returns physical image quality metrics (resolution, Laplacian sharpness, dynamic range, blockiness ratio, noise floor) and forensic reliability status (`RELIABLE`, `REDUCED_RELIABILITY`, `INSUFFICIENT_EVIDENCE`).

```http
GET /api/system/traces
```
- **Description**: Lists available spatial forensic trace types (`noise_residual`, `ela_residual`, `gradient_inconsistency`) with descriptions and interpretation notes.

```http
GET /api/evidence/{evidence_ref}/traces/{trace_type}?frame_idx=0
```
- **Description**: Generates and streams a 24-bit false-color spatial forensic trace PNG overlay blended with the original frame.

---

## 5. Verification & Test Execution Results

All baseline and new verification suites were executed against the running SROT platform:

```
======================================================================
1. inspect_data.py — Data Integrity & Structural Conformance
======================================================================
  Results: passed: 331 | failed: 0
  - SHA-256 integrity verified across all evidence items and packets.
  - Perceptual hash views validated across 368 ledger entries.
  - Zero placeholder text or forbidden over-claiming claims detected.

======================================================================
2. test_audit_chain.py — Cryptographic Ledger Tamper-Detection
======================================================================
  Results: 10/10 checks PASSED
  - Verified detection of content edits, payload tampering, and row deletions.
  - Verified cryptographic continuity and tamper classification.

======================================================================
3. calibrate.py — Perceptual Hash Population Separation
======================================================================
  Results: 100% Separation PASSED
  - True derivatives: 8–8 bits distance, 5–7 corroborating frames (5/5 accepted).
  - Unrelated controls: 18–32 bits distance, 0 corroborating frames (9/9 rejected).

======================================================================
4. test_features.py — End-to-End Feature Verification
======================================================================
  Results: passed: 30 | failed: 0
  - Hash verification: PASS (identical = MATCH, altered = MISMATCH).
  - Laundering stress test: PASS (12 variants generated, scored, real files).
  - Court-ready evidence packet: PASS (6 valid PDFs, non-empty, ZIP archive).
  - Report consistency: PASS (database, API, and rendered report in 100% agreement).
  - Over-claiming language audit: PASS (0 banned words).
  - Security & failure states: PASS (path traversal blocked, 404s clean).

======================================================================
5. e2e.py — Complete Pipeline Walk
======================================================================
  Results: 8-Stage Pipeline Walk PASSED
  - INGEST → ANALYSIS → NEURAL → TRACE → OCR → RECAPTURE → GRAPH → LEADS.

======================================================================
6. Frontend Build
======================================================================
  Command: cd frontend && npm run build
  Results: 0 TypeScript errors, 0 build warnings.
```

---

## 6. Model Provenance & Licensing Integrity

| Attribute | Specification |
|---|---|
| **Model Identifier** | `umm-maybe/AI-image-detector` |
| **Pinned Git Revision** | `c7e223baf11bc40528af364ba7bdea030ef42f9e` |
| **Model Architecture** | Swin Transformer (`SwinForImageClassification`) |
| **Execution Hardware** | Local Apple Silicon GPU (MPS) / CPU fallback |
| **License** | Creative Commons Attribution-NoDerivatives 4.0 International (`CC BY-ND 4.0`) |
| **Offline Guarantee** | `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` |
| **Model Scope** | Frame-level AI-synthetic image signal (decision-support only) |

---

## 7. Known Forensic Limitations & Operational Boundaries

1. **Screenshot / UI Elements**: Patch-based vision transformers can report elevated synthetic-image scores on crisp UI interfaces. SROT exposes this limitation transparently via the **Recapture Safeguard** (`screenshot_caution: true`) and cross-signal synthesis.
2. **Low-Resolution Video**: Clips $<360p$ suppress PRNU and high-frequency energy. SROT's **Quality Gate** flags this condition and downgrades signal reliability.
3. **Absence of Provenance**: The lack of C2PA manifests is standard on social media and is explicitly recorded as "Absence $\neq$ Manipulation".
4. **Attribution Ceiling**: SROT bounds its technical findings strictly to algorithmic measurements; legal attribution of human identity requires lawful subscriber record requests.

---

## 8. Conclusion & Readiness

SROT Phase 3 is **fully implemented, hardened, verified, and operational**. The system fulfills all requirements of an offline, explainable, evidence-backed forensic workstation suitable for law enforcement casework, forensic analysis, and court readiness under BSA §63.
