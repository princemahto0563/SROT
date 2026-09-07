# SROT — Phase 6 Security & Resilience Audit

**Date of Audit**: September 1, 2026  
**Auditor**: SROT Forensic Systems Security Team  
**Scope**: Backend API endpoints, media ingestion, file parsing, X.509 cryptographic validation, subprocess execution, database transactions, template rendering, and frontend client boundaries.  
**Execution Environment**: Apple Silicon Mac (Local Darwin / Offline Virtualenv)  
**Overall Security Rating**: **HIGH ASSURANCE / COURT-READY DEFENSE**  

---

## 1. Threat Vectors Evaluated & Defenses Verified

### A. Path Traversal & File Upload Attacks
- **Threat**: Uploading files with traversal sequences (`../../../../etc/passwd`, `..%2f..%2f`, Windows backslashes) to escape the evidence storage directory.
- **Defense**: `integrity.sanitize_filename()` normalizes via NFKD, strips directory paths using `Path(name).name`, removes non-alphanumeric characters, and enforces a 120-character maximum length limit.
- **Verification**: `test_security_audit.py` passes 100% against Unix, Windows, and URL-encoded traversal payloads.

### B. Archive Extraction & ZipSlip Vulnerabilities
- **Threat**: Malicious ZIP archives containing relative path escapes targeting system files during archive unpack.
- **Defense**: The packet generator writes strictly relative filenames (`01_BSA_Section63_Certificate_DRAFT.pdf`, etc.) and the unpacker asserts `not any(".." in name or name.startswith("/") for name in zf.namelist())`.
- **Verification**: Verified in `test_security_audit.py`.

### C. Offline Cryptographic Integrity & Tamper Detection
- **Threat**: Direct modification or deletion of evidence files or audit records in SQLite.
- **Defense**: 
  1. Evidence SHA-256 is computed before pipeline execution.
  2. Every pipeline action is recorded in an append-only cryptographic ledger (`AuditLog`) where each row hash is $H(\text{prev\_hash} \parallel \text{action} \parallel \text{payload} \parallel \text{evidence\_hash})$.
  3. `audit_svc.verify_chain()` scans the entire sequence from root to leaf, detecting row deletions, payload mutations, and content edits.
- **Verification**: `test_audit_chain.py` (10/10 PASS).

### D. Subprocess & Command Injection
- **Threat**: Passing unsanitized user filenames or metadata strings to shell interpreters during FFmpeg/ffprobe execution.
- **Defense**: All `subprocess.run()` calls use explicit argument lists without `shell=True`. Arguments are passed directly to execve syscalls.
- **Verification**: Hostile filenames with `;rm -rf /` execute safely without executing secondary commands.

### E. Template & Cross-Site Scripting (XSS) Prevention
- **Threat**: OCR-extracted entities or case metadata injecting `<script>` tags into generated PDF reports or frontend DOM.
- **Defense**:
  1. Jinja2 templates use `select_autoescape(["html"])`, automatically encoding `<` to `&lt;` and `>` to `&gt;`.
  2. React DOM automatically escapes interpolated variables.
- **Verification**: Verified in `test_security_audit.py`.

### F. Offline-First Model Execution & Supply Chain Safeguards
- **Threat**: Network telemetry calls leaking case hashes or evidence data to external servers.
- **Defense**:
  1. Enforced environment variables `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`.
  2. Pinned Swin-ViT model weights with hardcoded commit SHA-256.
  3. Zero runtime network dependencies.
- **Verification**: All tests run with complete local isolation.

---

## 2. Security Test Matrix

| Check | Target Surface | Test File | Result |
| :--- | :--- | :--- | :--- |
| **Path Traversal Sanitization** | Upload API / File IO | `test_security_audit.py` | **PASS** |
| **Upload Ceiling Limit** | 300 MB Ingestion Gate | `test_security_audit.py` | **PASS** |
| **ZipSlip Defense** | Packet ZIP Exporter | `test_security_audit.py` | **PASS** |
| **Audit Ledger Tamper Detection** | Cryptographic Chain | `test_security_audit.py` | **PASS** |
| **HTML / PDF XSS Escaping** | WeasyPrint Templates | `test_security_audit.py` | **PASS** |
| **SQL Injection Sanitization** | SQLAlchemy ORM | `test_security_audit.py` | **PASS** |
| **Zero Stack Trace Leakage** | 4xx / 5xx Handlers | `test_features.py` | **PASS** |
| **C2PA Signature Integrity** | X.509 Trust Validator | `test_c2pa.py` | **PASS** |
| **Acoustic Gating Safety** | Audio Waveform Decoder | `test_audio_forensics.py` | **PASS** |
| **Memory / Flat Image Stability** | Spatial False-Color Overlays | `test_failure_modes.py` | **PASS** |
