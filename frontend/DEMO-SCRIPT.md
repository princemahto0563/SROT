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

## 2 · Analysis & Neural Signal — measured, and shown disagreeing (60 s)

**Forensic Analysis**.

- Read the assessment aloud exactly as written: *No strong manipulation indicators*
- Note that `neural_detector_loaded = true`: the weighted ensemble is augmented by a real local Vision Transformer.
- Expand **AI-synthetic image signal** — show the real measurement score (72.1%, w=1.2).
- Point at **Signals not indicating manipulation** — classical measurements that disagree with the neural score.

> "Averaging dissent away is how a forensic tool ends up misleading an investigation.
> We show every signal independently."

**AI-Synthetic Signal** (Click `/neural` in sidebar).

- Point at **Model AI-synthetic score: 72.1%**
- Point at **Forensic Safeguard — Screenshot Caution**:
  *"Model result requires caution: screenshot/recaptured imagery may produce elevated synthetic-image scores."*
- Point at the visible **Model Scope & Limitations Notice**:
  *"This model is designed primarily for AI-generated artistic imagery and is not a standalone deepfake detector."*
- Point at the **Model Provenance**: `umm-maybe/AI-image-detector`, Architecture: ViT-Base, License: `CC BY-ND 4.0`, Device: Apple MPS GPU.

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

## 7 · Audit and packet (45 s)

**Audit Trail** — chain verified, N entries.

> "Hash-linked and append-only. `test_audit_chain.py` edits a row, deletes a row,
> and proves the check catches both and names the entry."

**Court Packet** — generate, open the BSA §63 certificate.

> "Six documents. Read the header: *pre-filled draft for verification and signature
> by the investigating officer. Legal admissibility is determined by the court.*
> We never claim to make evidence admissible."

- Point at the **Report consistency check**

> "Database, API and rendered PDF, field by field. They agree because all three
> render from one payload — divergence is structurally impossible, not just
> unlikely."

---

## Close (20 s)

> "SROT does not tell you whether a video is fake. It tells you what was measured,
> how far the trail actually goes, where it stops, and exactly what a human has to
> verify next — with a document set an officer can carry into a courtroom and a
> stress test that publishes its own limits."

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
