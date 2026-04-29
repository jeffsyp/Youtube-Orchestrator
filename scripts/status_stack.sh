#!/bin/bash
# Show a compact status summary for API, frontend, and worker.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API_PID_FILE="/tmp/yto_api_supervisor.pid"
FRONTEND_PID_FILE="/tmp/yto_frontend_supervisor.pid"
WORKER_PID_FILE="/tmp/yto_worker_supervisor.pid"
WORKER_HEARTBEAT="$ROOT_DIR/output/worker_heartbeat.json"

is_pid_running() {
    local pid="${1:-}"
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

listener_pid() {
    local port="$1"
    lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -n 1 || true
}

http_status() {
    local url="$1"
    local code
    code="$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "$url" 2>/dev/null || true)"
    if [[ -z "$code" ]]; then
        code="000"
    fi
    printf "%s" "$code"
}

status_from_pid_file() {
    local label="$1"
    local pid_file="$2"
    local port="$3"
    local url="$4"

    local supervisor_pid=""
    if [[ -f "$pid_file" ]]; then
        supervisor_pid="$(cat "$pid_file" 2>/dev/null || true)"
    fi

    local listener
    listener="$(listener_pid "$port")"
    local code
    code="$(http_status "$url")"

    if [[ -n "$listener" ]] || [[ "$code" == "200" ]]; then
        echo "$label: running (listener=${listener:-none}, supervisor=${supervisor_pid:-none}, http=$code)"
        return
    fi

    if [[ -n "$supervisor_pid" ]] && is_pid_running "$supervisor_pid"; then
        echo "$label: starting or unhealthy (supervisor=$supervisor_pid, http=$code)"
        return
    fi

    echo "$label: stopped"
}

worker_status() {
    local supervisor_pid=""
    if [[ -f "$WORKER_PID_FILE" ]]; then
        supervisor_pid="$(cat "$WORKER_PID_FILE" 2>/dev/null || true)"
    fi

    if [[ -f "$WORKER_HEARTBEAT" ]]; then
        "$ROOT_DIR/.venv/bin/python" - "$WORKER_HEARTBEAT" "$supervisor_pid" <<'PY'
import json, os, sys, time

heartbeat_path = sys.argv[1]
supervisor_pid = sys.argv[2] if len(sys.argv) > 2 else ""
try:
    with open(heartbeat_path) as f:
        data = json.load(f)
    pid = int(data.get("pid") or 0)
    last = float(data.get("last_heartbeat") or 0)
    age = int(time.time() - last) if last else None
    running = False
    if pid:
        try:
            os.kill(pid, 0)
            running = age is not None and age < 30
        except OSError:
            running = False
    if running:
        print(f"Worker: running (pid={pid}, supervisor={supervisor_pid or 'none'}, heartbeat_age={age}s)")
    elif supervisor_pid:
        print(f"Worker: starting or unhealthy (supervisor={supervisor_pid}, last_worker_pid={pid or 'none'}, heartbeat_age={age if age is not None else 'unknown'}s)")
    else:
        print("Worker: stopped")
except Exception:
    if supervisor_pid:
        print(f"Worker: starting or unhealthy (supervisor={supervisor_pid})")
    else:
        print("Worker: stopped")
PY
        return
    fi

    if [[ -n "$supervisor_pid" ]] && is_pid_running "$supervisor_pid"; then
        echo "Worker: starting or unhealthy (supervisor=$supervisor_pid)"
        return
    fi

    echo "Worker: stopped"
}

status_from_pid_file "API" "$API_PID_FILE" 8000 "http://127.0.0.1:8000/openapi.json"
status_from_pid_file "Frontend" "$FRONTEND_PID_FILE" 5173 "http://127.0.0.1:5173"
worker_status
