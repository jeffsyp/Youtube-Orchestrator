#!/bin/bash
# API supervisor — auto-restarts if uvicorn dies
cd "$(dirname "$0")/.."
while true; do
    echo "[$(date)] Starting API..."
    .venv/bin/uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 0 ]; then
        echo "[$(date)] API exited cleanly"
        break
    fi
    echo "[$(date)] API died (exit $EXIT_CODE), restarting in 5s..."
    sleep 5
done
