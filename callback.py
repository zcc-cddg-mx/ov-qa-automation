import os
import time
import requests

from checks.summary import format_log, executive_summary

_DELAYS = [2, 4, 8]
_VERIFY_SSL = os.environ.get("CALLBACK_VERIFY_SSL", "true").lower() != "false"


def send(task: dict, check_results: list, overall: str, summary: str,
         completed_at: str, error: str | None = None):
    url = task.get("callback_url") or os.environ.get("N8N_CALLBACK_URL")
    if not url:
        print("[N8N]    no callback_url configured — skipping")
        return

    if error:
        data = {
            "ticket":       task["ticket"],
            "status":       "error",
            "task_id":      task["task_id"],
            "error":        error,
            "completed_at": completed_at,
        }
        files = None
    else:
        log_text = format_log(task, check_results, overall, summary)
        exec_summary = executive_summary(log_text, overall, task={**task, "summary": summary},
                                         check_results=check_results)

        data = {
            "ticket":            task["ticket"],
            "status":            overall,
            "task_id":           task["task_id"],
            "command":           task["command"],
            "module":            task.get("module", ""),
            "migration_name":    task.get("migration_name", ""),
            "summary":           summary,
            "executive_summary": exec_summary,
            "completed_at":      completed_at,
        }
        files = {
            "checks_log": (
                f"checks_{task['task_id']}.txt",
                log_text.encode("utf-8"),
                "text/plain",
            )
        }
    for attempt, delay in enumerate(_DELAYS, start=1):
        try:
            resp = requests.post(url, data=data, files=files, timeout=10, verify=_VERIFY_SSL)
            print(f"[N8N]    callback → {url} status={resp.status_code} (attempt {attempt})")
            if resp.status_code < 500:
                return
        except Exception as exc:
            print(f"[N8N]    callback → {url} error={exc} (attempt {attempt})")

        if attempt < len(_DELAYS):
            time.sleep(delay)

    print(f"[N8N]    callback failed after {len(_DELAYS)} attempts")
