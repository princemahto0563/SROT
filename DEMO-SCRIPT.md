# SROT — live demonstration script

**Team LogicaLoom · PS-4, AI-Generated Media Detection & Source Tracing**

Target length **6 minutes**. Everything below is computed live; there are no
pre-recorded results and no fixture data in the frontend.

## Before you start

```bash
cd backend && python seed.py --reset && uvicorn app.main:app --port 8077
cd frontend && npm run dev          # http://127.0.0.1:5177
```

Leave the console on the **Case Dashboard** with `CASE-2026-001` loaded and no
evidence uploaded yet. Have the file manager open at
`data/evidence/_to_upload/`.

---

## 0 · The problem (20 seconds)

> "A video is circulating. It promises guaranteed returns. By the time it reaches
> the complainant it has been forwarded so many times that the metadata is gone,
> the filename says nothing, and it was screen-recorded off someone else's phone.
> The question a station gets is: *who put this out?*"

---

## 1 · Intake — the integrity record comes first (40 s)

**Evidence Intake** → drag in `WhatsApp_Video_2026-08-17_forwarded.mp4`.

Point at, in order:

- SHA-256 appears **before** any analysis stage starts running
- the seven stages progressing live
- in the evidence viewer: **EXIF fields: None present**, **No C2PA manifest found**

> "Nothing in this file tells us where it came from. Everything from here is
> recovered from the pixels."

---

## 2 · Analysis, Evidence State & Visual Traces (90 s)

**Forensic Analysis** (`/analysis`).

Point at, in order:

1. **Investigation Pipeline Stepper**:
   - Shows live progress across the 10-stage workstation workflow (`INTAKE` → `HASH` → `SIGNALS` → `NEURAL` → `RECAPTURE` → `TRACES` → `STRESS` → `GRAPH` → `PACKET`).
2. **Forensic Decision Transparency Assessment (The 7 Core Judicial Inquiries)**:
   - *Headline & Evidence State*: `CONSISTENT` with `STRONG_CONSISTENCY` (or `PARTIALLY_CORROBORATED` with `MIXED`).
   - *Evidence State Reasoning*: Dynamic narrative explaining *why* the state was assigned (e.g. Swin neural score interaction with static interface rows).
   - *7 Answers Grid*: Target of analysis, Primary observed findings, Neural score semantics (`MODEL_SCORE` disclaimer), Corroborating signals, Disagreements & safeguards, Operational limitations, and Recommended next actions.
3. **Explicit Evidence Matrix**:
   - Source-by-source table (`Sensor Noise`, `DCT Benford`, `Display Recapture`, `Perceptual Origin`, `Neural ViT`, `Container Metadata`, `Image Quality`).
   - Shows raw observation, signal strength, status, and scientific limitations.
4. **Side-by-Side Spatial Forensic Trace Inspector**:
   - Toggle **Side-by-Side (2-Up)**: Original Reference Frame on the left vs False-Color Heatmap on the right.
   - Switch between **Sensor Noise Residual** (Viridis), **Error Level Analysis (ELA)** (Inferno), and **High-Frequency Gradient** (Turbo).
   - Read the dual panels: *What this visualization can reveal* vs *What this visualization cannot prove*.
5. **Deterministic Case Replay Verification**:
   - Click **"Verify case reproducibility"**.
   - Watch live re-execution across raw disk bytes; show the live **Comparison Matrix** proving **100% REPRODUCIBLE** with per-signal $\Delta$ matching stored DB records.

> "Every single claim in SROT is accountable. We do not just show an AI score: we show the physical sensor noise, the compression physics, the side-by-side false-color trace, and we let any judge re-execute the pipeline to verify 100% mathematical reproducibility on the spot."

**AI-Synthetic Signal** (`/neural`).

- Point at **Model AI-synthetic score: 72.1%** (`MODEL_SCORE`, not probability).
- Point at **Forensic Safeguard — Screenshot Caution**:
  *"Model result requires caution: screenshot/recaptured imagery may produce elevated synthetic-image scores."*
- Point at the visible **Model Scope & Limitations Notice**:
  *"This model is designed primarily for AI-generated artistic imagery and is not a standalone deepfake detector."*
- Point at the **Model Provenance**: `umm-maybe/AI-image-detector`, Architecture: Swin-ViT, License: `CC BY-ND 4.0`, Device: Apple MPS GPU.

> "We run real inference on device, but we disclose the model's exact boundaries:
> it was trained on 2022-era artistic imagery, and it triggers on screenshots.
> SROT automatically flags that caution rather than claiming proof."

---

## 3 · Origin trace — the core result (70 s)

**Origin Trace**.

- Five matches, ordered by first observation, **4-day propagation span**
- The earliest is `forum_post_8841` at 87.5% — while `@chd_alerts_now` scores 90.6%

> "Note the earliest copy is *not* the most similar one. We order by when a copy
> was observed, not by how much we like the number."

- Point at **Threshold calibration**

> "This threshold was measured, not chosen. True derivatives land at 6–8 bits,
> unrelated clips at 18–22. Fourteen sits in the gap. `calibrate.py` reproduces
> that in a minute, and refuses to recommend a threshold if the two populations
> ever overlap."

- Scroll to **Attribution ceiling**

> "Steps 1 to 4 are ours. Step 5 onward — subscriber details, IP records, the
> person — needs a legal request. We stop there and we say so on screen."

---

## 4 · Recapture — the differentiator (60 s)

**Recapture Forensics**.

- HIGH likelihood; letterbox top 22 px / bottom 150 px measured; static bands 121 rows
- The recovered candidate handle

> "The forward was screen-recorded, so the interface came with it. That band is
> static across every frame while the content moves — that is what we measure.
> Then we OCR it."

- Point at the candidate: `@sourcealpha0Ol`

> "And look at the reading — a zero read as an O. We report it as a **candidate
> that requires human verification**, with its confidence, its frame and its pixel
> box. A tool that quietly cleaned that up to a plausible-looking handle would be
> lying to an investigating officer."

---

## 5 · Identifiers and graph (50 s)

**OCR & Identifiers** — click the UPI row; the box lands exactly on the text in
the frame.

> "UPI, phone, URL — recovered from inside the video, each with the frame,
> the coordinates and the OCR confidence. These are *media-derived identifiers*.
> We do not resolve who owns them; that is a bank and a legal request."

**Investigation Graph** — click the evidence node.

> "Corpus copies, evidence, frames, extraction steps, identifiers. Every edge is
> labelled observed or inferred, and every node records the method that produced it."

---

## 6 · Cross-case and stress test (55 s)

**Cross-Case Links** — one match against `CASE-2026-002`.

> "Same media, different case, found through a department-level fingerprint ledger.
> The wording is *potential campaign relationship* — not *same person*."

**Laundering Stress Test** — point at the finished run.

> "Twelve real FFmpeg variants, re-scored through the identical code path. The
> assessment holds through 360p and 400 kbps. And here —"

- Point at **Horizontal mirror · 68.75% · reliable = false**

> "— mirroring defeats our own perceptual fingerprint. The system reports its own
> failure mode rather than hiding it. That is the difference between a demo and a
> tool an officer can trust."

---

## 7 · Audit, Court Packet & Executive Dossier (50 s)

**Audit Trail** — chain verified, 150+ entries.

> "Hash-linked and append-only. `test_audit_chain.py` edits a row, deletes a row,
> and proves the check catches both and names the entry."

**Court Packet** — generate, open the single-file **Executive Forensic Dossier (PDF)**.

> "For judges and senior investigators, SROT renders a consolidated single-file
> Executive Forensic Dossier. It packs the 7 Judicial Inquiries, Evidence Matrix,
> multi-stream physical findings, Section 18 Replay Verification, and cryptographic
> SHA-256 seal into a court-ready brief."

- Point at the **Report consistency check**:

> "Database, API and rendered PDF, field by field. They agree because all three
> are rendered from one canonical payload in `report.py`."

**Adversarial Benchmark** (`/benchmark`):

> "Finally, we maintain a 27-sample technical test bench inside the application.
> It openly displays our precision (88.9%), recall (80.0%), and intentional failure
> modes under heavy compression so judges can see our exact empirical boundaries."

---

## 8 · Close (15 s)

> "Strip the metadata, forward the video ten times, record it off another screen —
> SROT recovers the pixels, isolates the physical noise, traces the earliest copy,
> extracts the identifiers, and leaves a verifiable cryptographic paper trail.
> It tells the officer what is there, what is not, and where automated analysis stops."

---

## If a judge asks

**"What's your accuracy?"**
> "We don't publish one, because we have no labelled operational corpus to measure
> it against and a number without that would be fabricated. What we do publish is a
> measured detection threshold for the origin trace, and a stress test that shows
> where the assessment stops holding."

**"What model is integrated and what are its limits?"**
> "We evaluated three models locally (`umm-maybe/AI-image-detector`, `Organika/sdxl-detector`,
> and `SigLIP2`). We selected `umm-maybe` (Vision Transformer, CC BY-ND 4.0) because it is stable
> and legally clear, but we explicitly restrict its scope to an **AI-Synthetic Image Signal**,
> not a universal deepfake detector. Our local tests proved it triggers elevated scores on UI screenshots,
> so SROT's pipeline couples it with our Recapture Forensics engine to warn investigators whenever
> an input is a screenshot or screen recording."

**"Is the corpus real?"**
> "No, and it is flagged synthetic in every view and every document. The corpus
> items are real files generated locally by `seed.py`, so the matching is real
> computation — but they are not scraped from any platform, and SROT performs no
> live social-media collection."

**"What if the media has no interface band, no text and no corpus match?"**
> "Then the screens say so: *attribution cannot be established*, *no reliable source
> handle recovered*, *no text extracted*. Every panel has an honest empty state, and
> the limitations section of the report is derived from what actually happened in
> that run."
