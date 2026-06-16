import os
import threading
import pytest

import db as db_module
import worker as worker_module
from app import app as flask_app


@pytest.fixture
def tmp_db(monkeypatch, tmp_path):
    path = str(tmp_path / "test.db")
    monkeypatch.setenv("QA_TASKS_DB", path)
    monkeypatch.setattr(db_module, "DB_PATH", path)
    db_module.init_db()
    return path


@pytest.fixture(autouse=True)
def reset_worker_lock():
    # garantiza que el lock esté libre al inicio de cada test
    if worker_module._lock.locked():
        try:
            worker_module._lock.release()
        except RuntimeError:
            pass
    worker_module._active.clear()
    yield
    if worker_module._lock.locked():
        try:
            worker_module._lock.release()
        except RuntimeError:
            pass
    worker_module._active.clear()


@pytest.fixture
def client(tmp_db):
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


@pytest.fixture
def ren_data_payload():
    return {
        "ticket":         "ZNRX-001",
        "command":        "ren-data",
        "module":         "ams-policy",
        "migration_name": "V2026_06_16__ZNRX_001_test",
        "branch":         "feature/ZNRX_001",
        "aux_branch":     "feature/ZNRX_001_aux",
        "commit_id":      "abc123",
        "year":           2026,
        "month":          6,
        "row_count":      100,
        "callback_url":   "http://localhost:19999/webhook/test",
    }


@pytest.fixture
def rules_payload():
    return {
        "ticket":         "ZNRX-002",
        "command":        "rules",
        "module":         "ams-rule",
        "migration_name": "V2026_06_16__ZNRX_002_test",
        "branch":         "feature/ZNRX_002",
        "aux_branch":     "feature/ZNRX_002_aux",
        "commit_id":      "def456",
        "entity":         "VHPlanRules",
        "callback_url":   "http://localhost:19999/webhook/test",
    }
