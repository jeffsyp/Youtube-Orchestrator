#!/bin/bash
# Worker supervisor — auto-restarts if the worker dies and self-detaches by default.

set -u

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="/tmp/yto_worker_supervisor.pid"
LOG_FILE="/tmp/worker.log"
HEARTBEAT_FILE="$ROOT_DIR/output/worker_heartbeat.json"
LOCK_FILE="$ROOT_DIR/output/worker.lock"

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
    echo "Worker supervisor started (pid $pid), logging to $LOG_FILE"
}

worker_pid_from_heartbeat() {
    [[ -f "$HEARTBEAT_FILE" ]] || return 1
    "$ROOT_DIR/.venv/bin/python" - "$HEARTBEAT_FILE" <<'PY'
import json, os, signal, sys, time

path = sys.argv[1]
try:
    with open(path) as f:
        data = json.load(f)
    pid = int(data.get("pid") or 0)
    last = float(data.get("last_heartbeat") or 0)
    if not pid or (time.time() - last) >= 30:
        raise SystemExit(1)
    os.kill(pid, 0)
    print(pid)
except Exception:
    raise SystemExit(1)
PY
}

if [[ "${YTO_FOREGROUND:-0}" != "1" ]]; then
    existing_worker="$(worker_pid_from_heartbeat 2>/dev/null || true)"
    if [[ -n "$existing_worker" ]]; then
        echo "Worker already running (pid $existing_worker)"
        exit 0
    fi

    if [[ -f "$PID_FILE" ]]; then
        existing_supervisor="$(cat "$PID_FILE" 2>/dev/null || true)"
        if is_pid_running "$existing_supervisor"; then
            echo "Worker supervisor already running (pid $existing_supervisor)"
            exit 0
        fi
        rm -f "$PID_FILE"
    fi

    echo "Starting detached worker supervisor..."
    start_detached_supervisor
    exit 0
fi

cleanup() {
    rm -f "$PID_FILE"
}

trap cleanup EXIT

cd "$ROOT_DIR"

while true; do
    existing_worker="$(worker_pid_from_heartbeat 2>/dev/null || true)"
    if [[ -n "$existing_worker" ]]; then
        echo "[$(date)] Worker already active (pid $existing_worker); waiting..."
        sleep 5
        continue
    fi

    echo "[$(date)] Starting worker..."
    .venv/bin/python -m apps.worker._run
    exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        echo "[$(date)] Worker exited cleanly"
        break
    fi

    echo "[$(date)] Worker died (exit $exit_code), restarting in 5s..."
    sleep 5
done
