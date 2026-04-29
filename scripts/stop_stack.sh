#!/bin/bash
# Stop API, frontend, and worker supervisors plus their child processes.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API_PID_FILE="/tmp/yto_api_supervisor.pid"
FRONTEND_PID_FILE="/tmp/yto_frontend_supervisor.pid"
WORKER_PID_FILE="/tmp/yto_worker_supervisor.pid"
WORKER_HEARTBEAT="$ROOT_DIR/output/worker_heartbeat.json"
WORKER_LOCK="$ROOT_DIR/output/worker.lock"

is_pid_running() {
    local pid="${1:-}"
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

kill_pid() {
    local pid="${1:-}"
    [[ -n "$pid" ]] || return 0
    if is_pid_running "$pid"; then
        kill "$pid" 2>/dev/null || true
        sleep 1
        if is_pid_running "$pid"; then
            kill -9 "$pid" 2>/dev/null || true
        fi
    fi
}

kill_listener_on_port() {
    local port="$1"
    local pid
    pid="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"
    if [[ -n "$pid" ]]; then
        echo "Stopping listener on port $port (pid $pid)"
        kill_pid "$pid"
    fi
}

stop_from_pid_file() {
    local label="$1"
    local pid_file="$2"
    if [[ -f "$pid_file" ]]; then
        local pid
        pid="$(cat "$pid_file" 2>/dev/null || true)"
        if [[ -n "$pid" ]]; then
            echo "Stopping $label supervisor (pid $pid)"
            kill_pid "$pid"
        fi
        rm -f "$pid_file"
    fi
}

stop_from_pid_file "API" "$API_PID_FILE"
stop_from_pid_file "frontend" "$FRONTEND_PID_FILE"
stop_from_pid_file "worker" "$WORKER_PID_FILE"

kill_listener_on_port 8000
kill_listener_on_port 5173

if [[ -f "$WORKER_HEARTBEAT" ]]; then
    worker_pid="$("$ROOT_DIR/.venv/bin/python" - "$WORKER_HEARTBEAT" <<'PY'
import json, sys
try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
    print(int(data.get("pid") or 0))
except Exception:
    print(0)
PY
)"
    if [[ -n "$worker_pid" && "$worker_pid" != "0" ]]; then
        echo "Stopping worker process (pid $worker_pid)"
        kill_pid "$worker_pid"
    fi
    rm -f "$WORKER_HEARTBEAT"
fi

if [[ -f "$WORKER_LOCK" ]]; then
    lock_pid="$(cat "$WORKER_LOCK" 2>/dev/null || true)"
    if [[ -n "$lock_pid" ]]; then
        echo "Stopping worker lock holder (pid $lock_pid)"
        kill_pid "$lock_pid"
    fi
    rm -f "$WORKER_LOCK"
fi

echo "Stack stopped."
