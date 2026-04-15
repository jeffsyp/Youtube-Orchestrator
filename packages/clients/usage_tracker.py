"""Track API usage across all external services. Append-only log file."""

import json
import os
import time
import threading
from datetime import datetime

_lock = threading.Lock()

USAGE_LOG = os.path.join(os.path.dirname(__file__), "..", "..", "output", "api_usage.jsonl")
USAGE_SUMMARY = os.path.join(os.path.dirname(__file__), "..", "..", "output", "api_usage.json")


def track(service: str, success: bool, elapsed: float = 0, run_id: int | None = None):
    """Record an API call by appending to log file."""
    entry = {
        "service": service,
        "success": success,
        "elapsed": round(elapsed, 2) if elapsed else 0,
        "run_id": run_id,
        "ts": datetime.now().isoformat(),
    }
    with _lock:
        try:
            os.makedirs(os.path.dirname(USAGE_LOG), exist_ok=True)
            with open(USAGE_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass
    # Rebuild summary periodically
    _rebuild_summary()


_last_rebuild = 0


def _rebuild_summary():
    """Rebuild the summary JSON from the append-only log. Max once per 5 seconds."""
    global _last_rebuild
    now = time.time()
    if now - _last_rebuild < 5:
        return
    _last_rebuild = now

    try:
        if not os.path.exists(USAGE_LOG):
            return

        services = {}
        per_run = {}

        with open(USAGE_LOG) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue

                svc = e.get("service", "unknown")
                success = e.get("success", False)
                elapsed = e.get("elapsed", 0)
                rid = e.get("run_id")

                if svc not in services:
                    services[svc] = {"calls": 0, "successes": 0, "failures": 0, "total_time": 0.0}
                services[svc]["calls"] += 1
                if success:
                    services[svc]["successes"] += 1
                else:
                    services[svc]["failures"] += 1
                services[svc]["total_time"] += elapsed

                if rid:
                    rid_str = str(rid)
                    if rid_str not in per_run:
                        per_run[rid_str] = {}
                    if svc not in per_run[rid_str]:
                        per_run[rid_str][svc] = {"calls": 0, "successes": 0, "failures": 0}
                    per_run[rid_str][svc]["calls"] += 1
                    if success:
                        per_run[rid_str][svc]["successes"] += 1
                    else:
                        per_run[rid_str][svc]["failures"] += 1

        # Format for display
        clean = {}
        for svc, data in services.items():
            clean[svc] = {
                "calls": data["calls"],
                "successes": data["successes"],
                "failures": data["failures"],
                "success_rate": f"{(data['successes'] / data['calls'] * 100):.0f}%" if data["calls"] > 0 else "0%",
                "avg_time": f"{(data['total_time'] / data['calls']):.1f}s" if data["calls"] > 0 and data["total_time"] > 0 else None,
            }

        with open(USAGE_SUMMARY, "w") as f:
            json.dump({
                "services": clean,
                "per_run": per_run,
                "updated": datetime.now().isoformat(),
            }, f, indent=2)
    except Exception:
        pass


def get_summary() -> dict:
    """Get current usage summary from disk."""
    try:
        if os.path.exists(USAGE_SUMMARY):
            with open(USAGE_SUMMARY) as f:
                return json.load(f)
    except Exception:
        pass
    return {"services": {}, "per_run": {}, "updated": None}
