import io
import pytest
from unittest.mock import patch

from tests.conftest import _multipart


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_validate_missing_fields(client):
    r = client.post("/validate", data={"ticket": "ZNRX-001"},
                    content_type="multipart/form-data")
    assert r.status_code == 400
    body = r.get_json()
    assert body["status"] == "error"
    assert "command" in body["error"]


def test_validate_ren_data_missing_file(client):
    r = client.post("/validate", data={
        "ticket": "ZNRX-001", "command": "ren-data", "module": "ams-policy",
        "migration_name": "V_test", "branch": "f/test", "aux_branch": "f/test_aux",
        "commit_id": "abc", "year": "2026", "month": "7",
    }, content_type="multipart/form-data")
    assert r.status_code == 400
    assert "file" in r.get_json()["error"]


def test_validate_ren_data_missing_year_month(client):
    form, files = _multipart({
        "ticket": "ZNRX-001", "command": "ren-data", "module": "ams-policy",
        "migration_name": "V_test", "branch": "f/test", "aux_branch": "f/test_aux",
        "commit_id": "abc",
    })
    r = client.post("/validate", data={**form, **files},
                    content_type="multipart/form-data")
    assert r.status_code == 400
    assert "year" in r.get_json()["error"]


def test_validate_rules_missing_entity(client):
    r = client.post("/validate", data={
        "ticket": "ZNRX-001", "command": "rules", "module": "ams-rule",
        "migration_name": "V_test", "branch": "f/test", "aux_branch": "f/test_aux",
        "commit_id": "abc",
    }, content_type="multipart/form-data")
    assert r.status_code == 400
    assert "entity" in r.get_json()["error"]


def test_validate_accepted_ren_data(client, ren_data_form):
    form, files = _multipart(ren_data_form)
    with patch("worker.run"), patch("worker._set_active"):
        r = client.post("/validate", data={**form, **files},
                        content_type="multipart/form-data")
    assert r.status_code == 202
    body = r.get_json()
    assert body["status"] == "queued"
    assert "task_id" in body


def test_validate_accepted_rules(client, rules_form):
    r = client.post("/validate", data={k: str(v) for k, v in rules_form.items()},
                    content_type="multipart/form-data")
    # rules does not require file
    with patch("worker.run"), patch("worker._set_active"):
        r = client.post("/validate", data={k: str(v) for k, v in rules_form.items()},
                        content_type="multipart/form-data")
    assert r.status_code == 202


def test_validate_rejected_when_locked(client, ren_data_form, rules_form):
    form, files = _multipart(ren_data_form)
    with patch("worker.run"), patch("worker._set_active"):
        client.post("/validate", data={**form, **files},
                    content_type="multipart/form-data")

    with patch("worker.is_locked", return_value=True), \
         patch("worker.get_active", return_value={"task_id": "prev", "ticket": "ZNRX-000"}):
        r = client.post("/validate", data={k: str(v) for k, v in rules_form.items()},
                        content_type="multipart/form-data")

    assert r.status_code == 202
    body = r.get_json()
    assert body["status"] == "rejected"
    assert body["active_task"]["task_id"] == "prev"


def test_status_not_found(client):
    r = client.get("/status/nonexistent")
    assert r.status_code == 404


def test_status_found(client, ren_data_form):
    form, files = _multipart(ren_data_form)
    with patch("worker.run"), patch("worker._set_active"):
        r = client.post("/validate", data={**form, **files},
                        content_type="multipart/form-data")
    task_id = r.get_json()["task_id"]

    r = client.get(f"/status/{task_id}")
    assert r.status_code == 200
    assert r.get_json()["ticket"] == "ZNRX-001"


def test_tasks_list(client, ren_data_form, rules_form):
    form, files = _multipart(ren_data_form)
    with patch("worker.run"), patch("worker._set_active"), \
         patch("worker.is_locked", return_value=False):
        client.post("/validate", data={**form, **files},
                    content_type="multipart/form-data")
        client.post("/validate", data={k: str(v) for k, v in rules_form.items()},
                    content_type="multipart/form-data")

    r = client.get("/tasks?limit=10")
    assert r.status_code == 200
    assert len(r.get_json()) == 2


def test_tasks_default_limit(client):
    r = client.get("/tasks")
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)
