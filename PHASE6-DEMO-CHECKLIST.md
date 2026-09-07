# SROT — Phase 6 Judge Demonstration Checklist (5–7 Minutes)

**Demonstration Goal**: Present SROT as a credible, transparent, offline-first digital media forensic workstation that empowers investigators with mathematical and physical evidence rather than uncalibrated "black box" declarations.

---

## ⏱️ Step-by-Step Demonstration Flow

| Time | Screen | Key Demonstration Actions | Explanatory Script Callout |
| :--- | :--- | :--- | :--- |
| **0:00 - 0:45** | **Case Dashboard** (`/`) | • Show Active Case (`CASE-2026-001`)<br>• Point out **100% OFFLINE** status & Apple MPS engine<br>• Show Audit Ledger (150+ verified entries)<br>• Switch case via dropdown to demonstrate multi-case capability | *"SROT is an autonomous forensic workstation operating 100% offline. Every action is recorded into an append-only, hash-linked cryptographic audit ledger."* |
| **0:45 - 1:30** | **Evidence Intake** (`/upload`) | • Ingest forwarded video sample<br>• Show SHA-256 computed **before** analysis begins<br>• Show container facts (codecs, resolution, fps) | *"Integrity is established at the threshold: the SHA-256 checksum is calculated prior to ingestion so the chain of custody begins immediately."* |
| **1:30 - 2:30** | **Forensic Analysis** (`/analysis`) | • Walk through the **7 Judicial Inquiries Grid**<br>• Explain Evidence State (`CONSISTENT` / `PARTIALLY_CORROBORATED`)<br>• Show Explicit Evidence Matrix<br>• Click **"Verify case reproducibility"** (Live Replay) | *"Notice SROT avoids dangerous binary claims like 'definitely fake'. Instead, it presents an Evidence Matrix mapping physical observations, neural scores, and limitations."* |
| **2:30 - 3:30** | **Spatial Visual Traces** (`/analysis#visual-traces`) | • Toggle **Side-by-Side (2-Up)** comparison<br>• Inspect Sensor Noise Residual (Viridis), ELA (Inferno), and Sobel Gradients (Turbo)<br>• Highlight "What it reveals" vs "What it cannot prove" callouts | *"Visual heatmaps localize physical discontinuities such as PRNU variance and re-compression blockiness with explicit scientific boundary callouts."* |
| **3:30 - 4:15** | **AI-Synthetic Signal & Recapture** (`/neural` & `/recapture`) | • View Swin-ViT signal (72.1%) with `MODEL_SCORE` semantics<br>• Show Recapture detection: static interface rows & letterbox borders<br>• Highlight false-positive safeguard | *"When an elevated neural score meets screenshot UI artifacts, SROT's safeguard activates to prevent wrongful manipulation flags."* |
| **4:15 - 5:00** | **Origin Trace & Stress Test** (`/origin` & `/stress`) | • Show origin propagation timeline against corpus<br>• Show calibrated 14-bit Hamming gap threshold<br>• Review 12 FFmpeg laundering variants and directional stability | *"Origin tracing establishes chronological propagation, while laundering stress testing proves the findings remain stable across recompression."* |
| **5:00 - 5:45** | **Investigation Graph** (`/graph`) | • Inspect direct (solid) vs inferred (dashed) edges<br>• Click SHA-256 Digest and Account Handle nodes<br>• Use contextual jump links | *"The investigation graph strictly partitions directly observed media facts from inferred associations."* |
| **5:45 - 6:30** | **Court Packet & Executive Dossier** (`/packet`) | • Download single-file **Executive Forensic Dossier (PDF)**<br>• Open and display Section 63 Certificate draft, technical annexure, and Section 18 Replay attestation | *"Finally, SROT generates court-ready documentation under Section 63 of the Bharatiya Sakshya Adhiniyam, pre-filled for human expert review."* |

---

## 🎯 Key Judge Talking Points

1. **Why SROT is different from standard AI image classifiers**:
   - Standard classifiers return an uncalibrated probability that fails under compression or screenshotting. SROT synthesizes independent physical measurements (PRNU, Benford, Blockiness, ELA) with a local Swin-ViT model, display recapture detection, and laundering stress validation.
2. **Deterministic Replay Guarantee**:
   - Any court or third-party expert can re-run SROT against the raw evidence bytes and reproduce the exact signal measurements ($\Delta = 0.00\%$).
3. **Strict Zero-Overclaiming Semantics**:
   - SROT never claims "100% fake" or "proves manipulation". It remains an objective, auditable decision-support workstation for law enforcement and judicial officers.
