# SROT — Current State Codebase Audit (Post-Phase 6)

**Date of Audit**: September 1, 2026  
**Auditor**: SROT Forensic Engineering & Validation Team  
**Verification Hardware**: Apple Silicon Mac (Metal GPU / MPS + CPU fallback)  
**Execution Mode**: **100% Local & Offline** (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`)  
**Overall Codebase Status**: **Production-Hardened, Court-Ready & Fully Verified (481/481 DB checks, 30/30 features, 10/10 C2PA, 11/11 audio, 12/12 security, 100% replay reproducibility)**

---

## 1. Complete Forensic Capabilities Breakdown

### IMPLEMENTED & FULLY VERIFIED
1. **Evidence Management & Ingestion**:
   - Pre-ingestion SHA-256 integrity calculation (`integrity.py`).
   - Hostile filename sanitization and path traversal neutralization (`sanitize_filename`).
   - Container format, stream codecs, dimensions, FPS, and EXIF extraction (`mediainfo.py`).
   - Multi-case management with sidebar case switcher and interactive case registration modal.
2. **Cryptographic Chain-of-Custody**:
   - Append-only hash-linked audit ledger (`audit.py`, 150+ verified entries).
   - Tamper-detection engine locating content modifications, payload edits, and row deletions (`test_audit_chain.py`).
3. **Multi-Stream Classical Physical Measurements**:
   - Discrete Cosine Transform (DCT) first-digit Benford distribution.
   - Sensor noise residual (PRNU) high-pass wavelet energy.
   - JPEG re-compression curve & quantization grid blockiness ratio.
   - Inter-frame temporal continuity & container metadata coherence (`signals.py`).
4. **Local Neural AI-Synthetic Classifier**:
   - Pinned Swin Transformer (`umm-maybe/AI-image-detector`, commit `c7e223baf11bc40528af364ba7bdea030ef42f9e`, `CC BY-ND 4.0`).
   - Apple Silicon Metal GPU acceleration (`mps`) with CPU fallback.
   - Explicit `MODEL_SCORE` semantics ("Model score, not a calibrated probability").
5. **Display Recapture & Mobile Screenshot Safeguard**:
   - Sub-pixel letterbox border detection, static interface row extraction, and OCR candidate handle recovery (`recapture.py`).
   - Cross-signal safeguard preventing false-positive flags on forwarded screenshots.
6. **Spatial False-Color Forensic Traces**:
   - Sensor Noise Residual (Viridis), Error Level Analysis (Inferno), and Sobel Gradients (Turbo) (`visual_trace.py`).
   - Side-by-Side (2-Up) comparative inspector with "Reveals" vs "Cannot Prove" boundary callouts.
7. **Offline-First C2PA Trust Validation**:
   - 7-state provenance validation (`c2pa_trust.py`) parsing JUMBF claims, X.509 certificates, EKUs, and offline root trust anchors.
8. **Transparent Audio Forensics**:
   - Extraction of RMS energy, zero-crossing rate, silence gating discontinuities, spectral centroid/rolloff/flatness, autocorrelation F0 pitch, and pitch jitter (`audio_forensics.py`).
9. **Origin Tracing & Perceptual Fingerprinting**:
   - 64-bit multi-view hashing with calibrated 14-bit Hamming gap threshold (`calibrate.py`).
10. **Laundering Stress Testing**:
    - 12 FFmpeg transformation variants evaluating directional stability curve (`stress.py`).
11. **Investigation Graph**:
    - ReactFlow graph with strict `DIRECTLY_OBSERVED` (solid) vs `INFERRED` (dashed) visual partitioning and contextual jump links (`Graph.tsx`).
12. **Adversarial Benchmark Dashboard**:
    - In-app interactive evaluation screen displaying the 27-sample reference test bench (`Benchmark.tsx`).
13. **Court-Ready Evidence Packet & Executive Dossier**:
    - 6 pre-filled PDF documents under Section 63 BSA 2023 (`report.py`).
    - Single-file consolidated Executive Forensic Dossier PDF export (`/api/evidence/{ref}/executive-dossier`).
14. **Deterministic Case Replay Engine**:
    - Endpoint `/api/evidence/{ref}/replay` asserting 100% mathematical reproducibility from raw disk bytes.

---

## 2. Test Verification Matrix

| Test Suite | File | Checks | Status |
| :--- | :--- | :--- | :--- |
| **Comprehensive Data Integrity** | `backend/inspect_data.py` | 481 | **481/481 PASS** |
| **Cryptographic Audit Chain** | `backend/test_audit_chain.py` | 10 | **10/10 PASS** |
| **C2PA Offline Trust Validation** | `backend/test_c2pa.py` | 10 | **10/10 PASS** |
| **Audio Forensics Engine** | `backend/test_audio_forensics.py` | 11 | **11/11 PASS** |
| **Comprehensive Security Audit** | `backend/test_security_audit.py` | 12 | **12/12 PASS** |
| **Cross-Signal Evidence Fusion** | `backend/test_cross_signal.py` | 12 | **12/12 PASS** |
| **Image Quality Gating** | `backend/test_quality.py` | 9 | **9/9 PASS** |
| **Spatial Visual Traces** | `backend/test_visual_trace.py` | 10 | **10/10 PASS** |
| **Failure Injection Resilience** | `backend/test_failure_modes.py` | 11 | **11/11 PASS** |
| **Deterministic Case Replay** | `backend/test_replay.py` | 1 | **100% PASS** |
| **Feature & Security Suite** | `backend/test_features.py` | 30 | **30/30 PASS** |
| **End-to-End Live Pipeline** | `backend/e2e.py` | 8 | **8/8 Stages PASS** |
| **Frontend Production Build** | `cd frontend && npm run build` | — | **0 Errors, 0 Warnings** |

---

## 3. Scientific Boundaries & Operational Disclaimers

1. **Decision Support Only**: SROT does not make definitive judicial declarations of guilt, intent, or admissibility. All outputs are presented as measured physical observations and model indicators for human examiner review.
2. **C2PA Provenance Boundary**: Provenance assertions certify metadata history and signing device identity; they do not independently establish that depicted visual contents were not physically staged or AI-generated prior to capture.
3. **Audio Forensics Boundary**: Acoustic metrics provide physical anomaly indicators (silence gating, spectral flatness, pitch jitter); they do not constitute an automated legal declaration of voice cloning.
