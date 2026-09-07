# SROT — Phase 5 Implementation & Verification Report

**Project**: SROT (Source Tracing & Recapture Origin Toolkit / Synthetic-Real Optical Trace)  
**Date**: September 1, 2026  
**Milestone**: Phase 5 — Full Investigator Workstation, Replay Verification & Forensic Hardening  
**Verification Environment**: Apple Silicon Mac (Metal GPU / MPS + CPU fallback)  
**Execution Mode**: **100% Local & Offline** (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`)  

---

## 1. Executive Summary

Phase 5 transitions SROT from a set of forensic analysis screens into a fully integrated, end-to-end digital media forensics workstation. The application provides cryptographic chain-of-custody tracking, independent physical signal measurements, spatial false-color heatmaps, neural Swin-ViT detection with explicit `MODEL_SCORE` semantics, display recapture geometry, multilingual OCR entity parsing, laundering stress testing, interactive graph exploration, court-ready PDF generation, and mathematical case replay verification.

All tests have been executed locally in offline mode with **100% pass rates**.

---

## 2. Features Implemented & Verified in Phase 5

### A. Forensic Decision Transparency & The 7 Judicial Inquiries
- **Executive Forensic Assessment Card** (`frontend/src/screens/Analysis.tsx`):
  - Integrates the Evidence State (`CONSISTENT`, `PARTIALLY_CORROBORATED`, `CONFLICTING`, `INSUFFICIENT`) and Signal Agreement (`STRONG_CONSISTENCY`, `MODERATE_CONSISTENCY`, `MIXED`, `CONFLICTING`).
  - Dynamic explanatory narrative detailing *why* SROT assigned its state based on measured physical signals, neural Swin-ViT scores, and recapture static row interactions.
  - Answers the 7 essential judicial forensic inquiries:
    1. *Target of Analysis*: Media container, frame count, dimensions, SHA-256 digest.
    2. *Primary Observed Finding*: Evidence synthesis narrative.
    3. *Neural Signal Semantics*: Explicit `MODEL_SCORE` declaration ("Model score, not a calibrated probability").
    4. *Corroborating Signals*: Physical and algorithmic measurements in agreement.
    5. *Disagreements & Safeguards*: Dissenting factors, baseline signals, and UI screenshot caveats.
    6. *Operational Limitations*: Gating constraints and model domain boundaries.
    7. *Recommended Next Actions*: Ordered, actionable checklist for the examiner.

### B. Interactive Side-by-Side Spatial Forensic Trace Inspector
- **Comparative 2-Up View Mode**: Reference frame positioned side-by-side with spatial false-color overlays.
- **Trace Modes**:
  - `noise_residual`: Sensor Noise Residual Map (PRNU Isolation, Viridis false-color).
  - `ela_residual`: Error Level Analysis (Quantization Delta, Inferno false-color).
  - `gradient_inconsistency`: Sobel Gradient Magnitude (Turbo false-color).
- **Scientific Boundaries Guidance**: Direct callouts explaining *What this visualization can reveal* vs *What this visualization cannot prove*.

### C. Deterministic Forensic Case Replay (`/api/evidence/{ref}/replay` & `replay.py`)
- **Live Re-execution**: Deterministically recalculates SHA-256 integrity, quality gating, Swin-ViT inference, and signal scores from raw disk bytes.
- **Comparison Delta Matrix**: Returns per-signal $\Delta$, execution latency, hardware platform (`mps`), model provenance, and cryptographic byte match.
- **Frontend Verification Widget**: "Verify case reproducibility" button integrated into the analysis header for live demonstration.

### D. Case & Evidence Management
- **Case Switcher Dropdown**: Allows instant switching between cases (`CASE-2026-001`, `CASE-2026-002`) across the entire workstation.
- **New Case Registration Modal**: Registered directly to the SQLite database with full audit ledger logging.

### E. Investigation Graph Deepening (`casebuild.py` & `Graph.tsx`)
- **Forensic Node Types**: Added dedicated nodes for Cryptographic SHA-256 Digest (`hash`), Analysis Evaluation (`analysis`), and Recovered Account Handles (`account`).
- **Interactive Inspector Navigation**: Node selection drawer provides direct jump links to the corresponding forensic module (Analysis, Visual Traces, OCR Identifiers, Recapture, Origin).

### F. Enhanced Forensic Report & Court Packet (`report.py`)
- **Section 18 Added**: Embedded Deterministic Forensic Replay & Verification Environment recording software pipeline version, hardware device, model revision hash, and mathematical reproducibility bounds.

---

## 3. Test Verification Suite Results

| Test Suite | Script | Status | Results |
| :--- | :--- | :--- | :--- |
| **Comprehensive Data Integrity** | `backend/inspect_data.py` | **PASS** | **432 / 432 checks passed** |
| **Cryptographic Audit Chain** | `backend/test_audit_chain.py` | **PASS** | **10 / 10 checks passed** |
| **Failure Injection & Resilience** | `backend/test_failure_modes.py` | **PASS** | **11 / 11 checks passed** |
| **Cross-Signal Evidence Fusion** | `backend/test_cross_signal.py` | **PASS** | **12 / 12 checks passed** |
| **Image Quality Gating** | `backend/test_quality.py` | **PASS** | **9 / 9 checks passed** |
| **Spatial Visual Traces** | `backend/test_visual_trace.py` | **PASS** | **10 / 10 checks passed** |
| **Deterministic Case Replay** | `backend/test_replay.py` | **PASS** | **100% Reproducibility Verified** |
| **Feature & Security Suite** | `backend/test_features.py` | **PASS** | **30 / 30 checks passed** |
| **End-to-End Pipeline** | `backend/e2e.py` | **PASS** | **8 / 8 stages passed** |
| **Frontend Production Build** | `npm run build` | **PASS** | **0 errors, 0 warnings** |

---

## 4. Security & Offline Guarantees

1. **Zero External Runtime Dependencies**: Model weights (`umm-maybe/AI-image-detector`) run locally from disk cache. No external API calls are made during inference.
2. **Path Traversal Protection**: Uploaded files and trace paths are strictly sanitized against traversal attacks (`../`, `..%2f`, Windows backslashes).
3. **Cryptographic Chain-of-Custody**: All events are hash-linked in an append-only ledger; any deletion or modification is immediately flagged by the integrity verifier.
4. **Pre-Analysis SHA-256 Hashing**: Checksums are computed and recorded before any analysis stage begins.

---

## 5. Live Demonstration Order (6 Minutes)

1. **Case Dashboard (`/`)**: Show active case metadata, cryptographic audit status (133 entries verified), and quick-access triage bar.
2. **Evidence Intake (`/upload`)**: Upload forwarded video; highlight SHA-256 hash computed before analysis begins.
3. **Multi-Stream Forensic Assessment (`/analysis`)**: Walk through the 7 Judicial Inquiries, Evidence Matrix, and Evidence State rationale.
4. **Side-by-Side Spatial Traces (`/analysis#visual-traces`)**: Compare reference frame vs Sensor Noise Residual, ELA, and Sobel Gradients.
5. **Deterministic Case Replay (`/analysis`)**: Click "Verify case reproducibility" and display live 100% reproducibility delta matrix.
6. **AI-Synthetic Signal (`/neural`)**: Show local Swin-ViT score (72.1%), `MODEL_SCORE` semantics, and screenshot safeguard warning.
7. **Recapture Forensics (`/recapture`)**: Show static interface row detection and OCR source handle candidate recovery.
8. **Origin Trace (`/origin`)**: Show chronological propagation timeline and calibrated 14-bit Hamming gap threshold.
9. **Laundering Stress Test (`/stress`)**: Review 12 FFmpeg transformation variants and directional stability curve.
10. **Investigation Graph (`/graph`)**: Inspect observed vs inferred relationships, SHA-256 hash nodes, and derivation metadata.
11. **Court Packet Generation (`/packet`)**: Generate 6 standalone pre-filled PDF documents and download the signed ZIP archive.
