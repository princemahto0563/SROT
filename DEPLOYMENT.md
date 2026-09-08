# SROT Deployment Guide: Render & Vercel

This document specifies the official deployment and operational configuration for **SROT (Source Tracing & Recapture Origin Toolkit)**.

---

## 1. System Architecture Overview

SROT is split into two independent, decoupled cloud components:

```
┌──────────────────────────────────────────────┐
│             Vercel (Frontend)                │
│  - React 19 + TypeScript (Vite)              │
│  - Client-side HashRouter                    │
│  - Zero embedded secrets / credentials       │
└──────────────────────┬───────────────────────┘
                       │ HTTPS / TLS (Encrypted)
                       │ Authorization: Bearer <token> & Media Query-Token
                       ▼
┌──────────────────────────────────────────────┐
│              Render (Backend)                │
│  - Docker Web Service (Linux Python 3.11)    │
│  - FastAPI REST API + SQLite engine          │
│  - Pre-baked Swin-ViT Neural Model           │
│  - Persistent Disk mounted at /var/data      │
│  - System binaries: FFmpeg, Tesseract, Cairo │
└──────────────────────────────────────────────┘
```

> [!IMPORTANT]
> **Operational Scope & Disclaimers**:
> - **Evaluation Environment**: SROT is designed as a digital forensics decision-support toolkit for hackathon and research evaluation.
> - **No Government or Official Certification**: This toolkit has not been formally certified by any statutory police or governmental authority.
> - **No Claim of Infallibility**: Machine learning scores and forensic signals are probabilistic decision-support indicators, not infallible guarantees or conclusive proof of media provenance.
> - **Admissibility**: Reports and certificates conform to formatting standards (such as Section 63 BSA), but admissibility in a court of law remains subject to judicial discretion and expert testimony.

---

## 2. Distinction Between Local & Cloud Deployments

| Dimension | Local Development (`localhost`) | Production Cloud Deployment |
| :--- | :--- | :--- |
| **Frontend Origin** | `http://localhost:5177` (or `http://127.0.0.1:5177`) | `https://<your-project>.vercel.app` |
| **Backend Origin** | `http://127.0.0.1:8077` | `https://<your-service>.onrender.com` |
| **Connectivity** | 100% offline, air-gapped capable | Network-connected over HTTPS |
| **Routing** | Vite local proxy or relative fallback | Direct cross-origin CORS via `VITE_API_URL` |
| **Media Delivery** | Local relative `/api/evidence/...` | Cross-origin Render URL with query-token authentication |
| **Storage** | Local `./data/` directory | Render Persistent Disk at `/var/data` |

---

## 3. Render Backend Deployment Specification

### A. Repository Details
- **GitHub Repository**: `https://github.com/princemahto0563/SROT`
- **Branch**: `main`

### B. Render Service Configuration
- **Service Type**: **Web Service**
- **Environment**: **Docker** (Uses root `Dockerfile`)
- **Region**: Select your preferred region (e.g. Frankfurt / Singapore / Oregon)
- **Instance Type**: **Standard** or higher (minimum 1 GB RAM recommended for PyTorch Swin-ViT and WeasyPrint)

### C. Persistent Storage Configuration
- **Disk Name**: `srot-data`
- **Mount Path**: `/var/data`
- **Size**: 2 GB (or larger depending on ingested video evidence volume)
- **Persisted Directories**:
  - `/var/data/srot.db` (SQLite relational database)
  - `/var/data/evidence/` (Sealed evidence files)
  - `/var/data/work/` (Derived analysis artefacts, keyframes, traces)
  - `/var/data/corpus/` (Reference campaign corpus items)
  - `/var/data/packets/` (Generated court packets & executive dossiers)

### D. Render Environment Variables

Configure these in the Render Dashboard under **Environment**:

| Variable | Recommended Value | Purpose |
| :--- | :--- | :--- |
| `SROT_DATA` | `/var/data` | Points data storage to the persistent disk |
| `CORS_ORIGINS` | `https://<your-frontend>.vercel.app,http://localhost:5177` | Restricts API access to your exact frontend origin |
| `DEMO_OFFICER_BADGE` | `DEMO-OFFICER` | Badge ID for the evaluation account |
| `DEMO_OFFICER_PASSWORD` | `<your-secure-evaluator-password>` | Police gate authentication password |
| `DEMO_OFFICER_NAME` | `Insp. Vikramaditya (Cyber Ops)` | Profile name for report generation |
| `DEMO_OFFICER_ROLE` | `Senior Forensic Investigator` | Role title displayed in certificates |
| `DEMO_OFFICER_UNIT` | `Cyber Crime Investigation Unit` | Investigative unit name |
| `HF_HUB_OFFLINE` | `1` | Enforces offline Hugging Face operation |
| `TRANSFORMERS_OFFLINE`| `1` | Disables network calls in transformers |
| `PYTHONUNBUFFERED` | `1` | Ensures real-time container log streaming |

*(Note: Render automatically injects `$PORT`. Do **not** manually configure a fixed `$PORT` on Render).*

### E. Health Check & Startup Configuration
- **Health Check Path**: `/api/health`
- **Startup Command**: Handled automatically by `Dockerfile`:
  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port $PORT --app-dir backend
  ```
- Startup automatically runs database schema migration (`init_db()`) and seeds the configured demo officer account.

---

## 4. Vercel Frontend Deployment Specification

### A. Project Import & Build Settings
Import the GitHub repository into Vercel and apply these build settings:

- **Root Directory**: `frontend`
- **Framework Preset**: `Vite`
- **Install Command**: `npm install`
- **Build Command**: `npm run build`
- **Output Directory**: `dist`

### B. Vercel Environment Variables
Set the following environment variable in **Vercel Settings → Environment Variables**:

| Variable | Value | Description |
| :--- | :--- | :--- |
| `VITE_API_URL` | `https://<your-render-service>.onrender.com/api` | Full URL to the Render backend API base (omit trailing slash) |

---

## 5. One-Time Demo Data Initialization Procedure

Because persistent disks are empty on initial creation, run this one-time procedure to generate the demo case, synthetic media, and corpus ledger:

### Option 1: Via Render Shell (Recommended)
1. In the Render Dashboard, open your SROT Web Service.
2. Navigate to the **Shell** tab.
3. Run:
   ```bash
   python backend/seed.py
   ```
4. The seed script will:
   - Generate the synthetic master clip using Linux DejaVu fonts and FFmpeg.
   - Extract frame fingerprints and create 4 reference corpus derivatives.
   - Register the demonstration case `CASE-2026-001` and seal the evidence.
   - Commit all records to `/var/data/srot.db`.

### Option 2: One-Time Render Job
Alternatively, create a one-off Render Job with command `python backend/seed.py` attached to the same `srot-data` disk.

---

## 6. Evaluation & Login Procedure

1. Open your Vercel URL: `https://<your-frontend>.vercel.app/#/login`.
2. The **Police Forensic Access Gate** will be displayed.
3. Click **"Fill Demo Badge"** (or manually input `DEMO-OFFICER`).
4. Enter the password configured in `DEMO_OFFICER_PASSWORD` on Render.
5. Click **"Authenticate & Access Console"**.
6. The dashboard loads all ingested cases, timeline events, and forensic modules.
7. Media previews (video, frames, visual noise traces) and Court Packet downloads (PDFs & ZIP) resolve directly to Render with authenticated tokens.

---

## 7. Media & Token Security Architecture

- **Standard REST Endpoints**: Authenticated via standard `Authorization: Bearer <session_token>` headers.
- **Embedded Browser Media (`<img>`, `<video>`)**: Browser HTML media tags cannot send custom headers. SROT securely passes an encrypted session query parameter:
  ```
  https://<render-service>.onrender.com/api/evidence/<ref>/media?token=<session_token>
  ```
- **Session Revocation**: Clicking **Logout** immediately revokes the token on Render (`OfficerSession.is_revoked = True`), which immediately invalidates all subsequent REST API calls and media loads.
