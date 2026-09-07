# SROT — file manifest

Every source and configuration file in the package, what it does, and whether the
running application needs it.

---

## Entry points

| Role | Path | Command |
|---|---|---|
| **Run script** | `run.sh` | `./run.sh --reset` |
| **Backend entry** | `backend/app/main.py` (FastAPI app object `app`) | `python -m uvicorn app.main:app --port 8077` |
| **Frontend entry** | `frontend/src/main.tsx` → `frontend/index.html` | `npm run dev` |
| **Database entry** | `backend/app/db.py` (`init_db()`, engine, `SessionLocal`) | created automatically on first start |
| **Demo data entry** | `backend/seed.py` | `python seed.py --reset` |

The database file itself is `data/srot.db`, created at run time. It is **not** in the
package — `seed.py` builds it.

---

## Root

| Path | Purpose | Runtime? |
|---|---|---|
| `run.sh` | One-command launcher: prerequisite check, venv, npm install, seed, both services, clean shutdown | **YES** |
| `README.md` | macOS setup, running, testing, troubleshooting, architecture | NO (docs) |
| `MODEL-EVALUATION.md` | Phase 2 neural detector fitness review, local benchmark observations, CC BY-ND 4.0 license, operational safeguards | NO (docs) |
| `FINAL-VERIFICATION.md` | Complete forensic audit, model provenance, test results, and ZIP verification | NO (docs) |
| `PROJECT-DEPENDENCIES.md` | Dependency and model audit | NO (docs) |
| `FILE-MANIFEST.md` | This file | NO (docs) |
| `DEMO-SCRIPT.md` | 6-minute live demonstration script and judge Q&A | NO (docs) |
| `.gitignore` | Excludes `data/`, `node_modules/`, `.venv/`, caches | NO |

---

## Backend — application

| Path | Purpose | Runtime? |
|---|---|---|
| `backend/app/__init__.py` | Package marker | **YES** |
| `backend/app/main.py` | FastAPI app; all 30 endpoints; global exception handler that never leaks stack traces | **YES** |
| `backend/app/pipeline.py` | Seven-stage orchestration (INGEST → ANALYSIS → TRACE → OCR → RECAPTURE → GRAPH → LEADS); shared scoring path for evidence and stress variants | **YES** |
| `backend/app/models.py` | 21 SQLAlchemy models; every derived row records method, source evidence and confidence | **YES** |
| `backend/app/db.py` | SQLite engine, session factory, data directories, `init_db()` | **YES** |

There is no separate `schemas.py`: responses are built as explicit dicts in
`main.py` so the wire format is visible at the endpoint, and no migration
framework — SQLite tables are created by `Base.metadata.create_all()`.

## Backend — services

| Path | Purpose | Runtime? |
|---|---|---|
| `backend/app/services/__init__.py` | Service package exports | **YES** |
| `backend/app/services/integrity.py` | Filename sanitisation (path-traversal defence), SHA-256, MIME/type allow-list, 300 MB upload cap | **YES** |
| `backend/app/services/mediainfo.py` | ffprobe/PIL container facts, EXIF, JPEG quantization tables, C2PA marker scan | **YES** |
| `backend/app/services/frames.py` | Bounded FFmpeg keyframe sampling, frame numbering, audio extraction | **YES** |
| `backend/app/services/neural.py` | Phase 2 local neural classifier (`umm-maybe/AI-image-detector`, ViT-Base, CC BY-ND 4.0); frame-level inference on Apple MPS/Metal, bounded sampling, median aggregation | **YES** |
| `backend/app/services/signals.py` | The measured forensic ensemble: recompression, DCT/Benford, noise residual, blockiness, high-frequency energy, temporal continuity, metadata coherence, C2PA, neural signal. Aggregation formula and `neural_detector_available()` | **YES** |
| `backend/app/services/fingerprint.py` | Multi-view perceptual hashing, the measured match threshold and corroboration rule (`qualifies()`), similarity computation | **YES** |
| `backend/app/services/ocr.py` | Multilingual OCR (per-language passes), preprocessing variants, entity patterns (UPI/WALLET/URL/HANDLE/PHONE/AMOUNT/TIME/DATE), script detection | **YES** |
| `backend/app/services/recapture.py` | Letterbox geometry, static interface bands, FFT moiré, UI-region OCR handle recovery | **YES** |
| `backend/app/services/stress.py` | 12 FFmpeg laundering variants, reliability assessment, boundary derivation | **YES** |
| `backend/app/services/casebuild.py` | Investigation graph (semantic column layout), timeline, deterministic lead ranking, attribution ceiling, `rebuild_case_views()` | **YES** |
| `backend/app/services/audit.py` | Hash-linked append-only audit chain; `canonical_ts()`; `verify_chain()` distinguishing content edits from broken links | **YES** |
| `backend/app/services/cross_signal.py` | Cross-signal forensic assessment layer & explicit Evidence Matrix construction | **YES** |
| `backend/app/services/quality.py` | Pre-analysis image quality gating (resolution, Laplacian blur, dynamic range, blockiness, noise floor) | **YES** |
| `backend/app/services/visual_trace.py` | Spatial forensic trace generation (noise residual, ELA, high-frequency gradient maps) | **YES** |
| `backend/app/services/c2pa_trust.py` | Offline-first C2PA provenance validation with X.509 certificate parsing and trust anchors | **YES** |
| `backend/app/services/audio_forensics.py` | Acoustic and spectral physical measurements (RMS, ZCR, silence gating, spectral flatness, pitch jitter) | **YES** |
| `backend/app/services/replay.py` | Deterministic case replay and mathematical reproducibility verification engine | **YES** |
| `backend/app/services/report.py` | `collect()` canonical payload → 6 Jinja2 documents → WeasyPrint PDFs → ZIP; Executive Forensic Dossier | **YES** |
| `backend/app/services/fonts.py` | Cross-platform TrueType discovery for FFmpeg `drawtext` (macOS/Linux) | **YES** (seeding) |
| `backend/app/services/jsonsafe.py` | Coerces NumPy scalars, bytes and datetimes before they reach JSON columns | **YES** |

## Backend — scripts and tests

| Path | Purpose | Runtime? |
|---|---|---|
| `backend/requirements.txt` | Pinned Python dependencies + system package notes | **YES** (install) |
| `backend/seed.py` | Generates the **SYNTHETIC DEMO DATA** with FFmpeg and registers it | **YES** (demo) |
| `backend/calibrate.py` | Measures the perceptual-hash match rule against true-derivative and control populations; fails if they do not separate | NO (verification) |
| `backend/eval_models.py` | Empirical model fitness harness evaluating candidate architectures | NO (evaluation) |
| `backend/e2e.py` | End-to-end walk of the whole pipeline against the live API | NO (test) |
| `backend/test_features.py` | 30 checks: stress test, court packet, hash verify, consistency, timeline, leads, audit, failure states, filename fuzzing | NO (test) |
| `backend/test_audit_chain.py` | Proves the audit chain detects content edits, payload edits and deletions | NO (test) |
| `backend/test_c2pa.py` | 10-check test suite for offline C2PA trust validation across all 7 statuses | NO (test) |
| `backend/test_audio_forensics.py` | 11-check test suite for acoustic physical extraction and pitch jitter | NO (test) |
| `backend/test_security_audit.py` | 12-check test suite for path traversal, sanitization, XSS escaping, ZipSlip | NO (test) |
| `backend/adversarial_benchmark.py` | Comprehensive 27-sample adversarial benchmark evaluating the full multi-stream pipeline | NO (benchmark) |
| `backend/replay_case.py` | Deterministic case replay and forensic reproducibility auditor | **YES** (audit) |
| `backend/test_cross_signal.py` | Unit tests for Evidence-State Model and signal consistency detection | NO (test) |
| `backend/test_quality.py` | Unit tests for physical image quality gating & reliability bounds | NO (test) |
| `backend/test_visual_trace.py` | Unit tests for spatial trace generation (noise residual, ELA, gradient) | NO (test) |
| `backend/test_failure_modes.py` | 11-surface failure injection & safe degradation test suite | NO (test) |
| `backend/test_replay.py` | Unit test verifying mathematical reproducibility on stored evidence | NO (test) |
| `backend/inspect_data.py` | 481 data-integrity checks — recomputes scores and hashes, verifies files exist, scans for placeholder/over-claiming text | NO (test) |

---

## Frontend — configuration

| Path | Purpose | Runtime? |
|---|---|---|
| `frontend/package.json` | Dependencies and scripts (`dev`, `build`, `lint`, `preview`) | **YES** (install) |
| `frontend/package-lock.json` | Exact dependency tree for reproducible installs | **YES** (install) |
| `frontend/vite.config.ts` | Dev server port, `/api` proxy to the backend, single-file build option | **YES** |
| `frontend/tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json` | TypeScript project references and compiler options | **YES** (build) |
| `frontend/tailwind.config.js` | Design tokens — the whole colour system | **YES** (build) |
| `frontend/postcss.config.js` | Tailwind/autoprefixer pipeline | **YES** (build) |
| `frontend/.oxlintrc.json` | Lint rules | NO |
| `frontend/.gitignore` | Excludes `node_modules/`, `dist/` | NO |
| `frontend/index.html` | HTML shell, favicon link, page title | **YES** |

## Frontend — source

| Path | Purpose | Runtime? |
|---|---|---|
| `frontend/src/main.tsx` | React root mount | **YES** |
| `frontend/src/App.tsx` | Router, session provider, 12 routes | **YES** |
| `frontend/src/index.css` | Tailwind layers, component classes, print styles, React Flow theme | **YES** |
| `frontend/src/lib/api.ts` | Typed API client, `useApi`/`usePolling` hooks, payload types, formatters | **YES** |
| `frontend/src/state/session.tsx` | Case and evidence selection derived from the live API | **YES** |
| `frontend/src/components/Shell.tsx` | Sidebar, navigation, case/evidence pickers, live backend status | **YES** |
| `frontend/src/components/ui.tsx` | Panel, Chip, Stat, Notice, Meter, Table, Field, Button, Skeleton, EmptyState, ErrorState, `Async` | **YES** |
| `frontend/src/components/guards.tsx` | Shared "no evidence / running / failed" states | **YES** |
| `frontend/src/components/Boundary.tsx` | Error boundary so one screen's failure cannot blank the console | **YES** |
| `frontend/src/screens/Dashboard.tsx` | Case overview, evidence table, leads, audit-chain status | **YES** |
| `frontend/src/screens/Intake.tsx` | Upload, live stage progress, evidence viewer | **YES** |
| `frontend/src/screens/Analysis.tsx` | Assessment, signal agreement/dissent, signal breakdown, frame heatmap, limitations | **YES** |
| `frontend/src/screens/Neural.tsx` | AI-Synthetic Image Signal: frame-level scores, Vision Transformer provenance, CC BY-ND 4.0 license, screenshot caution safeguard, multi-signal view | **YES** |
| `frontend/src/screens/OriginTrace.tsx` | Earliest known copy, corpus matches, threshold calibration, attribution ceiling | **YES** |
| `frontend/src/screens/Recapture.tsx` | Recapture likelihood, recovered handle candidates, geometry measurements | **YES** |
| `frontend/src/screens/Entities.tsx` | OCR identifiers with bounding boxes drawn on the real frame | **YES** |
| `frontend/src/screens/Graph.tsx` | Investigation graph (React Flow), node inspector, legend | **YES** |
| `frontend/src/screens/CrossCase.tsx` | Cross-case fingerprint matches | **YES** |
| `frontend/src/screens/Stress.tsx` | Laundering stress test, degradation chart, variant table | **YES** |
| `frontend/src/screens/Timeline.tsx` | Case timeline and ranked leads with cited reasons | **YES** |
| `frontend/src/screens/Audit.tsx` | Hash-linked audit chain with expandable entries | **YES** |
| `frontend/src/screens/Packet.tsx` | Court packet, hash verification, report consistency check | **YES** |

## Frontend — assets

| Path | Purpose | Runtime? |
|---|---|---|
| `frontend/public/favicon.svg` | Browser tab icon | **YES** |
| `frontend/public/icons.svg` | SVG sprite | **YES** |
| `frontend/src/assets/hero.png` | Cover image asset | NO (not imported by any screen) |
| `frontend/src/assets/vite.svg` | Vite default asset | NO |
| `frontend/DEMO-SCRIPT.md` | Demonstration script (duplicate of the root copy, kept beside the UI) | NO |
| `frontend/README.md` | Frontend conventions and screen/endpoint map | NO |

---

## Deliberately excluded from the package

| Path | Why | How to recreate |
|---|---|---|
| `data/` | Generated media, database, frames, stress variants, packets (~64 MB) | `python backend/seed.py --reset`, then run the pipeline |
| `backend/.venv/` | Machine- and architecture-specific virtualenv | `run.sh` creates it, or `pip install -r backend/requirements.txt` |
| `frontend/node_modules/` | ~200 MB of platform-specific packages | `npm install` (pinned by `package-lock.json`) |
| `frontend/dist/` | Build output | `npm run build` |
| `**/__pycache__/`, `*.pyc` | Python bytecode | regenerated automatically |
| Logs, `.DS_Store`, editor folders | Not source | — |
