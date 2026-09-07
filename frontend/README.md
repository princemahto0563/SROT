# SROT console (frontend)

React + TypeScript + Vite. Twelve screens, one per stage of the investigation.

**There is no bundled fixture data.** Every value on screen comes from the running
backend; if the backend is down, the console says so rather than showing sample
numbers.

## Run

```bash
npm install
npm run dev            # http://127.0.0.1:5177, proxies /api to 127.0.0.1:8077
```

Point at a different backend with `SROT_API=http://host:port npm run dev`.

```bash
npm run build          # dist/
SINGLEFILE=1 npm run build   # one self-contained dist/index.html
npm run lint
npx tsc -b             # type check
```

## Structure

| Path | Purpose |
|------|---------|
| `src/lib/api.ts` | typed fetch client, `useApi` / `usePolling` hooks, formatters |
| `src/state/session.tsx` | which case and evidence item the screens are showing |
| `src/components/ui.tsx` | panels, tables, chips, meters, `Async` wrapper, empty/error states |
| `src/components/guards.tsx` | shared "no evidence / still running / failed" states |
| `src/components/Boundary.tsx` | error boundary — one screen failing never blanks the app |
| `src/components/Shell.tsx` | sidebar, case + evidence selection, live backend status |
| `src/screens/*` | the twelve screens |

## Conventions

- **Every remote view goes through `<Async>`** — loading skeleton, error with retry,
  and an empty state that explains *why* it is empty, in one place.
- **Empty means empty.** A panel with no data says what was searched and what was
  not found. It never substitutes a plausible-looking value.
- **No dead controls.** Every button either performs a request or is disabled with
  a reason.
- **Wording is fixed by the backend.** Disclaimers, limitations and the attribution
  ceiling are rendered from API fields, not retyped in the components, so the
  console and the PDFs cannot drift apart.

## Screens

| Route | Screen | Reads |
|-------|--------|-------|
| `/` | Case Dashboard | `/cases`, `/cases/{ref}`, `/leads`, `/campaign-matches` |
| `/upload` | Evidence Intake | `POST /evidence`, `/job`, evidence viewer via `/media` |
| `/analysis` | Forensic Analysis | `/analysis`, `/frames`, `/frames/{i}/image` |
| `/origin` | Origin Trace | `/origin` (incl. threshold calibration + attribution ceiling) |
| `/recapture` | Recapture Forensics | `/recapture` |
| `/entities` | OCR & Identifiers | `/entities` (bounding boxes drawn on the real frame) |
| `/graph` | Investigation Graph | `/graph` (React Flow) |
| `/cross-case` | Cross-Case Links | `/campaign-matches` |
| `/stress` | Laundering Stress Test | `POST`/`GET /stress-test` (Recharts) |
| `/timeline` | Timeline & Leads | `/timeline`, `/leads` |
| `/audit` | Audit Trail | `/audit` |
| `/packet` | Court Packet | `/court-packet`, `/verify-hash`, `/consistency` |
