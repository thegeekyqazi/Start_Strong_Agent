#!/usr/bin/env bash
# E2E-DEMO: start a demo-owned API + web dev server on separate ports.
#
# Labelled LOCAL demo only: fixture identity, deterministic fake model, FIXTURE funding
# search/capture providers, durable C in the existing local PostgreSQL. It never migrates,
# seeds, resets or stops any other process/database. It refuses to start when the database
# is not already at the required migration head (readiness must be 200).
#
# Usage:  scripts/demo/start_stack.sh            # API :18120, web :15190
#         E2E_DEMO_FRESH=1 scripts/demo/start_stack.sh   # empty B state for a clean picker
#         E2E_DEMO_API_PORT=18130 E2E_DEMO_WEB_PORT=15200 scripts/demo/start_stack.sh
# Stop:   Ctrl+C (stops only the two processes started here).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

API_PORT="${E2E_DEMO_API_PORT:-18120}"
WEB_PORT="${E2E_DEMO_WEB_PORT:-15190}"
STATE_DIR="${E2E_DEMO_STATE_DIR:-$ROOT/.local-data/e2e-demo/state}"
# E2E_DEMO_FRESH=1: new empty B state dir for this session, so the "Questions from" pickers
# list only definitions prepared in this session (identical fixture labels are otherwise
# hard to tell apart). Nothing is deleted; earlier state dirs stay on disk.
if [[ "${E2E_DEMO_FRESH:-0}" == "1" ]]; then
  STATE_DIR="$ROOT/.local-data/e2e-demo/state-$(date -u +%Y%m%dT%H%M%SZ)"
fi
# Local Compose development URL (placeholder password from .env.example, not a secret).
# Override privately with E2E_DEMO_DATABASE_URL; it is never printed.
DB_URL="${E2E_DEMO_DATABASE_URL:-postgresql+psycopg://strongstart:strongstart_local_dev@127.0.0.1:55432/strongstart}"

for port in "$API_PORT" "$WEB_PORT"; do
  if ss -ltn "( sport = :$port )" 2>/dev/null | grep -q LISTEN; then
    echo "E2E-DEMO: port $port is already in use; choose E2E_DEMO_API_PORT/E2E_DEMO_WEB_PORT." >&2
    exit 2
  fi
done
if [[ -f "$ROOT/.env" ]]; then
  echo "E2E-DEMO: note: $ROOT/.env exists; explicit variables below take precedence." >&2
fi

mkdir -p "$STATE_DIR/dev-b-store" "$STATE_DIR/funding-captures"

export STRONGSTART_ENVIRONMENT=local
export STRONGSTART_AUTH_MODE=fixture
export STRONGSTART_ANSWER_STORE_BACKEND=postgres
export STRONGSTART_DATABASE_PROFILE=local
export STRONGSTART_DATABASE_URL="$DB_URL"
export STRONGSTART_MODEL_PROVIDER=fake
export STRONGSTART_FUNDING_SEARCH_MODE=fixture
export STRONGSTART_FUNDING_CAPTURE_MODE=fixture
export STRONGSTART_DEV_B_STORE_DIR="$STATE_DIR/dev-b-store"
export STRONGSTART_FUNDING_CAPTURE_STORE_DIR="$STATE_DIR/funding-captures"
export STRONGSTART_CORS_ORIGINS="[\"http://127.0.0.1:$WEB_PORT\"]"
# Provider keys are deliberately empty: no paid/live calls during the demo.
export STRONGSTART_GEMINI_API_KEY= STRONGSTART_TAVILY_API_KEY= STRONGSTART_FIRECRAWL_API_KEY=

pids=()
cleanup() {
  for pid in "${pids[@]}"; do kill -INT "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
  echo "E2E-DEMO: stopped demo-owned API/web processes (state kept in $STATE_DIR)."
}
trap cleanup EXIT INT TERM

uv run uvicorn --factory strongstart_api.app:app_factory \
  --host 127.0.0.1 --port "$API_PORT" --workers 1 &
pids+=("$!")

for _ in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$API_PORT/health/ready" || true)
  [[ "$code" == "200" ]] && break
  sleep 0.5
done
if [[ "${code:-}" != "200" ]]; then
  echo "E2E-DEMO BLOCKER: GET http://127.0.0.1:$API_PORT/health/ready returned ${code:-no response}." >&2
  curl -s "http://127.0.0.1:$API_PORT/health/ready" >&2 || true
  echo >&2
  echo "Not migrating or resetting anything. Ask the database owner to bring it to head." >&2
  exit 3
fi

(cd apps/web && WEB_DEV_API_PROXY="http://127.0.0.1:$API_PORT" \
  npx vite --host 127.0.0.1 --port "$WEB_PORT" --strictPort) &
pids+=("$!")

cat <<EOF

E2E-DEMO stack ready (LOCAL, SYNTHETIC, FIXTURE identity):
  API  http://127.0.0.1:$API_PORT   (ready 200)
  Web  http://127.0.0.1:$WEB_PORT
  State $STATE_DIR (dev-only B files owned by this demo)

Next, in another terminal:
  uv run python -m scripts.demo.e2e_demo prepare --api http://127.0.0.1:$API_PORT --web http://127.0.0.1:$WEB_PORT
EOF
wait
