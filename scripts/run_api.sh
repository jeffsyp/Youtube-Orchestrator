#!/bin/bash
# API supervisor — auto-restarts if uvicorn dies and self-detaches by default.

set -u

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PORT=8000
PID_FILE="/tmp/yto_api_supervisor.pid"
LOG_FILE="/tmp/api.log"

is_pid_running() {
    local pid="${1:-}"
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

start_detached_supervisor() {
    local pid
    pid="$(
        python3 - "$0" "$LOG_FILE" <<'PY'
import os
import subprocess
import sys

script = sys.argv[1]
log_file = sys.argv[2]
env = dict(os.environ)
env["YTO_FOREGROUND"] = "1"

with open(log_file, "ab", buffering=0) as out:
    proc = subprocess.Popen(
        ["bash", script],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=out,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

print(proc.pid)
PY
    )"
    echo "$pid" > "$PID_FILE"
    echo "API supervisor started (pid $pid), logging to $LOG_FILE"
}

listener_pid() {
    lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -n 1
}

if [[ "${YTO_FOREGROUND:-0}" != "1" ]]; then
    existing_listener="$(listener_pid || true)"
    if [[ -n "$existing_listener" ]]; then
        echo "API already listening on 127.0.0.1:$PORT (pid $existing_listener)"
        exit 0
    fi

    if [[ -f "$PID_FILE" ]]; then
        existing_supervisor="$(cat "$PID_FILE" 2>/dev/null || true)"
        if is_pid_running "$existing_supervisor"; then
            echo "API supervisor already running (pid $existing_supervisor)"
            exit 0
        fi
        rm -f "$PID_FILE"
    fi

    echo "Starting detached API supervisor..."
    start_detached_supervisor
    exit 0
fi

cleanup() {
    rm -f "$PID_FILE"
}

trap cleanup EXIT

cd "$ROOT_DIR"

while true; do
    existing_listener="$(listener_pid || true)"
    if [[ -n "$existing_listener" ]]; then
        echo "[$(date)] API listener already active on 127.0.0.1:$PORT (pid $existing_listener); waiting..."
        sleep 5
        continue
    fi

    echo "[$(date)] Starting API..."
    .venv/bin/uvicorn apps.api.main:app --host 127.0.0.1 --port "$PORT"
    exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        echo "[$(date)] API exited cleanly"
        break
    fi

    echo "[$(date)] API died (exit $exit_code), restarting in 5s..."
    sleep 5
done
