# SROT — Police Officer Authentication Gate & Demo Guide

> **SROT (Source Tracing & Recapture Origin Toolkit)**
> *Police / Digital Forensics Hackathon Evaluation*

---

## 1. Overview

SROT now features a secure, air-gapped **Police Forensic Access Gate** before the forensic analysis console. 

All sensitive forensic operations (evidence ingestion, metadata extraction, neural ViT inference, C2PA trust validation, origin graph matching, court packet generation, and audit logging) are strictly protected by server-side authentication.

---

## 2. Seeded Evaluation Credentials

The backend automatically seeds a default demo officer account on startup:

| Field | Evaluation Value | Description |
| :--- | :--- | :--- |
| **Badge / Service ID** | `DEMO-OFFICER` | Unique officer credential identifier |
| **Authorization Password** | `Forensic#2026!SecOps` | Strong password verified via PBKDF2-HMAC-SHA256 |
| **Officer Name** | `Insp. Vikramaditya (Cyber Ops)` | Investigating officer profile |
| **Designation / Role** | `Senior Forensic Investigator` | Cyber forensics authority role |
| **Assigned Unit** | `Cyber Crime Investigation Unit` | Operational forensic wing |

> **Tip for Judges**: A convenient **"Auto-fill Demo"** button is integrated directly into the login screen to instantly populate these credentials for quick review.

---

## 3. How to Run Locally

### Start Backend (Port 8077)
```bash
cd /Users/princemahto/Downloads/SROT
backend/.venv/bin/uvicorn app.main:app --port 8077 --app-dir backend
```

### Start Frontend (Port 5177)
```bash
npm --prefix frontend run dev
```

### Access Application
Open your browser at:
```
http://localhost:5177/
```

---

## 4. 2-Minute Jury Evaluation Walkthrough

1. **Gate Interception**:
   - Navigate to `http://localhost:5177/#/` or any deep link (e.g. `http://localhost:5177/#/analysis`).
   - Notice that unauthenticated access is immediately intercepted and securely redirected to `/#/login`.
   - The UI displays the dark police forensics terminal aesthetic, SROT shield emblem, and statutory warning notice.

2. **Security & Rejection Validation**:
   - Enter `TEST-OFFICER` with an arbitrary password.
   - Click **"Authenticate & Access Console"**.
   - Notice the immediate HTTP 401 rejection: *"Invalid officer badge ID or authorization password."*

3. **Authorized Entry**:
   - Click **"Auto-fill Demo"** (or enter `DEMO-OFFICER` and `Forensic#2026!SecOps`).
   - Click **"Authenticate & Access Console"**.
   - The gate verifies credentials and redirects to the active SROT Forensic Dashboard.

4. **Officer Identity in Sidebar**:
   - In the sidebar footer, notice the authenticated officer profile card:
     - Badge ID: `DEMO-OFFICER`
     - Officer: `Insp. Vikramaditya (Cyber Ops)`
     - Backend status indicator: `Backend online`

5. **Session Persistence**:
   - Press browser refresh (`F5` or `Cmd+R`).
   - The session token is verified against `/api/auth/session` and the user remains logged in without re-prompting.

6. **Logout Flow**:
   - Click the **"Logout"** button in the sidebar footer.
   - The session token is revoked on the backend and purged from client storage.
   - The browser returns to the login gate, and previous tokens can no longer access forensic APIs.

---

## 5. Security Architecture

- **Zero-Dependency PBKDF2-HMAC-SHA256**:
  - Offline-safe password hashing using 100,000 rounds and a 16-byte cryptographically secure salt (`os.urandom`).
  - No external cloud identity dependencies; runs completely offline and air-gapped.
- **Constant-Time Comparison**:
  - Password checks use Python's `hmac.compare_digest` to prevent timing side-channel attacks.
- **Server-Side Token Hashing**:
  - Issued session tokens (`secrets.token_urlsafe(32)`) are stored as SHA-256 hashes in SQLite. A database read exposure does not reveal active tokens.
- **FastAPI Route Dependency**:
  - Global dependency enforces authorization across all `/api/*` forensic endpoints. Only `/api/health` and `/api/auth/login` remain public.
- **Clean React Architecture**:
  - React Router Layout Route protects all views without touching or altering existing forensic screens, scoring engines, or report exporters.

---

## 6. Automated Test Suite

Run the authentication test suite:
```bash
backend/.venv/bin/python backend/test_auth_gate.py
```

Expected output:
```
============================================================
RUNNING SROT POLICE AUTHENTICATION GATE TEST SUITE
============================================================
PASS: /api/health is publicly accessible (HTTP 200)
PASS: Unauthenticated requests to protected endpoints return HTTP 401
PASS: Invalid login attempts correctly rejected (HTTP 401)
PASS: Demo officer login succeeded for Insp. Vikramaditya (Cyber Ops) (Badge: DEMO-OFFICER)
PASS: Session verification endpoint validates active token
PASS: Protected endpoint accessible with Bearer token (80 cases retrieved)
PASS: Officer logout succeeded
PASS: Revoked token rejected with HTTP 401
============================================================
ALL AUTHENTICATION GATE TESTS PASSED!
============================================================
```

---

## 7. Disclaimer

SROT is an open digital forensics research toolkit developed for hackathon evaluation. It is not affiliated with or endorsed by any official government or law enforcement agency.
