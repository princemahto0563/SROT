#!/usr/bin/env bash
#
# SROT — one-command launcher.
#
#   ./run.sh                 start backend + frontend (seeds only if empty)
#   ./run.sh --reset         rebuild the demonstration media and database first
#   ./run.sh --backend       backend only
#   ./run.sh --frontend      frontend only (expects a backend already running)
#   ./run.sh --test          run the full verification suite and exit
#   ./run.sh --check         check prerequisites and exit
#
# Written for bash 3.2 so it runs on a stock macOS shell as well as Linux.
# Ctrl-C stops both services cleanly.

set -u
cd "$(cd "$(dirname "$0")" && pwd)"
ROOT="$PWD"

BACKEND_PORT="${SROT_BACKEND_PORT:-8077}"
FRONTEND_PORT="${SROT_FRONTEND_PORT:-5177}"
BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}"
FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}"
VENV="$ROOT/backend/.venv"

RESET=""; ONLY_BACKEND=""; ONLY_FRONTEND=""; ONLY_TEST=""; ONLY_CHECK=""

for a in "$@"; do
  case "$a" in
    --reset)    RESET="--reset" ;;
    --backend)  ONLY_BACKEND=1 ;;
    --frontend) ONLY_FRONTEND=1 ;;
    --test)     ONLY_TEST=1 ;;
    --check)    ONLY_CHECK=1 ;;
    -h|--help)  sed -n '3,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $a  (try --help)" >&2; exit 2 ;;
  esac
done

# ── output helpers ───────────────────────────────────────────────────────────
if [ -t 1 ]; then B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; N=$'\033[0m'
else B=""; G=""; Y=""; R=""; N=""; fi
say()  { printf '%s\n' "$1"; }
step() { printf '%s\n' "${B}· $1${N}"; }
ok()   { printf '  %s\n' "${G}✓${N} $1"; }
warn() { printf '  %s\n' "${Y}!${N} $1"; }
die()  { printf '%s\n' "${R}✗ $1${N}" >&2; exit 1; }

is_mac() { [ "$(uname -s)" = "Darwin" ]; }

brew_hint() {
  if is_mac; then echo "brew install $1"
  else echo "sudo apt-get install -y $2"; fi
}

# ── 1. prerequisites ─────────────────────────────────────────────────────────
check_prereqs() {
  step "Checking prerequisites"
  local missing=0

  if command -v python3 >/dev/null 2>&1; then
    PYV=$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')
    PYOK=$(python3 -c 'import sys;print(1 if sys.version_info[:2]>=(3,10) else 0)')
    if [ "$PYOK" = "1" ]; then ok "python3 $PYV"
    else warn "python3 $PYV — 3.10 or newer required ($(brew_hint 'python@3.12' 'python3'))"; missing=1; fi
  else
    warn "python3 not found ($(brew_hint 'python@3.12' 'python3'))"; missing=1
  fi

  if command -v node >/dev/null 2>&1; then
    NODEV=$(node -v)
    NODEMAJ=$(printf '%s' "$NODEV" | sed 's/^v\([0-9]*\).*/\1/')
    if [ "$NODEMAJ" -ge 20 ] 2>/dev/null; then ok "node $NODEV"
    else warn "node $NODEV — 20 or newer required ($(brew_hint 'node' 'nodejs npm'))"; missing=1; fi
  else
    warn "node not found ($(brew_hint 'node' 'nodejs npm'))"; missing=1
  fi

  command -v npm >/dev/null 2>&1 && ok "npm $(npm -v)" || { warn "npm not found"; missing=1; }

  for t in ffmpeg ffprobe; do
    if command -v "$t" >/dev/null 2>&1; then ok "$t"
    else warn "$t not found ($(brew_hint 'ffmpeg' 'ffmpeg'))"; missing=1; fi
  done

  if command -v tesseract >/dev/null 2>&1; then
    ok "tesseract $(tesseract --version 2>&1 | head -1 | awk '{print $2}')"
    LANGS=$(tesseract --list-langs 2>/dev/null | tail -n +2 | tr '\n' ' ')
    for l in eng hin pan; do
      case " $LANGS " in
        *" $l "*) ok "OCR language: $l" ;;
        *) warn "OCR language '$l' missing — $(brew_hint 'tesseract-lang' "tesseract-ocr-$l")" ;;
      esac
    done
  else
    warn "tesseract not found ($(brew_hint 'tesseract tesseract-lang' 'tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin tesseract-ocr-pan'))"
    missing=1
  fi

  if is_mac && ! (command -v pango-view >/dev/null 2>&1 || ls /opt/homebrew/lib/libpango* >/dev/null 2>&1 || ls /usr/local/lib/libpango* >/dev/null 2>&1); then
    warn "pango not detected — the court packet needs it: brew install pango gdk-pixbuf libffi"
  fi

  [ "$missing" -eq 0 ] || die "Install the tools above, then run ./run.sh again. See README.md."
  ok "all required tools present"
}

# ── 2. python environment ────────────────────────────────────────────────────
setup_python() {
  step "Python environment"
  if [ ! -d "$VENV" ]; then
    say "  creating virtualenv at backend/.venv"
    python3 -m venv "$VENV" || die "could not create the virtualenv"
  fi
  PY="$VENV/bin/python"
  STAMP="$VENV/.requirements-sha"
  NEW=$(shasum -a 256 "$ROOT/backend/requirements.txt" 2>/dev/null | awk '{print $1}')
  [ -n "$NEW" ] || NEW=$(sha256sum "$ROOT/backend/requirements.txt" | awk '{print $1}')
  if [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$NEW" ]; then
    say "  installing python dependencies (first run takes a few minutes)"
    "$PY" -m pip install --quiet --upgrade pip >/dev/null 2>&1
    "$PY" -m pip install --quiet -r "$ROOT/backend/requirements.txt" \
      || die "pip install failed — see README.md troubleshooting"
    printf '%s' "$NEW" > "$STAMP"
  fi
  ok "python dependencies ready"
}

setup_node() {
  step "Node environment"
  if [ ! -d "$ROOT/frontend/node_modules" ]; then
    say "  installing node dependencies (first run takes a minute)"
    ( cd "$ROOT/frontend" && npm install --no-audit --no-fund ) || die "npm install failed"
  fi
  ok "node dependencies ready"
}

# ── 3. ports ─────────────────────────────────────────────────────────────────
port_pid() {
  # lsof is present on macOS and most Linux images; fall back to fuser, then to
  # a python probe, so a missing tool never blocks startup.
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti tcp:"$1" 2>/dev/null | head -1
  elif command -v fuser >/dev/null 2>&1; then
    fuser "$1"/tcp 2>/dev/null | awk '{print $1}' | head -1
  else
    "$PY" - "$1" 2>/dev/null <<'PYEOF'
import socket, sys
s = socket.socket()
try:
    s.bind(("127.0.0.1", int(sys.argv[1])))
except OSError:
    print("unknown")
finally:
    s.close()
PYEOF
  fi
}

free_port() {
  local p="$1" name="$2" pid
  pid=$(port_pid "$p")
  [ -n "$pid" ] || return 0
  if [ "$pid" = "unknown" ]; then
    die "port $p is in use but the owning process could not be identified — stop it and retry"
  fi
  warn "port $p already in use by pid $pid ($name)"
  kill "$pid" 2>/dev/null
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    sleep 0.5
    [ -z "$(port_pid "$p")" ] && { ok "freed port $p"; return 0; }
  done
  kill -9 "$pid" 2>/dev/null; sleep 1
  [ -z "$(port_pid "$p")" ] || die "could not free port $p — stop that process and retry"
  ok "freed port $p"
}

# ── 4. lifecycle ─────────────────────────────────────────────────────────────
BACKEND_PID=""; FRONTEND_PID=""
cleanup() {
  trap - INT TERM EXIT
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
  wait 2>/dev/null
  say ""
  say "stopped."
}

seed_data() {
  step "Demonstration data (SYNTHETIC)"
  ( cd "$ROOT/backend" && "$PY" seed.py $RESET ) || die "seeding failed"
}

start_backend() {
  step "Backend"
  free_port "$BACKEND_PORT" "backend"
  ( cd "$ROOT/backend" && exec "$PY" -m uvicorn app.main:app \
      --host 127.0.0.1 --port "$BACKEND_PORT" ) &
  BACKEND_PID=$!
  local i=0
  while [ "$i" -lt 60 ]; do
    if curl -sf "$BACKEND_URL/api/health" >/dev/null 2>&1; then
      ok "backend ready at ${BACKEND_URL}"
      ok "API docs at      ${BACKEND_URL}/docs"
      return 0
    fi
    kill -0 "$BACKEND_PID" 2>/dev/null || die "backend exited during startup"
    sleep 1; i=$((i + 1))
  done
  die "backend did not become healthy within 60s"
}

start_frontend() {
  step "Frontend"
  free_port "$FRONTEND_PORT" "frontend"
  ( cd "$ROOT/frontend" && exec npm run dev -- --port "$FRONTEND_PORT" --strictPort ) &
  FRONTEND_PID=$!
  local i=0
  while [ "$i" -lt 60 ]; do
    if curl -sf "$FRONTEND_URL" >/dev/null 2>&1; then
      ok "frontend ready at ${FRONTEND_URL}"
      return 0
    fi
    kill -0 "$FRONTEND_PID" 2>/dev/null || die "frontend exited during startup"
    sleep 1; i=$((i + 1))
  done
  die "frontend did not become reachable within 60s"
}

banner() {
  say ""
  say "${B}────────────────────────────────────────────────────────────${N}"
  say "${B}  SROT is running${N}"
  say ""
  say "    Console (open this):  ${B}${FRONTEND_URL}${N}"
  say "    Backend API:          ${BACKEND_URL}"
  say "    API documentation:    ${BACKEND_URL}/docs"
  say "    Health check:         ${BACKEND_URL}/api/health"
  say ""
  say "    Demo file to upload:  data/evidence/_to_upload/"
  say "    Press Ctrl-C to stop both services."
  say "${B}────────────────────────────────────────────────────────────${N}"
  say ""
}

# ── main ─────────────────────────────────────────────────────────────────────
check_prereqs
[ -n "$ONLY_CHECK" ] && exit 0

setup_python

if [ -n "$ONLY_TEST" ]; then
  seed_data
  trap cleanup INT TERM EXIT
  start_backend
  step "Verification suite"
  cd "$ROOT/backend"
  "$PY" calibrate.py       || die "calibration failed"
  "$PY" e2e.py             || die "end-to-end run failed"
  "$PY" test_features.py   || die "feature tests failed"
  "$PY" test_audit_chain.py || die "audit chain tests failed"
  "$PY" inspect_data.py    || die "data inspection failed"
  ok "all verification suites passed"
  exit 0
fi

if [ -n "$ONLY_FRONTEND" ]; then
  setup_node
  trap cleanup INT TERM EXIT
  start_frontend
  banner
  wait "$FRONTEND_PID"
  exit 0
fi

[ -n "$ONLY_BACKEND" ] || setup_node
seed_data
trap cleanup INT TERM EXIT
start_backend

if [ -n "$ONLY_BACKEND" ]; then
  say ""
  ok "backend only. API: ${BACKEND_URL}  ·  docs: ${BACKEND_URL}/docs"
  wait "$BACKEND_PID"
else
  start_frontend
  banner
  wait "$BACKEND_PID" "$FRONTEND_PID"
fi
