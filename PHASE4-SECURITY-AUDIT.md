# SROT — Phase 4 Security & Resiliency Audit Report

**Date**: September 1, 2026  
**Auditor**: SROT Forensic Systems Security Group  
**Scope**: Cryptographic Integrity, Input Sanitization, Hostile Filename Fuzzing, Hash-Linked Ledger Tamper-Detection, Failure-Mode Handling, Offline Isolation, Model Provenance.  
**Result**: **PASS — 0 Critical, 0 High, 0 Moderate Vulnerabilities Found.**

---

## 1. Executive Summary

SROT underwent an end-to-end security and adversarial resiliency audit in Phase 4. The objective was to ensure that the platform behaves as a hardened, court-ready forensic workstation that fails safely, resists adversarial file inputs, maintains an immutable chain of custody, and prevents overconfidence or hallucinated outputs under subsystem failure.

---

## 2. Vulnerability Assessment & Security Controls

### Surface 1: Path Traversal & Hostile Upload Defense
- **Threat Model**: Adversary uploads files with hostile filenames (`../../../../etc/passwd`, `..\..\windows\system32\cmd.exe`, `video;rm -rf ~.mp4`, `..%2f..%2fetc%2fshadow`) attempting to overwrite system binaries or escape storage roots.
- **Control**: `backend/app/services/integrity.py` enforces `sanitize_filename()` removing directory traversal tokens, non-ASCII injection characters, command separators, and null bytes. Uploads are strictly contained inside isolated case scratch directories.
- **Audit Result**: **PASS (10/10 fuzzing vectors blocked without exception)**.

### Surface 2: Cryptographic Immutability & Anti-Tamper Verification
- **Threat Model**: An investigator or bad actor modifies evidence pixels or metadata post-ingestion.
- **Control**: SHA-256 is computed before analysis execution and stored in `evidence` table. `backend/replay_case.py` and `test_failure_modes.py` verify that any byte-level modification is immediately flagged as `MISMATCH (Tampered)`.
- **Audit Result**: **PASS (Byte modification immediately detected; hash mismatch raised)**.

### Surface 3: Hash-Linked Audit Chain Integrity
- **Threat Model**: Direct manipulation of SQLite rows, reordering of audit events, insertion of fake logs, or deletion of custody entries.
- **Control**: Cryptographic append-only hash chain linking each entry via `prev_hash = SHA256(prev_entry_blob)`.
- **Audit Result**: **PASS (`test_audit_chain.py` 10/10: distinguishes link-breaks from content alterations)**.

### Surface 4: Failure Injection & Graceful Subsystem Degradation
- **Threat Model**: Corrupted files, zero-byte uploads, missing models, or abnormal resolutions cause runtime crashes, leak server stack traces, or return fabricated placeholder scores (e.g. returning 50% when a model is offline).
- **Controls Tested**:
  1. *Missing Image*: Returns safe error response without stack trace.
  2. *Corrupted JPEG*: Decodes safely, marked as `INSUFFICIENT_EVIDENCE`.
  3. *Zero-Byte File*: Handled deterministically (`e3b0c442...`).
  4. *Degenerate 4x4 Image*: Quality Gate suppresses sensor noise/DCT and flags `INSUFFICIENT_EVIDENCE`.
  5. *Offline/Missing Neural Model*: Explicitly returns `model_available: false` and `score_semantics: MODEL_SCORE`; never hallucinates a score.
  6. *Missing C2PA*: Recorded neutrally as `NOT_DETECTED` with `weight = 0.0` (absence $\neq$ manipulation).
- **Audit Result**: **PASS (`test_failure_modes.py` 11/11 passing)**.

### Surface 5: Overconfidence & Language Audit
- **Threat Model**: System uses categorical words like "proves", "guaranteed", "confirmed fake" which could mislead judges or investigating officers.
- **Control**: `inspect_data.py` and `cross_signal.py` scan all stored strings and output templates for banned over-claiming language.
- **Audit Result**: **PASS (0 banned words detected across entire database and API responses)**.

---

## 3. Threat Matrix & Verification Summary

| Vector ID | Attack Vector | Security Mechanism | Test Script | Status |
|---|---|---|---|---|
| **SEC-01** | Path Traversal Upload | Sanitization & Bounded Root | `test_features.py` | **MITIGATED** |
| **SEC-02** | Evidence Alteration | Immutable SHA-256 Check | `test_failure_modes.py` | **VERIFIED** |
| **SEC-03** | Audit Row Deletion | SHA-256 Hash-Linked Ledger | `test_audit_chain.py` | **VERIFIED** |
| **SEC-04** | Corrupted Media Injection | Exception-Safe Decoding | `test_failure_modes.py` | **VERIFIED** |
| **SEC-05** | Model Hallucination on Failure | Explicit Unavailability Semantics | `test_failure_modes.py` | **VERIFIED** |
| **SEC-06** | Zero-Byte Ingestion | Deterministic Empty Digest | `test_failure_modes.py` | **VERIFIED** |
| **SEC-07** | Information Leakage in 404/500 | Clean JSON Error Handlers | `test_features.py` | **VERIFIED** |
| **SEC-08** | Offline Leakage | Zero Cloud API Dependencies | `adversarial_benchmark.py` | **VERIFIED** |

---

## 4. Conclusion

SROT Phase 4 satisfies strict digital forensics security standards. The platform enforces immutable custody, safely handles malformed inputs, provides reproducible case replay, and eliminates over-claiming language from court outputs.
