import time
import pytest
from unittest.mock import patch


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_validate_missing_fields(client):
    r = client.post("/validate", json={"ticket": "ZNRX-001"})
    assert r.status_code == 400
    body = r.get_json()
    assert body["status"] == "error"
    assert "command" in body["error"]


def test_validate_ren_data_missing_year_month(client):
    r = client.post("/validate", json={
        "ticket": "ZNRX-001", "command": "ren-data", "module": "ams-policy",
        "migration_name": "V_test", "branch": "f/test", "aux_branch": "f/test_aux",
        "commit_id": "abc"
    })
    assert r.status_code == 400
    assert "year" in r.get_json()["error"]


def test_validate_rules_missing_entity(client):
    r = client.post("/validate", json={
        "ticket": "ZNRX-001", "command": "rules", "module": "ams-rule",
        "migration_name": "V_test", "branch": "f/test", "aux_branch": "f/test_aux",
        "commit_id": "abc"
    })
    assert r.status_code == 400
    assert "entity" in r.get_json()["error"]


def test_validate_accepted(client, ren_data_payload):
    with patch("worker.run"), patch("worker._set_active"):
        r = client.post("/validate", json=ren_data_payload)
    assert r.status_code == 202
    body = r.get_json()
    assert body["status"] == "queued"
    assert "task_id" in body


def test_validate_rejected_when_locked(client, ren_data_payload, rules_payload):
    with patch("worker.run"), patch("worker._set_active"):
        client.post("/validate", json=ren_data_payload)

    with patch("worker.is_locked", return_value=True), \
         patch("worker.get_active", return_value={"task_id": "prev", "ticket": "ZNRX-000"}):
        r = client.post("/validate", json=rules_payload)

    assert r.status_code == 202
    body = r.get_json()
    assert body["status"] == "rejected"
    assert body["active_task"]["task_id"] == "prev"


def test_status_not_found(client):
    r = client.get("/status/nonexistent")
    assert r.status_code == 404


def test_status_found(client, ren_data_payload):
    with patch("worker.run"), patch("worker._set_active"):
        r = client.post("/validate", json=ren_data_payload)
    task_id = r.get_json()["task_id"]

    r = client.get(f"/status/{task_id}")
    assert r.status_code == 200
    assert r.get_json()["ticket"] == "ZNRX-001"


def test_tasks_list(client, ren_data_payload, rules_payload):
    with patch("worker.run"), patch("worker._set_active"), \
         patch("worker.is_locked", return_value=False):
        client.post("/validate", json=ren_data_payload)
        client.post("/validate", json=rules_payload)

    r = client.get("/tasks?limit=10")
    assert r.status_code == 200
    assert len(r.get_json()) == 2


def test_tasks_default_limit(client):
    r = client.get("/tasks")
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)
