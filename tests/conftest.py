import io
import os
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
def client(tmp_db, tmp_path, monkeypatch):
    monkeypatch.setenv("QA_UPLOAD_DIR", str(tmp_path / "uploads"))
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def _multipart(data: dict, file_content: bytes = b"fake-excel") -> tuple[dict, dict]:
    form = {k: str(v) for k, v in data.items()}
    files = {"file": (io.BytesIO(file_content), "baseticketMES.xlsx",
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    return form, files


@pytest.fixture
def ren_data_form():
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
def rules_form():
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


# keep old json-payload fixture names as aliases for worker/db tests
@pytest.fixture
def ren_data_payload(ren_data_form):
    return ren_data_form


@pytest.fixture
def rules_payload(rules_form):
    return rules_form
