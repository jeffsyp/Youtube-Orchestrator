#!/bin/bash
# Worker supervisor — auto-restarts if the watchdog kills the process
cd "$(dirname "$0")/.."
while true; do
    echo "[$(date)] Starting worker..."
    .venv/bin/python -m apps.worker._run
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 0 ]; then
        echo "[$(date)] Worker exited cleanly"
        break
    fi
    echo "[$(date)] Worker died (exit $EXIT_CODE), restarting in 5s..."
    sleep 5
done
