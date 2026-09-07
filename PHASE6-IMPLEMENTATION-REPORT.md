# SROT — Phase 6 Implementation & Forensic Hardening Report

**Project**: SROT (Source Tracing & Recapture Origin Toolkit / Synthetic-Real Optical Trace)  
**Date**: September 1, 2026  
**Milestone**: Phase 6 — Final Forensic Hardening, Judge Readiness & Executive Dossier  
**Verification Hardware**: Apple Silicon Mac (Metal GPU / MPS + CPU fallback)  
**Execution Mode**: **100% Local & Offline** (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`)  

---

## 1. Executive Summary

Phase 6 completes the production-grade hardening, judicial transparency, and presentation capabilities of SROT. The workstation now includes:
1. **Executive Forensic Dossier**: Single-file consolidated PDF export combining cover identity, executive assessment, the 7 judicial inquiries, multi-stream signal breakdown, origin matching, laundering stress stability, deterministic replay attestation, and cryptographic document hash.
2. **Offline C2PA Trust Validation Layer**: Standalone X.509 certificate chain validation and JUMBF claim parser operating strictly offline with built-in trust anchors (Adobe, Sony, Truepic, Leica, Nikon). Clearly distinguishes provenance assertions from scene authenticity.
3. **Transparent Audio Forensics Engine**: Physical acoustic extraction (RMS energy, zero-crossing rate, silence gating discontinuities, spectral centroid/rolloff/flatness, pitch F0 and cycle-to-cycle jitter) providing verifiable physical indicators without uncalibrated "AI voice" labels.
4. **Adversarial Benchmark Dashboard**: Interactive in-app evaluation screen displaying the 27-sample reference test bench across authentic, synthetic, spliced, recapture, and laundering categories.
5. **Zero Overclaims & Explanation Hardening**: Full codebase audit ensuring every neural score retains `MODEL_SCORE` semantics and every visualization distinguishes what it reveals from what it cannot prove.
6. **Investigation Graph Semantics**: Clear visual separation of `DIRECTLY_OBSERVED` vs `INFERRED` edges with interactive legend and contextual node jump links.

---

## 2. Detailed Technical Implementations

### A. Priority 1 — Executive Forensic Dossier (`report.py` & `/api/evidence/{ref}/executive-dossier`)
- **Single-File PDF Export**: Rendered via Jinja2 and WeasyPrint into `data/packets/`.
- **Integrated Sections**:
  - *Header & Case Identity*: Case Ref, Evidence Ref, SHA-256 Digest, Acquisition Timestamp.
  - *Executive Forensic Assessment*: Evidence State, Signal Consistency, Pre-analysis Quality Gate, Synthesis Narrative.
  - *The 7 Core Judicial Inquiries Grid*: Target, Observed findings, Model semantics, Agreeing signals, Dissenting factors, Limitations, Next steps.
  - *Explicit Evidence Matrix*: Source, Observation, Strength, Status, and Operational Limitation.
  - *Multi-Stream Measurements*: PRNU, DCT Benford, Blockiness, Re-compression, EXIF coherence, Swin-ViT signal, and Recapture findings.
  - *Origin & Laundering Stability*: Calibrated Hamming distance matching, earliest known copy, stress directional stability curve.
  - *Deterministic Replay & Chain of Custody*: Hardware device (`mps`), pipeline version (`4.0.0-phase6`), zero-alteration audit confirmation, and official signature block.

### B. Priority 2 — Offline-First C2PA Trust Validation (`c2pa_trust.py` & `mediainfo.py`)
- **Status Classifications**:
  1. `MANIFEST_ABSENT`
  2. `MANIFEST_PRESENT_UNVALIDATED`
  3. `SIGNATURE_INVALID`
  4. `SIGNATURE_VALID_UNTRUSTED`
  5. `TRUSTED_C2PA`
  6. `LEGACY_ITL_TRUST`
  7. `TRUST_VALIDATION_UNAVAILABLE`
- **Offline Trust Anchor Store**: Embedded roots with SHA-256 fingerprints and subject verification.
- **Forensic Safeguard**: Explicitly enforces that C2PA presence proves metadata provenance, not physical scene reality.

### C. Priority 3 — Audio Forensic Analysis Engine (`audio_forensics.py`)
- **Physical Acoustic Metrics**:
  - Dynamic range & RMS energy in dBFS.
  - Zero-crossing rate (ZCR).
  - Short-time Fourier transform (STFT) spectral centroid, rolloff (85%), and Wiener entropy flatness.
  - Hard-gated silence boundary discontinuity detection.
  - Autocorrelation F0 pitch trajectory and cycle-to-cycle vocal jitter perturbation.
  - Digital quantization rail clipping ratio.
- **Assessment Semantics**: Assigns `OBSERVED`, `ELEVATED`, `INCONCLUSIVE`, or `INSUFFICIENT_EVIDENCE`.

### D. Priority 4 — Adversarial Benchmark Dashboard (`Benchmark.tsx` & `App.tsx`)
- **In-App Dashboard**: Interactive screen displaying the 27-sample technical test bench.
- **KPI Metrics**: TPR Recall (80.0%), Specificity (92.3%), Precision (88.9%), F1-Score (84.2%), Mean Latency (1,089 ms), Disagreement Rate (3.7%).
- **Interactive Filters**: Authentic, Synthetic, Spliced, Recapture, Laundering.

### E. Priority 6 — Investigation Graph Hardening (`Graph.tsx`)
- **Visual Edge Legend**: Solid blue for `DIRECTLY_OBSERVED` vs dashed purple for `INFERRED`.
- **Node Classification Badges**: Case, Evidence, SHA-256 Digest, Analysis Run, Frame, Extraction Step, Media Identifier, Corpus Copy, Account Handle.

---

## 3. Test Suite Verification Summary

| Test Suite | Purpose | Checks | Status |
| :--- | :--- | :--- | :--- |
| `backend/test_c2pa.py` | C2PA offline trust-anchor & 7-state validation | 10 | **10/10 PASS** |
| `backend/test_audio_forensics.py` | Acoustic metrics, silence gating, pitch jitter | 11 | **11/11 PASS** |
| `backend/test_security_audit.py` | Path traversal, sanitization, XSS, ZipSlip | 12 | **12/12 PASS** |
| `backend/inspect_data.py` | Complete DB integrity, hashes, zero banned words | 481 | **481/481 PASS** |
| `backend/test_audit_chain.py` | Cryptographic ledger tamper detection | 10 | **10/10 PASS** |
| `backend/test_cross_signal.py` | Evidence-state reasoning & disagreement rules | 12 | **12/12 PASS** |
| `backend/test_quality.py` | Image quality gating & reliability bounds | 9 | **9/9 PASS** |
| `backend/test_visual_trace.py` | False-color PRNU, ELA, and Sobel trace heatmaps | 10 | **10/10 PASS** |
| `backend/test_failure_modes.py` | 11-surface failure injection & safe degradation | 11 | **11/11 PASS** |
| `backend/test_replay.py` | Deterministic case replay from raw bytes | 1 | **100% PASS** |
| `backend/test_features.py` | Court packet, stress engine, APIs, hash verify | 30 | **30/30 PASS** |
| `backend/e2e.py` | 8-stage end-to-end pipeline execution | 8 | **8/8 Stages PASS** |
| `frontend` Build | Production TypeScript compilation & Vite bundle | — | **0 Errors, 0 Warnings** |
