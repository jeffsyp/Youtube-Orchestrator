#!/bin/bash
# Preferred way to start the local orchestrator stack.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WORKER_HEARTBEAT="$ROOT_DIR/output/worker_heartbeat.json"

api_ready() {
    curl -sf --max-time 2 "http://127.0.0.1:8000/openapi.json" >/dev/null 2>&1
}

frontend_ready() {
    curl -sf --max-time 2 "http://127.0.0.1:5173" >/dev/null 2>&1
}

worker_ready() {
    "$ROOT_DIR/.venv/bin/python" - "$WORKER_HEARTBEAT" <<'PY'
import json
import os
import sys
import time

path = sys.argv[1]
try:
    with open(path) as f:
        data = json.load(f)
    pid = int(data.get("pid") or 0)
    last = float(data.get("last_heartbeat") or 0)
    if not pid or (time.time() - last) >= 30:
        raise SystemExit(1)
    os.kill(pid, 0)
except Exception:
    raise SystemExit(1)
PY
}

echo "Starting API..."
bash "$ROOT_DIR/scripts/run_api.sh"

echo "Starting frontend..."
bash "$ROOT_DIR/scripts/run_frontend.sh"

echo "Starting worker..."
bash "$ROOT_DIR/scripts/run_worker.sh"

echo
echo "Waiting for stack to become healthy..."
for _ in $(seq 1 20); do
    if api_ready && frontend_ready && worker_ready; then
        bash "$ROOT_DIR/scripts/status_stack.sh"
        exit 0
    fi
    sleep 1
done

bash "$ROOT_DIR/scripts/status_stack.sh"
echo "Stack did not become fully healthy within 20s" >&2
exit 1
