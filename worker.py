import threading
from datetime import datetime, timezone

from db import update_task

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
    try:
        update_task(task_id, status="running", updated_at=_now())
        print(f"[CHECK]  task_id={task_id} ticket={task['ticket']} running (stub)")

        # --- Fase 3: checks reales van aquí ---
        checks = []
        result = "approved"
        summary = "Stub — no checks executed yet"
        # --------------------------------------

        import json
        update_task(
            task_id,
            status="done",
            result=result,
            checks=json.dumps(checks),
            summary=summary,
            updated_at=_now(),
        )
        print(f"[DONE]   task_id={task_id} result={result}")

    except Exception as exc:
        import json
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
