import json
import time
import pytest
from unittest.mock import patch, MagicMock
import db as db_module
import worker


TASK = {
    "task_id":        "w001",
    "ticket":         "ZNRX-001",
    "command":        "ren-data",
    "module":         "ams-policy",
    "migration_name": "V2026_test",
    "branch":         "feature/test",
    "aux_branch":     "feature/test_aux",
    "commit_id":      "abc123",
    "input_path":     None,
    "sample_size":    10,
    "year":           2026,
    "month":          6,
    "row_count":      100,
    "entity":         None,
    "callback_url":   None,
}


def _insert_task(tmp_db, task_id="w001"):
    db_module.insert_task({
        "task_id": task_id, "ticket": "ZNRX-001", "status": "queued",
        "command": "ren-data", "module": "ams-policy",
        "migration_name": "V2026_test", "branch": "feature/test",
        "aux_branch": "feature/test_aux", "commit_id": "abc123",
        "input_path": None, "sample_size": 10,
        "result": None, "checks": json.dumps([]), "summary": None, "error": None,
        "created_at": "2026-06-16T10:00:00+00:00",
        "updated_at": "2026-06-16T10:00:00+00:00",
    })


def _ok_check(name):
    return {"name": name, "status": "ok", "detail": "ok"}


def _failed_check(name):
    return {"name": name, "status": "failed", "detail": "failed"}


def test_worker_approved(tmp_db):
    _insert_task(tmp_db)

    checks_ok = [_ok_check("flyway_history"), _ok_check("endpoint_health"),
                 _ok_check("row_count"), _ok_check("no_renovar_count")]

    with patch("worker.flyway.run", return_value=checks_ok[0]), \
         patch("worker.health.run", return_value=checks_ok[1]), \
         patch("worker.renewal.run_row_count", return_value=checks_ok[2]) as mock_rc, \
         patch("worker.renewal.run_no_renovar_count", return_value=checks_ok[3]) as mock_nr, \
         patch("callback.send"):
        worker._execute({**TASK})

    mock_rc.assert_called_once_with(2026, 6, 100)
    mock_nr.assert_called_once_with(2026, 6)

    row = db_module.get_task("w001")
    assert row["status"] == "done"
    assert row["result"] == "approved"
    assert len(row["checks"]) == 4


def test_worker_rejected_partial_failure(tmp_db):
    _insert_task(tmp_db)

    with patch("worker.flyway.run", return_value=_ok_check("flyway_history")), \
         patch("worker.health.run", return_value=_ok_check("endpoint_health")), \
         patch("worker.renewal.run_row_count", return_value=_failed_check("row_count")), \
         patch("worker.renewal.run_no_renovar_count", return_value=_failed_check("no_renovar_count")), \
         patch("callback.send"):
        worker._execute({**TASK})


    row = db_module.get_task("w001")
    assert row["result"] == "rejected"
    assert "2 check(s) failed" in row["summary"]


def test_worker_all_checks_run_before_resolving(tmp_db):
    _insert_task(tmp_db)
    ran = []

    def track(name):
        def _inner(*args, **kwargs):
            ran.append(name)
            return _failed_check(name)
        return _inner

    with patch("worker.flyway.run", side_effect=track("flyway_history")), \
         patch("worker.health.run", side_effect=track("endpoint_health")), \
         patch("worker.renewal.run_row_count", side_effect=track("row_count")), \
         patch("worker.renewal.run_no_renovar_count", side_effect=track("no_renovar_count")), \
         patch("callback.send"):
        worker._execute({**TASK})


    assert ran == ["flyway_history", "endpoint_health", "row_count", "no_renovar_count"]


def test_worker_error_on_exception(tmp_db):
    _insert_task(tmp_db)

    with patch("worker.flyway.run", side_effect=RuntimeError("DB down")), \
         patch("callback.send"):
        worker._execute({**TASK})

    row = db_module.get_task("w001")
    assert row["status"] == "error"
    assert "DB down" in row["error"]


def test_worker_callback_always_fired(tmp_db):
    _insert_task(tmp_db)

    with patch("worker.flyway.run", side_effect=RuntimeError("boom")), \
         patch("callback.send") as mock_cb:
        worker._execute({**TASK})

    mock_cb.assert_called_once()


def test_worker_rules_command(tmp_db):
    task = {**TASK, "task_id": "w002", "command": "rules",
            "module": "ams-rule", "entity": "VHPlanRules"}
    db_module.insert_task({
        "task_id": "w002", "ticket": "ZNRX-001", "status": "queued",
        "command": "rules", "module": "ams-rule",
        "migration_name": "V2026_test", "branch": "feature/test",
        "aux_branch": "feature/test_aux", "commit_id": "abc123",
        "input_path": None, "sample_size": 10,
        "result": None, "checks": json.dumps([]), "summary": None, "error": None,
        "created_at": "2026-06-16T10:00:00+00:00",
        "updated_at": "2026-06-16T10:00:00+00:00",
    })

    with patch("worker.flyway.run", return_value=_ok_check("flyway_history")), \
         patch("worker.health.run", return_value=_ok_check("endpoint_health")), \
         patch("worker.rules.run_entity_rows", return_value=_ok_check("entity_rows")) as mock_entity, \
         patch("callback.send"):
        worker._execute(task)

    mock_entity.assert_called_once_with("VHPlanRules", "V2026_test")
    row = db_module.get_task("w002")
    assert row["result"] == "approved"
    assert len(row["checks"]) == 3
