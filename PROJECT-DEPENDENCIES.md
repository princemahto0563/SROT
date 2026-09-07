# SROT — dependency and model audit

Every import in the project was inspected and is accounted for below.
Versions are the ones this build was developed and verified against.

---

## Neural model status (Phase 2 Integration)

> **Phase 2 Neural Signal: `umm-maybe/AI-image-detector` (Swin-ViT Transformer)**

SROT integrates a real, local, offline pretrained Swin Transformer (`SwinForImageClassification` / Hierarchical Vision Transformer) for frame-level AI-synthetic image analysis.

- **Model ID**: `umm-maybe/AI-image-detector`
- **Pinned Revision**: `c7e223baf11bc40528af364ba7bdea030ef42f9e`
- **Source**: [https://huggingface.co/umm-maybe/AI-image-detector](https://huggingface.co/umm-maybe/AI-image-detector)
- **License**: **CC BY-ND 4.0** (Creative Commons Attribution-NoDerivatives 4.0 International; HF repo YAML tag displays `cc-by-4.0`)
- **License Notice**: Attribution required. Prohibits distribution of modified model weights. Review licensing prior to production or commercial deployment.
- **Product Role**: **AI-Synthetic Image Signal** (Forensic decision-support signal, NOT a universal deepfake detector)
- **Execution**: Local Apple MPS / Metal GPU (or CPU), fully offline once weights are cached locally.
- **Scope & Limitations**: Trained primarily on artistic AI imagery (Oct 2022 VQGAN+CLIP era); not trained on deepfake face-swaps or modern diffusion engines; known elevated scores on UI screenshots (mitigated by SROT's Screenshot Caution safeguard).

The API and health endpoints expose full model provenance:

```
GET /api/health           →  { "neural_detector_loaded": true, "neural_model": "AI-image-detector (Swin-ViT)", "neural_revision": "c7e223baf11bc40528af364ba7bdea030ef42f9e", "neural_license": "CC BY-ND 4.0", ... }
GET /api/system/model-status  →  { "architecture": "Swin Transformer (Hierarchical ViT) — SwinForImageClassification", "license": "CC BY-ND 4.0", "scope": "AI-synthetic/artistic image signal", ... }
```

**No audio manipulation detector is bundled.** SROT does not produce audio authenticity claims.

---

## Runtime platform

| Name | Version | Purpose | Required | Installation (macOS) | Offline |
|---|---|---|---|---|---|
| **Python** | 3.10+ (3.11/3.12/3.13 verified on 3.11) | Backend runtime | **Required** | `brew install python@3.12` | yes |
| **Node.js** | 20+ (verified on 22) | Frontend build and dev server | **Required** | `brew install node` | yes |
| **npm** | 10+ | Frontend package manager | **Required** | ships with Node | needs network for first `npm install` |

---

## System tools (not installable with pip)

| Name | Version | Purpose | Required | Installation (macOS) | Offline |
|---|---|---|---|---|---|
| **FFmpeg** | 6.x / 7.x | Keyframe sampling, demonstration-media generation, all 12 stress-test variants | **Required** — the pipeline cannot sample frames without it | `brew install ffmpeg` | yes |
| **ffprobe** | ships with FFmpeg | Container, codec, duration and encoder facts | **Required** | included in `ffmpeg` | yes |
| **Tesseract OCR** | 5.x | OCR engine behind identifier extraction and UI-band handle recovery | **Required** | `brew install tesseract` | yes |
| **Tesseract `eng`** | 5.x traineddata | English / Latin OCR — UPI IDs, URLs, handles, phone numbers | **Required** | included in `tesseract` | yes, local file |
| **Tesseract `hin`** | 5.x traineddata | Hindi (Devanagari) OCR | Optional — OCR degrades to Latin only, and the console shows which languages are installed | `brew install tesseract-lang` | yes, local file |
| **Tesseract `pan`** | 5.x traineddata | Punjabi (Gurmukhi) OCR | Optional — same degradation | `brew install tesseract-lang` | yes, local file |
| **Pango + GDK-PixBuf + libffi** | current | WeasyPrint's text/image rendering back end for the court-packet PDFs | **Required for the Court Packet screen only**; the rest of the app runs without it | `brew install pango gdk-pixbuf libffi` | yes |
| **poppler (`pdftotext`)** | current | Only used by `test_features.py` to verify the BSA §63 wording inside the PDF | Optional — the test skips this check and says so | `brew install poppler` | yes |
| **A TrueType font** | any | FFmpeg `drawtext` renders the demonstration media overlays | **Required for seeding** | macOS system fonts are used automatically; override with `SROT_FONT=/path/font.ttf` | yes |

Tesseract traineddata files live inside the Homebrew installation
(`/opt/homebrew/share/tessdata/`) and are read from local disk — no network access.

---

## Python packages (`backend/requirements.txt`)

| Name | Version | Purpose | Required | Installation | Offline |
|---|---|---|---|---|---|
| **fastapi** | 0.141.1 | HTTP API framework — all 30 endpoints | **Required** | pip | yes at run time |
| **uvicorn** | 0.46.0 | ASGI server that runs the backend | **Required** | pip | yes |
| **python-multipart** | 0.0.26 | Multipart parsing for evidence upload and hash verification | **Required** — uploads fail without it | pip | yes |
| **SQLAlchemy** | 2.0.52 | ORM over SQLite; the 21 models in `app/models.py` | **Required** | pip | yes |
| **pydantic** | 2.13.3 | Request/response validation (via FastAPI) | **Required** | pip | yes |
| **SQLite** | bundled with Python (`sqlite3`) | The entire datastore — one file at `data/srot.db` | **Required** | none, part of Python | yes |
| **opencv-python-headless** | 4.13.0.92 | Frame decoding, colour conversion, letterbox/static-band/moiré measurement, OCR preprocessing | **Required** | pip | yes |
| **numpy** | 2.4.4 | Numerical core for every forensic measurement | **Required** | pip | yes |
| **scipy** | 1.17.1 | FFT and signal processing for the high-frequency-energy and moiré measurements | **Required** | pip | yes |
| **Pillow** | 12.2.0 | Image IO, EXIF reading, JPEG quantization tables | **Required** | pip | yes |
| **ImageHash** | 4.3.2 | 64-bit pHash / dHash / wHash — Origin Trace and campaign linking | **Required** | pip | yes |
| **PyWavelets** | 1.9.0 | Required by ImageHash for `whash` | **Required** (transitive) | pip | yes |
| **pytesseract** | 0.3.13 | Python wrapper driving the Tesseract binary | **Required** | pip | yes |
| **networkx** | 3.6.1 | Investigation-graph layering and degree computation | **Required** | pip | yes |
| **Jinja2** | 3.1.6 | Templates for the six court-packet documents | **Required** | pip | yes |
| **weasyprint** | 69.0 | HTML → PDF for the court packet | **Required for the Court Packet screen** | pip (+ Pango system libs) | yes |
| **qrcode** | 8.2 | Evidence-reference QR code embedded in the certificate | **Required** by the packet templates | pip | yes |
| **torch** | 2.x | PyTorch runtime supporting Apple MPS (Metal GPU) acceleration | **Required for Neural analysis** | pip | yes (local cache) |
| **transformers** | 4.x | Hugging Face pipeline for Vision Transformer classification | **Required for Neural analysis** | pip | yes (local cache) |
| **requests** | 2.33.1 | Used **only** by the test scripts (`e2e.py`, `test_features.py`) | Optional for running the app; required to run the tests | pip | yes (localhost only) |

---

## Node packages (`frontend/package.json`)

| Name | Version | Purpose | Required | Installation | Offline |
|---|---|---|---|---|---|
| **react** / **react-dom** | 19.2.x | UI runtime | **Required** | npm | yes after install |
| **typescript** | ~6.0.2 | Type checking (`npx tsc -b`) | **Required** to build | npm | yes |
| **vite** | 8.2.x | Dev server (with the `/api` proxy) and production build | **Required** | npm | yes |
| **@vitejs/plugin-react** | 6.0.x | React fast refresh + JSX transform | **Required** | npm | yes |
| **react-router-dom** | 7.18.x | Hash routing across the 12 screens | **Required** | npm | yes |
| **@xyflow/react** | 12.11.x | Investigation-graph canvas | **Required** by the Graph screen | npm | yes |
| **recharts** | 3.10.x | Stress-test degradation chart | **Required** by the Stress screen | npm | yes |
| **lucide-react** | 1.31.x | Icon set | **Required** | npm | yes |
| **tailwindcss** | 3.4.x | Styling | **Required** to build | npm | yes |
| **postcss** / **autoprefixer** | 8.5.x / 10.5.x | Tailwind's build pipeline | **Required** (transitive) | npm | yes |
| **vite-plugin-singlefile** | 2.3.x | Optional `SINGLEFILE=1` build producing one self-contained HTML | Optional | npm | yes |
| **oxlint** | 1.75.x | Linting (`npm run lint`) | Optional | npm | yes |
| **@types/** react, react-dom, node | current | TypeScript definitions | **Required** to build | npm | yes |

`npm install` needs network access once. After that the frontend builds and runs offline.

---

## Network and offline behaviour

SROT makes **no outbound network calls at run time**. Specifically it does not:

- download or fetch any model, weight file or checkpoint
- call any cloud inference or moderation API
- scrape or query any social-media platform
- perform subscriber, bank, UPI or telecom lookups
- send telemetry

`HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` are safe to export; neither
`transformers` nor `huggingface_hub` is imported anywhere in the project.

The only two network operations in the whole project are:

1. the frontend dev server proxying `/api` to `127.0.0.1:8077` (localhost)
2. the test scripts calling that same localhost API

Network access is needed **once**, at install time, for `pip install` and
`npm install`.

---

## Environment variables (all optional)

| Variable | Default | Effect |
|---|---|---|
| `SROT_DATA` | `<repo>/data` | Where the database, evidence, corpus, working files and packets live |
| `SROT_FONT` | auto-discovered | Absolute path to the TrueType font FFmpeg uses when generating demo media |
| `SROT_API` | `http://127.0.0.1:8077` | Backend base URL used by the test scripts and the Vite proxy |
| `SROT_BACKEND_PORT` | `8077` | Backend port used by `run.sh` |
| `SROT_FRONTEND_PORT` | `5177` | Frontend port used by `run.sh` |

**No environment variable is required.** The application runs with none set.
