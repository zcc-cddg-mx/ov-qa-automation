import json
import threading
from datetime import datetime, timezone

from db import update_task
import checks.flyway as flyway
import checks.health as health
import checks.renewal as renewal
import checks.rules as rules

_lock = threading.Lock()
_active: dict = {}
_active_lock = threading.Lock()


def is_locked():
    return not _lock.acquire(blocking=False)


def release():
    try:
        _lock.release()
    except RuntimeError:
        pass


def get_active():
    with _active_lock:
        return dict(_active) if _active else None


def _set_active(task):
    with _active_lock:
        _active.clear()
        if task:
            _active.update(task)


def run(task):
    thread = threading.Thread(target=_execute, args=(task,), daemon=True)
    thread.start()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _execute(task):
    task_id = task["task_id"]
    command = task["command"]
    module = task["module"]
    migration_name = task["migration_name"]

    try:
        update_task(task_id, status="running", updated_at=_now())
        print(f"[RECV]   task_id={task_id} ticket={task['ticket']} running")

        check_results = []

        # flyway_history — ambos comandos
        result = flyway.run(migration_name)
        check_results.append(result)
        print(f"[CHECK]  flyway_history — {result['status']} ({result['detail']})")

        # endpoint_health — ambos comandos
        result = health.run(module)
        check_results.append(result)
        print(f"[CHECK]  endpoint_health — {result['status']} ({result['detail']})")

        # checks específicos por command
        if command == "ren-data":
            result = renewal.run_row_count(migration_name, task.get("row_count"))
            check_results.append(result)
            print(f"[CHECK]  row_count — {result['status']} ({result['detail']})")

            result = renewal.run_no_renovar_count(migration_name)
            check_results.append(result)
            print(f"[CHECK]  no_renovar_count — {result['status']} ({result['detail']})")

        elif command == "rules":
            result = rules.run_entity_rows(task["entity"], migration_name)
            check_results.append(result)
            print(f"[CHECK]  entity_rows — {result['status']} ({result['detail']})")

        failed = [c for c in check_results if c["status"] == "failed"]
        overall = "approved" if not failed else "rejected"
        summary = (
            f"All {len(check_results)} checks passed"
            if not failed
            else f"{len(failed)} check(s) failed"
        )

        update_task(
            task_id,
            status="done",
            result=overall,
            checks=json.dumps(check_results),
            summary=summary,
            updated_at=_now(),
        )
        print(f"[DONE]   task_id={task_id} result={overall} ({summary})")

    except Exception as exc:
        update_task(
            task_id,
            status="error",
            error=str(exc),
            checks=json.dumps([]),
            updated_at=_now(),
        )
        print(f"[ERROR]  task_id={task_id} {exc}")

    finally:
        _set_active(None)
        release()
