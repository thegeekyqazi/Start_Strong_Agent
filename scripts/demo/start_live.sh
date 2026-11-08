#!/usr/bin/env bash
# DEMO-LIVE: start one API + one web dev server with LIVE providers for a demonstration.
#
# Unlike start_stack.sh (fake model, FIXTURE funding providers, keys cleared), this launcher
# requires live configuration and refuses to start when any of it is missing. It never falls
# back to fake/fixture output and never prints secrets or connection URLs.
#
# Live:    model provider gemini (key + model), funding search (Tavily) and capture (Firecrawl),
#          read from this worktree's Git-ignored .env.
# Labelled fixture (unchanged): LOCAL fixture identity (STRONGSTART_AUTH_MODE=fixture),
#          synthetic evidence bundle, representative portals. Staff still control submission.
# Database: hosted TigerData TEST service through the restricted runtime role, loaded from the
#          private DEMO_DB_ENV file (verify-full TLS, pinned trust root, connection budget).
#          The migration URL in that file is dropped before the API starts. An explicitly
#          labelled local PostgreSQL fallback needs DEMO_DB=local-fallback and
#          DEMO_LOCAL_DATABASE_URL (a 127.0.0.1 database already at migration head).
#
# Usage:   scripts/demo/start_live.sh                 # API :18220, web :15290, detached
#          DEMO_ALLOWED_HOST=<exact tunnel hostname> scripts/demo/start_live.sh --web-only
#          scripts/demo/stop_live.sh                  # stops only the PIDs recorded here
# Nothing migrates, seeds, resets or grants here; readiness must already be 200.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

API_PORT="${DEMO_API_PORT:-18220}"
WEB_PORT="${DEMO_WEB_PORT:-15290}"
RUN_DIR="$ROOT/.local-data/demo-live"
STATE_DIR="$RUN_DIR/state"
LOG_DIR="$RUN_DIR/logs"
DB_MODE="${DEMO_DB:-tigerdata}"
DB_ENV="${DEMO_DB_ENV:-$HOME/.local/share/strongstart-data001-private/hosted.env}"
WEB_ONLY=0
[[ "${1:-}" == "--web-only" ]] && WEB_ONLY=1

die() { echo "DEMO-LIVE BLOCKER: $*" >&2; exit "${2:-2}"; }

port_busy() { ss -ltn "( sport = :$1 )" 2>/dev/null | grep -q LISTEN; }
alive() { [[ -f "$1" ]] && kill -0 "$(cat "$1")" 2>/dev/null; }

mkdir -p "$STATE_DIR/dev-b-store" "$STATE_DIR/funding-captures" "$LOG_DIR"
chmod 700 "$RUN_DIR"

start_web() {
  alive "$RUN_DIR/web.pid" && die "web already running (PID $(cat "$RUN_DIR/web.pid")); stop it first"
  port_busy "$WEB_PORT" && die "port $WEB_PORT is in use"
  local extra=()
  if [[ -n "${DEMO_ALLOWED_HOST:-}" ]]; then
    [[ "$DEMO_ALLOWED_HOST" =~ ^[a-z0-9-]+(\.[a-z0-9-]+)+$ ]] || die "DEMO_ALLOWED_HOST must be one exact hostname"
    extra=(env "__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS=$DEMO_ALLOWED_HOST")
  fi
  (cd apps/web && exec "${extra[@]}" env WEB_DEV_API_PROXY="http://127.0.0.1:$API_PORT" \
    setsid "$ROOT/node_modules/.bin/vite" --host 127.0.0.1 --port "$WEB_PORT" --strictPort \
    >"$LOG_DIR/web.log" 2>&1 </dev/null) &
  echo $! >"$RUN_DIR/web.pid"
  for _ in $(seq 1 40); do port_busy "$WEB_PORT" && break; sleep 0.5; done
  port_busy "$WEB_PORT" || die "web did not start; see $LOG_DIR/web.log" 3
  echo "DEMO-LIVE web  http://127.0.0.1:$WEB_PORT  PID $(cat "$RUN_DIR/web.pid")  log $LOG_DIR/web.log"
  [[ -n "${DEMO_ALLOWED_HOST:-}" ]] && echo "  additional allowed host: $DEMO_ALLOWED_HOST"
  return 0
}

if [[ "$WEB_ONLY" == "1" ]]; then
  start_web
  exit 0
fi

alive "$RUN_DIR/api.pid" && die "API already running (PID $(cat "$RUN_DIR/api.pid")); run stop_live.sh first"
for port in "$API_PORT" "$WEB_PORT"; do port_busy "$port" && die "port $port is in use"; done
[[ -f "$ROOT/.env" ]] || die "$ROOT/.env is missing; copy .env.example and fill the live settings privately"

# --- database selection (never silently falls back) -----------------------------------------
case "$DB_MODE" in
  tigerdata)
    [[ -r "$DB_ENV" ]] || die "private TigerData env $DB_ENV is not readable"
    set -a; . "$DB_ENV"; set +a
    unset DATA001_MIGRATION_DATABASE_URL DATA001_TIGERDATA_OPT_IN  # runtime role only
    [[ "${STRONGSTART_DATABASE_PROFILE:-}" == "tigerdata" ]] || die "DEMO_DB_ENV does not select the tigerdata profile"
    DB_LABEL="TigerData hosted TEST service (runtime role, verify-full)"
    ;;
  local-fallback)
    [[ -n "${DEMO_LOCAL_DATABASE_URL:-}" ]] || die "DEMO_DB=local-fallback needs DEMO_LOCAL_DATABASE_URL"
    export STRONGSTART_DATABASE_URL="$DEMO_LOCAL_DATABASE_URL" STRONGSTART_DATABASE_PROFILE=local
    DB_LABEL="LOCAL PostgreSQL FALLBACK (not TigerData)"
    ;;
  *) die "DEMO_DB must be tigerdata or local-fallback" ;;
esac

# Fixed demo posture: local environment, LOCAL fixture identity, durable C store.
export STRONGSTART_ENVIRONMENT=local
export STRONGSTART_AUTH_MODE=fixture
export STRONGSTART_ANSWER_STORE_BACKEND=postgres
export STRONGSTART_API_PROCESSES=1
export STRONGSTART_DEV_B_STORE_DIR="$STATE_DIR/dev-b-store"
export STRONGSTART_FUNDING_CAPTURE_STORE_DIR="$STATE_DIR/funding-captures"
export STRONGSTART_CORS_ORIGINS="[\"http://127.0.0.1:$WEB_PORT\"]"

# --- live provider preflight (names only; values never printed) ------------------------------
"$ROOT/.venv/bin/python" - <<'PY' || die "live configuration incomplete (see above); not starting" 4
import sys
from strongstart_api.config import Settings
s = Settings()
missing = []
def secret(v):
    return bool(v is not None and v.get_secret_value())
if s.model_provider != "gemini":
    missing.append("STRONGSTART_MODEL_PROVIDER=gemini")
if not secret(s.gemini_api_key):
    missing.append("STRONGSTART_GEMINI_API_KEY")
if not s.gemini_model:
    missing.append("STRONGSTART_GEMINI_MODEL")
if s.funding_search_mode != "live":
    missing.append("STRONGSTART_FUNDING_SEARCH_MODE=live")
if s.funding_capture_mode != "live":
    missing.append("STRONGSTART_FUNDING_CAPTURE_MODE=live")
if not secret(s.tavily_api_key):
    missing.append("STRONGSTART_TAVILY_API_KEY")
if not secret(s.firecrawl_api_key):
    missing.append("STRONGSTART_FIRECRAWL_API_KEY")
if s.auth_mode != "fixture" or s.answer_store_backend != "postgres":
    missing.append("fixture auth + postgres answer store")
if missing:
    print("DEMO-LIVE missing/invalid: " + ", ".join(missing), file=sys.stderr)
    sys.exit(1)
print(f"DEMO-LIVE preflight: gemini model {s.gemini_model}; search/capture live; "
      f"DB profile {s.database_profile}")
PY

setsid "$ROOT/.venv/bin/uvicorn" --factory strongstart_api.app:app_factory \
  --host 127.0.0.1 --port "$API_PORT" --workers 1 >"$LOG_DIR/api.log" 2>&1 </dev/null &
echo $! >"$RUN_DIR/api.pid"

code=""
for _ in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$API_PORT/health/ready" || true)
  [[ "$code" == "200" ]] && break
  alive "$RUN_DIR/api.pid" || break
  sleep 0.5
done
if [[ "$code" != "200" ]]; then
  curl -s "http://127.0.0.1:$API_PORT/health/ready" >&2 || true
  echo >&2
  die "API readiness ${code:-no response}; see $LOG_DIR/api.log. Not migrating or resetting." 3
fi
echo "DEMO-LIVE API  http://127.0.0.1:$API_PORT  PID $(cat "$RUN_DIR/api.pid")  ready 200  log $LOG_DIR/api.log"
echo "  database: $DB_LABEL"

start_web
echo "Stop: scripts/demo/stop_live.sh   (fixture identity + synthetic evidence remain labelled)"
