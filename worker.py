import json
import os
import threading
from datetime import datetime, timezone

from db import update_task
import callback
import checks.flyway as flyway
import checks.health as health
import checks.renewal as renewal
import checks.rules as rules
import checks.quote as quote
from checks.quote import run_from_excel

_lock = threading.Lock()
_active: dict = {}
_active_lock = threading.Lock()


def is_locked() -> bool:
    return _lock.locked()


def acquire() -> bool:
    return _lock.acquire(blocking=False)


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

    check_results = []
    overall = None
    summary = None
    exec_error = None
    completed_at = None

    try:
        update_task(task_id, status="running", updated_at=_now())
        print(f"[RECV]   task_id={task_id} ticket={task['ticket']} running")

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
            result = renewal.run_row_count(task["year"], task["month"], task.get("row_count"))
            check_results.append(result)
            print(f"[CHECK]  row_count — {result['status']} ({result['detail']})")

            result = renewal.run_no_renovar_count(task["year"], task["month"])
            check_results.append(result)
            print(f"[CHECK]  no_renovar_count — {result['status']} ({result['detail']})")

            if task.get("input_path"):
                min_ok = int(os.environ.get("QA_QUOTE_MIN_OK_COUNT", "1"))
                quote_results, plates = run_from_excel(
                    task["input_path"], task["year"], task["month"],
                    task.get("sample_size"),
                )
                print(f"[CHECK]  quote_flow — muestra {len(plates)} placas")
                for qr in quote_results:
                    check_results.append(qr)
                    print(f"[CHECK]  quote_flow:{qr['name'].split(':',1)[-1]} — {qr['status']} ({qr['detail']})")

                quotable = [r for r in quote_results if r["status"] != "skipped"]
                ok_count = sum(1 for r in quotable if r["status"] == "ok")
                skipped = len(quote_results) - len(quotable)
                batch_ok = ok_count >= min_ok
                batch_status = "ok" if batch_ok else "failed"
                batch_detail = (
                    f"{ok_count}/{len(quotable)} quotable plates ok (min={min_ok})"
                    + (f", {skipped} skipped (non-quotable)" if skipped else "")
                )
                batch_check = {"name": "quote_flow", "status": batch_status, "detail": batch_detail}
                check_results.append(batch_check)
                print(f"[CHECK]  quote_flow — {batch_status} ({batch_detail})")

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
        completed_at = _now()

        update_task(
            task_id,
            status="done",
            result=overall,
            checks=json.dumps(check_results),
            summary=summary,
            updated_at=completed_at,
        )
        print(f"[DONE]   task_id={task_id} result={overall} ({summary})")

    except Exception as exc:
        exec_error = str(exc)
        completed_at = _now()
        update_task(
            task_id,
            status="error",
            error=exec_error,
            checks=json.dumps(check_results),
            updated_at=completed_at,
        )
        print(f"[ERROR]  task_id={task_id} {exec_error}")

    finally:
        callback.send(task, check_results, overall, summary, completed_at, exec_error)
        _set_active(None)
        release()
