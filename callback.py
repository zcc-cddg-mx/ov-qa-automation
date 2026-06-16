import os
import time
import requests

_DELAYS = [2, 4, 8]


def send(task: dict, check_results: list, overall: str, summary: str,
         completed_at: str, error: str | None = None):
    url = task.get("callback_url") or os.environ.get("N8N_CALLBACK_URL")
    if not url:
        print("[N8N]    no callback_url configured — skipping")
        return

    if error:
        payload = {
            "ticket":       task["ticket"],
            "status":       "error",
            "task_id":      task["task_id"],
            "error":        error,
            "completed_at": completed_at,
        }
    else:
        payload = {
            "ticket":         task["ticket"],
            "status":         overall,
            "task_id":        task["task_id"],
            "command":        task["command"],
            "module":         task["module"],
            "migration_name": task["migration_name"],
            "branch":         task["branch"],
            "aux_branch":     task["aux_branch"],
            "commit_id":      task["commit_id"],
            "summary":        summary,
            "checks":         check_results,
            "completed_at":   completed_at,
        }

    for attempt, delay in enumerate(_DELAYS, start=1):
        try:
            resp = requests.post(url, json=payload, timeout=10)
            print(f"[N8N]    callback → {url} status={resp.status_code} (attempt {attempt})")
            if resp.status_code < 500:
                return
        except Exception as exc:
            print(f"[N8N]    callback → {url} error={exc} (attempt {attempt})")

        if attempt < len(_DELAYS):
            time.sleep(delay)

    print(f"[N8N]    callback failed after {len(_DELAYS)} attempts")
