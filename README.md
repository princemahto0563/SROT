# SROT — Source Tracing & Recapture Origin Toolkit

**Team LogicaLoom · Chandigarh Police National Hackathon 2026 · Problem Statement 4**
*AI-Generated Media Detection & Source Tracing*

SROT is an offline-first forensic console for investigating a piece of media whose
metadata has been stripped and whose filename has been changed. It measures what can
actually be measured, traces the earliest copy it can find, reads identifiers out of
the pixels, and stops precisely where automated analysis has to hand over to a legal
request or a human investigator.

**It never claims to know whether media is real or fake, never identifies a person,
and never asserts legal admissibility.**

---

## 1 · Prerequisites

Written and verified for **macOS on Apple Silicon (M1/M2/M3/M4), zsh, Homebrew**.
It also runs on Linux; where the commands differ, both are given.

If you do not have Homebrew:

```zsh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

On Apple Silicon, Homebrew installs to `/opt/homebrew`. Make sure it is on your PATH
(the installer prints this; add it to `~/.zprofile` if needed):

```zsh
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

### Install everything in one command

```zsh
brew install python@3.12 node ffmpeg tesseract tesseract-lang pango gdk-pixbuf libffi poppler
```

That single line covers sections 2–7 below. The rest of this section explains what
each piece is for, in case you want to install them individually.

### 2 · Python

**Required: 3.10 or newer.** Verified on 3.11; 3.12 and 3.13 also work.

```zsh
brew install python@3.12
python3 --version          # expect Python 3.12.x
```

macOS ships an older system Python. Homebrew's `python3` takes precedence once
Homebrew is on your PATH. `run.sh` creates its own virtualenv, so nothing is
installed into your system Python.

### 3 · Node.js

**Required: 20 or newer.** Verified on 22.

```zsh
brew install node
node -v                    # expect v20.x or newer
npm -v
```

### 4 · FFmpeg

Used for keyframe sampling, generating the demonstration media, and producing the 12
laundering stress-test variants. `ffprobe` comes with it.

```zsh
brew install ffmpeg
ffmpeg -version
ffprobe -version
```

### 5 · Tesseract OCR

The OCR engine behind identifier extraction and interface-band handle recovery.

```zsh
brew install tesseract
tesseract --version
```

### 6 · Hindi OCR (Devanagari)

### 7 · Punjabi OCR (Gurmukhi)

Both ship in the same Homebrew package, which installs all Tesseract language data:

```zsh
brew install tesseract-lang
tesseract --list-langs | grep -E '^(eng|hin|pan)$'
```

You should see `eng`, `hin` and `pan`. If `tesseract-lang` is too large for your
liking, you can instead drop just the three `.traineddata` files into
`/opt/homebrew/share/tessdata/`.

Hindi and Punjabi are **optional** — without them OCR runs in English/Latin only,
and the console shows exactly which languages are installed rather than pretending.

<details>
<summary>Linux (Debian/Ubuntu) equivalent for sections 2–7</summary>

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip nodejs npm \
     ffmpeg tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin tesseract-ocr-pan \
     fonts-dejavu-core libpango-1.0-0 libpangoft2-1.0-0 libcairo2 \
     libgdk-pixbuf-2.0-0 poppler-utils
```
</details>

### Additional macOS libraries

The court packet renders PDFs with WeasyPrint, which needs Pango:

```zsh
brew install pango gdk-pixbuf libffi
```

`poppler` (for `pdftotext`) is optional — it only enables one extra assertion in the
test suite, which skips itself and says so if poppler is absent.

### Verify your machine before going further

```zsh
cd SROT
./run.sh --check
```

This prints a tick or a fix-it command for every prerequisite and exits.

---

## 8–12 · Setup, database, demo data and running — one command

```zsh
cd SROT
chmod +x run.sh          # only needed once, if the executable bit was lost
./run.sh --reset
```

That command does all of the following, in order:

| Step | What happens |
|---|---|
| **8. Backend setup** | Creates `backend/.venv` and installs `backend/requirements.txt` (first run only, a few minutes) |
| **9. Frontend setup** | Runs `npm install` in `frontend/` (first run only, about a minute) |
| **10. Database initialisation** | Creates `data/srot.db` and all tables |
| **11. Demo data seeding** | Generates the synthetic media with FFmpeg and registers the corpus, both cases and all fingerprints |
| **12. Running** | Starts the backend, waits until it is healthy, starts the frontend, prints the URLs |

When it finishes you will see:

```
────────────────────────────────────────────────────────────
  SROT is running

    Console (open this):  http://127.0.0.1:5177
    Backend API:          http://127.0.0.1:8077
    API documentation:    http://127.0.0.1:8077/docs
    Health check:         http://127.0.0.1:8077/api/health

    Demo file to upload:  data/evidence/_to_upload/
    Press Ctrl-C to stop both services.
────────────────────────────────────────────────────────────
```

**Open http://127.0.0.1:5177 in your browser.** Press `Ctrl-C` in the terminal to
stop both services cleanly.

### Other run modes

```zsh
./run.sh                 # start both; seed only if the database is empty
./run.sh --reset         # rebuild the demonstration media and database first
./run.sh --backend       # backend only
./run.sh --frontend      # frontend only (expects a backend already running)
./run.sh --test          # run the whole verification suite and exit
./run.sh --check         # check prerequisites and exit
./run.sh --help
```

If a port is already in use, `run.sh` reports which process holds it and frees it.
To use different ports:

```zsh
SROT_BACKEND_PORT=9000 SROT_FRONTEND_PORT=9001 ./run.sh
```

### Manual setup, if you prefer not to use the script

```zsh
# backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python seed.py --reset
python -m uvicorn app.main:app --host 127.0.0.1 --port 8077

# frontend, in a second terminal
cd frontend
npm install
npm run dev
```

---

## 13 · Running tests

```zsh
./run.sh --test          # seeds, starts the backend, runs everything, exits
```

Or individually, with the backend already running:

```zsh
cd backend
source .venv/bin/activate

python calibrate.py              # measures the perceptual-hash match rule
python e2e.py                    # full 8-stage pipeline walk against live API
python test_features.py          # 30 checks across court packets, stress engine, APIs
python test_audit_chain.py       # proves the audit chain detects tampering (10/10)
python adversarial_benchmark.py  # 27-sample adversarial benchmark over entire pipeline
python test_failure_modes.py     # 11-surface failure injection & safe degradation
python test_cross_signal.py      # cross-signal evidence-state fusion unit tests
python test_quality.py           # image quality gating & reliability bounds unit tests
python test_visual_trace.py      # spatial forensic trace generation unit tests
python replay_case.py EV-CASE-2026-001-001 # deterministic case replay & reproducibility
python test_replay.py            # replay verification unit test
python inspect_data.py           # 380 data-integrity checks over the database
```

Each script prints what the system actually returned and exits non-zero on failure.

`calibrate.py` is the one worth watching: it builds two populations — true
derivatives of the seed media and unrelated control clips — and validates the
configured matching rule against both. **If the populations overlap, it fails and
refuses to recommend a threshold** rather than quietly widening one.

Expected results on a healthy install:

```
calibrate.py            Configured matching rule validated against both populations.
e2e.py                  8/8 stages completed
test_features.py        passed: 30   failed: 0
test_audit_chain.py     ALL AUDIT CHAIN CHECKS PASSED (10/10)
adversarial_benchmark.py 27/27 adversarial samples evaluated
test_failure_modes.py   passed: 11   failed: 0
test_cross_signal.py    passed: 12   failed: 0
test_quality.py         passed: 9    failed: 0
test_visual_trace.py    passed: 10   failed: 0
test_replay.py          100% REPRODUCIBLE (PASS)
inspect_data.py         passed: 380  failed: 0
```

---

## 14 · Resetting demo data

```zsh
./run.sh --reset                     # wipe and rebuild everything
```

or:

```zsh
cd backend && source .venv/bin/activate && python seed.py --reset
```

`--reset` deletes `data/srot.db` and everything under `data/evidence`, `data/work`,
`data/corpus` and `data/packets`, then regenerates the demonstration media from
scratch with FFmpeg.

To wipe absolutely everything including installed dependencies:

```zsh
rm -rf data backend/.venv frontend/node_modules frontend/dist
./run.sh --reset
```

---

## 15 · Troubleshooting

**`./run.sh: permission denied`**
```zsh
chmod +x run.sh
```

**`zsh: command not found: brew`** — Homebrew is not on your PATH. See section 1.

**`ModuleNotFoundError: No module named 'weasyprint'` or a Pango error when
generating the court packet**
```zsh
brew install pango gdk-pixbuf libffi
rm -rf backend/.venv && ./run.sh --reset
```
Everything except the Court Packet screen works without Pango.

**`OSError: cannot load library 'libgobject-2.0-0'`** — same cause on Apple Silicon.
Confirm Homebrew's lib directory is visible:
```zsh
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_FALLBACK_LIBRARY_PATH
```
Add that line to `~/.zprofile` to make it permanent.

**`tesseract is not installed or it's not in your PATH`**
```zsh
brew install tesseract tesseract-lang
```

**OCR returns nothing, or the console shows only `eng`**
```zsh
tesseract --list-langs        # expect eng, hin, pan
brew install tesseract-lang
```
This is not a failure state — SROT reports which languages are available and does
not invent text it could not read.

**`No TrueType font found for rendering the demonstration media`**
macOS system fonts are normally discovered automatically. If not:
```zsh
export SROT_FONT="/System/Library/Fonts/Supplemental/Arial Bold.ttf"
./run.sh --reset
```

**Port 8077 or 5177 already in use** — `run.sh` frees it automatically. If it cannot:
```zsh
lsof -ti tcp:8077 | xargs kill
```

**The console says "Backend offline"** — the backend is not running or is on a
different port. Check `curl http://127.0.0.1:8077/api/health`. The console never
falls back to sample data; an offline backend always shows as offline.

**`calibrate.py` fails with "RE-CALIBRATION REQUIRED"** — this is the script working
as intended. It means the measured populations no longer separate on your machine's
FFmpeg encoding. Report the printed numbers rather than widening the threshold.

**Apple Silicon `pip install` fails building a wheel** — make sure you are on
Homebrew Python, not the system one:
```zsh
which python3        # expect /opt/homebrew/bin/python3
```

**Xcode command line tools missing**
```zsh
xcode-select --install
```

---

## 16 · Offline usage

SROT makes **no outbound network calls at run time**. It downloads no model, calls no
cloud inference service, scrapes no platform, and performs no subscriber, bank or
telecom lookup.

Network access is needed **once**, at install time, for `pip install` and
`npm install`. After that you can disconnect entirely:

```zsh
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1     # safe once model weights are cached locally
./run.sh
```

The only network traffic in normal operation is the frontend dev server proxying
`/api` to `127.0.0.1:8077` on your own machine.

See `MODEL-EVALUATION.md` for the empirical model fitness review, and `PROJECT-DEPENDENCIES.md`
for the full software audit.

---

## 17 · Project architecture

```
SROT/
├── run.sh                      one-command launcher
├── README.md                   this file
├── MODEL-EVALUATION.md         Phase 2 neural model evaluation & fitness review
├── PROJECT-DEPENDENCIES.md     dependency + model audit
├── FILE-MANIFEST.md            every file, purpose, runtime-required flag
├── DEMO-SCRIPT.md              6-minute demonstration script
│
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py             FastAPI application — 30 endpoints
│   │   ├── pipeline.py         8-stage orchestration (including NEURAL)
│   │   ├── models.py           21 SQLAlchemy models
│   │   ├── db.py               SQLite engine + data directories
│   │   └── services/
│   │       ├── integrity.py    filename sanitisation, SHA-256, upload limits
│   │       ├── mediainfo.py    ffprobe/PIL facts, EXIF, C2PA marker scan
│   │       ├── frames.py       bounded keyframe sampling
│   │       ├── neural.py       Phase 2 local Vision Transformer inference
│   │       ├── signals.py      the measured forensic signal ensemble
│   │       ├── fingerprint.py  multi-view pHash + calibrated match rule
│   │       ├── ocr.py          multilingual OCR + identifier extraction
│   │       ├── recapture.py    letterbox / static-band / moiré + UI-region OCR
│   │       ├── stress.py       12 FFmpeg laundering variants
│   │       ├── casebuild.py    graph, timeline, leads, attribution ceiling
│   │       ├── audit.py        hash-linked append-only audit chain
│   │       ├── report.py       one payload → six documents → ZIP
│   │       ├── fonts.py        cross-platform font discovery
│   │       └── jsonsafe.py     NumPy/bytes coercion for JSON columns
│   ├── seed.py                 SYNTHETIC DEMO DATA generator
│   ├── eval_models.py          3-candidate model fitness evaluation harness
│   ├── calibrate.py            measures the match rule
│   ├── e2e.py                  end-to-end pipeline test
│   ├── test_features.py        30 workflow + failure-state checks
│   ├── test_audit_chain.py     tamper-detection proof
│   └── inspect_data.py         180+ data-integrity checks
│
├── frontend/
│   ├── package.json / package-lock.json
│   ├── vite.config.ts          dev server + /api proxy
│   ├── tailwind.config.js      design tokens
│   ├── tsconfig*.json
│   ├── index.html
│   ├── public/                 favicon, icon sprite
│   └── src/
│       ├── main.tsx            React root
│       ├── App.tsx             router + session provider
│       ├── index.css           Tailwind layers and component classes
│       ├── lib/api.ts          typed API client + hooks
│       ├── screens/
│       │   ├── Dashboard.tsx
│       │   ├── Intake.tsx
│       │   ├── Analysis.tsx
│       │   ├── Neural.tsx      AI-Synthetic Image Signal screen
│       │   ├── OriginTrace.tsx
│       │   ├── Recapture.tsx
│       │   ├── Entities.tsx
│       │   ├── Graph.tsx
│       │   ├── CrossCase.tsx
│       │   ├── Stress.tsx
│       │   ├── Timeline.tsx
│       │   ├── Audit.tsx
│       │   └── Packet.tsx
│       ├── state/session.tsx   case / evidence selection
│       ├── components/         Shell, ui, guards, Boundary
│       └── screens/            the 12 screens
│
└── data/                       created at run time — not in the package
    ├── srot.db                 SQLite database
    ├── evidence/               immutable originals
    ├── work/                   frames, stress variants
    ├── corpus/                 synthetic reference media
    └── packets/                generated court packets
```

**Data flow:** upload → SHA-256 before analysis → seven background stages, each
writing its own rows → every API view and every generated PDF renders from a single
`report.collect()` payload, so the console, the database and the documents cannot
disagree. The `/consistency` endpoint proves this field by field.

---

## 18 · Feature overview

| Screen | What it does |
|---|---|
| **Case Dashboard** | Evidence list, corpus size, cross-case links, live audit-chain status, ranked leads |
| **Evidence Intake** | Upload with live 7-stage progress; SHA-256 computed before any analysis; evidence viewer showing measured container facts |
| **Forensic Analysis** | Eight measured signals, each expandable to raw numbers; supporting vs dissenting signals shown separately; frame-level heatmap; derived limitations |
| **Origin Trace** | Earliest known copy in the searched corpus, propagation span, the calibration data behind the match rule, and the attribution ceiling |
| **Recapture Forensics** | Letterbox geometry, static interface bands, FFT moiré response, and candidate source handles recovered from the interface by OCR |
| **OCR & Identifiers** | UPI, phone, URL and handle read from the pixels, each highlighted at the exact coordinates OCR returned |
| **Investigation Graph** | Corpus copies → evidence → frames → extraction → identifiers, every edge marked observed or inferred |
| **Cross-Case Links** | Department-level fingerprint ledger matches, worded as *potential campaign relationship* |
| **Laundering Stress Test** | 12 real FFmpeg variants re-scored through the identical path; reports its own failure modes |
| **Timeline & Leads** | Case timeline and ranked leads, each citing its evidence and stating its limitation |
| **Audit Trail** | Hash-linked append-only chain, verified live |
| **Court Packet** | Six pre-filled PDFs plus a ZIP; hash verification; field-by-field consistency check |

### What SROT will not say

Enforced in code and checked by `test_features.py` and `inspect_data.py`:

- No guaranteed real/fake classification, and no accuracy figure without measurement
- No identification of a person, subscriber, bank account or UPI owner
- Never "this is the original file" — only *earliest known copy in the searched corpus*
- The BSA §63 certificate reads *"Pre-filled draft for verification and signature by
  the investigating officer / relevant expert. Legal admissibility is determined by
  the court."*
- Unknown device fields read *"Not available / To be completed"* — never invented
- If no handle is recovered: *"Recapture indicators detected, but no reliable source
  handle recovered."*
- Absence of metadata or C2PA is recorded as an absence, never as evidence of manipulation

### Demonstration data

Everything in `data/` is **SYNTHETIC DEMO DATA**, generated locally by `seed.py`
with FFmpeg. It contains no real, private, confidential or unauthorised material and
no real person's data. Every corpus item is flagged `is_synthetic` in the database
and labelled as synthetic in the console and in every generated document.

The demonstration identifiers (`quickprofit.demo@upi`, `+91 98765 43210`,
`invest-demo.example`, `@sourcealpha01`) are fictional and use reserved or
clearly non-real values.

Because the corpus consists of **real media files** rather than seeded rows, every
similarity, OCR reading and recapture measurement SROT reports is genuinely computed
at run time. Nothing is hardcoded to make the demo work.
