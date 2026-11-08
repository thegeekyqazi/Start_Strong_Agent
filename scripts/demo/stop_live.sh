#!/usr/bin/env bash
# DEMO-LIVE: stop only the processes recorded by start_live.sh (and an optional tunnel PID).
# Usage: scripts/demo/stop_live.sh [api|web|tunnel ...]   (default: tunnel web api)
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_DIR="$ROOT/.local-data/demo-live"
targets=("$@")
[[ ${#targets[@]} -eq 0 ]] && targets=(tunnel web api)
for name in "${targets[@]}"; do
  f="$RUN_DIR/$name.pid"
  [[ -f "$f" ]] || { echo "$name: no PID file"; continue; }
  pid="$(cat "$f")"
  if kill -0 "$pid" 2>/dev/null; then
    # Process-group kill: setsid made each recorded PID its own group leader.
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid"
    for _ in $(seq 1 20); do kill -0 "$pid" 2>/dev/null || break; sleep 0.25; done
    echo "$name: stopped PID $pid"
  else
    echo "$name: PID $pid not running"
  fi
  rm -f "$f"
done
