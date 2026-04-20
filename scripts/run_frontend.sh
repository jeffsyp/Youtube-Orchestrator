#!/bin/bash
# Frontend supervisor — auto-restarts if Vite dies
cd "$(dirname "$0")/../frontend"
while true; do
    echo "[$(date)] Starting frontend..."
    npm run dev -- --host 127.0.0.1
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 0 ]; then
        echo "[$(date)] Frontend exited cleanly"
        break
    fi
    echo "[$(date)] Frontend died (exit $EXIT_CODE), restarting in 5s..."
    sleep 5
done
