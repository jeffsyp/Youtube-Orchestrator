#!/usr/bin/env bash
# Watchdog: detect and unblock stuck pipeline runs
# Exits after 60 minutes. Uses temp files for tracking (bash 3.2 compatible).

set -uo pipefail

PROJECT_DIR="/Users/jeffsyp/Projects/Youtube-Orchestrator"
cd "$PROJECT_DIR"

DURATION=3600  # 60 minutes
INTERVAL=60    # check every 60 seconds
STUCK_THRESHOLD=900  # 15 minutes in seconds

TRACK_DIR="/tmp/watchdog_tracking"
rm -rf "$TRACK_DIR"
mkdir -p "$TRACK_DIR"

START_TIME=$(date +%s)

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

restart_worker() {
  log "Starting worker process..."
  cd "$PROJECT_DIR"
  .venv/bin/python -m apps.worker._run > /tmp/worker_direct.log 2>&1 &
  log "Worker started with PID $!"
}

check_worker() {
  if ! pgrep -f "apps.worker._run" > /dev/null 2>&1; then
    log "WARNING: Worker process not running. Restarting..."
    restart_worker
  fi
}

get_tracked_step() {
  local run_id=$1
  if [ -f "$TRACK_DIR/run_${run_id}_step" ]; then
    cat "$TRACK_DIR/run_${run_id}_step"
  fi
}

get_tracked_time() {
  local run_id=$1
  if [ -f "$TRACK_DIR/run_${run_id}_time" ]; then
    cat "$TRACK_DIR/run_${run_id}_time"
  fi
}

set_tracking() {
  local run_id=$1
  local step="$2"
  local time=$3
  echo "$step" > "$TRACK_DIR/run_${run_id}_step"
  echo "$time" > "$TRACK_DIR/run_${run_id}_time"
}

clear_tracking() {
  local run_id=$1
  rm -f "$TRACK_DIR/run_${run_id}_step" "$TRACK_DIR/run_${run_id}_time"
}

unstick_run() {
  local run_id=$1
  local step="$2"
  local channel="$3"

  log "=== STUCK RUN DETECTED ==="
  log "Run $run_id ($channel) stuck on '$step' for 15+ minutes"

  # Get content_bank_id
  local cb_id
  cb_id=$(psql -t -A -d youtube_orchestrator -c "SELECT content_bank_id FROM content_runs WHERE id = $run_id;" 2>/dev/null || echo "")

  # Kill the worker
  log "Killing worker process..."
  local worker_pids
  worker_pids=$(pgrep -f "apps.worker._run" 2>/dev/null || true)
  if [ -n "$worker_pids" ]; then
    echo "$worker_pids" | xargs kill 2>/dev/null || true
  fi
  sleep 2

  # Mark run as failed
  log "Marking run $run_id as failed..."
  psql -d youtube_orchestrator -c "UPDATE content_runs SET status = 'failed', error = 'watchdog: stuck for 15min on $step' WHERE id = $run_id;" 2>/dev/null

  # Clean output
  log "Cleaning output/run_$run_id..."
  rm -rf "output/run_$run_id" 2>/dev/null || true

  # Re-queue content if we have a content_bank_id
  if [ -n "$cb_id" ] && [ "$cb_id" != "" ]; then
    log "Re-queuing content_bank item $cb_id..."
    psql -d youtube_orchestrator -c "UPDATE content_bank SET status = 'queued', run_id = NULL WHERE id = $cb_id;" 2>/dev/null
  fi

  # Remove tracking for this run
  clear_tracking "$run_id"

  # Restart worker
  restart_worker
  log "=== UNSTICK COMPLETE ==="
}

log "Watchdog started. Monitoring for $((DURATION / 60)) minutes."
log "Current active runs:"

while true; do
  NOW=$(date +%s)
  ELAPSED=$((NOW - START_TIME))

  if [ $ELAPSED -ge $DURATION ]; then
    log "60-minute window complete. Exiting cleanly."
    break
  fi

  REMAINING=$(( (DURATION - ELAPSED) / 60 ))

  # Check worker is alive
  check_worker

  # Query active runs
  RUNS=$(psql -t -A -d youtube_orchestrator -c "SELECT cr.id, c.name, cr.current_step, cr.started_at FROM content_runs cr JOIN channels c ON c.id = cr.channel_id WHERE cr.status = 'running' ORDER BY cr.id;" 2>/dev/null || echo "")

  # Collect active IDs
  ACTIVE_IDS=""

  if [ -z "$RUNS" ]; then
    log "No active runs. ${REMAINING}m remaining."
    # Clean all tracking files
    rm -f "$TRACK_DIR"/run_*_step "$TRACK_DIR"/run_*_time 2>/dev/null || true
  else
    # Write runs to temp file to avoid subshell issues with pipe
    echo "$RUNS" > "$TRACK_DIR/_current_runs"
    while IFS='|' read -r run_id channel step started_at; do
      [ -z "$run_id" ] && continue

      tracked_step=$(get_tracked_step "$run_id")
      tracked_time=$(get_tracked_time "$run_id")

      if [ -z "$tracked_step" ]; then
        # First time seeing this run
        set_tracking "$run_id" "$step" "$NOW"
        log "Tracking run $run_id ($channel): '$step'"
      elif [ "$tracked_step" != "$step" ]; then
        # Step changed, progressing normally
        set_tracking "$run_id" "$step" "$NOW"
        log "Run $run_id ($channel) progressed to '$step'"
      else
        # Same step, check how long
        stuck_duration=$((NOW - tracked_time))
        if [ $stuck_duration -ge $STUCK_THRESHOLD ]; then
          unstick_run "$run_id" "$step" "$channel"
        fi
      fi
    done < "$TRACK_DIR/_current_runs"

    # Prune tracking for runs that are no longer active
    for track_file in "$TRACK_DIR"/run_*_step; do
      [ -f "$track_file" ] || continue
      tracked_id=$(echo "$track_file" | sed 's/.*run_\([0-9]*\)_step/\1/')
      if ! echo "$RUNS" | grep -q "^${tracked_id}|"; then
        log "Run $tracked_id no longer active. Removing from tracking."
        clear_tracking "$tracked_id"
      fi
    done
  fi

  sleep "$INTERVAL"
done

# Cleanup
rm -rf "$TRACK_DIR"
log "Watchdog exiting."
