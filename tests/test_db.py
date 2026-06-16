import json
import pytest
import db as db_module


def _task(task_id="t001"):
    return {
        "task_id":        task_id,
        "ticket":         "ZNRX-001",
        "status":         "queued",
        "command":        "ren-data",
        "module":         "ams-policy",
        "migration_name": "V2026_test",
        "branch":         "feature/test",
        "aux_branch":     "feature/test_aux",
        "commit_id":      "abc123",
        "input_path":     None,
        "sample_size":    None,
        "year":           None,
        "month":          None,
        "result":         None,
        "checks":         json.dumps([]),
        "summary":        None,
        "error":          None,
        "created_at":     "2026-06-16T10:00:00+00:00",
        "updated_at":     "2026-06-16T10:00:00+00:00",
    }


def test_init_creates_table(tmp_db):
    task = db_module.get_task("nonexistent")
    assert task is None


def test_insert_and_get(tmp_db):
    db_module.insert_task(_task("t001"))
    row = db_module.get_task("t001")
    assert row["ticket"] == "ZNRX-001"
    assert row["status"] == "queued"
    assert row["checks"] == []


def test_update_status(tmp_db):
    db_module.insert_task(_task("t002"))
    db_module.update_task("t002", status="running", updated_at="2026-06-16T10:01:00+00:00")
    row = db_module.get_task("t002")
    assert row["status"] == "running"


def test_update_result(tmp_db):
    db_module.insert_task(_task("t003"))
    checks = [{"name": "flyway_history", "status": "ok", "detail": "ok"}]
    db_module.update_task("t003", status="done", result="approved",
                          checks=json.dumps(checks), summary="All passed",
                          updated_at="2026-06-16T10:02:00+00:00")
    row = db_module.get_task("t003")
    assert row["result"] == "approved"
    assert row["checks"][0]["name"] == "flyway_history"


def test_list_tasks_order_and_limit(tmp_db):
    for i in range(5):
        t = _task(f"t{i:03d}")
        t["created_at"] = f"2026-06-16T10:0{i}:00+00:00"
        db_module.insert_task(t)
    rows = db_module.list_tasks(3)
    assert len(rows) == 3
    assert rows[0]["created_at"] > rows[1]["created_at"]


def test_list_tasks_max_200(tmp_db):
    for i in range(10):
        t = _task(f"big{i:03d}")
        t["created_at"] = f"2026-06-16T10:00:00+00:00"
        db_module.insert_task(t)
    rows = db_module.list_tasks(999)
    assert len(rows) <= 200
