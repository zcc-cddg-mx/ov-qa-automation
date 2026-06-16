import pytest
from unittest.mock import patch, MagicMock
import callback


TASK = {
    "task_id":        "t001",
    "ticket":         "ZNRX-001",
    "command":        "ren-data",
    "module":         "ams-policy",
    "migration_name": "V2026_test",
    "branch":         "feature/test",
    "aux_branch":     "feature/test_aux",
    "commit_id":      "abc123",
    "callback_url":   "http://n8n.host/webhook/qa-result",
}

CHECKS = [{"name": "flyway_history", "status": "ok", "detail": "ok"}]


def test_no_url_skips(monkeypatch, capsys):
    task = {**TASK, "callback_url": None}
    monkeypatch.delenv("N8N_CALLBACK_URL", raising=False)
    callback.send(task, CHECKS, "approved", "All passed", "2026-06-16T00:00:00+00:00")
    assert "skipping" in capsys.readouterr().out


def test_sends_approved_payload():
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("callback.requests.post", return_value=mock_resp) as mock_post, \
         patch("callback.time.sleep"):
        callback.send(TASK, CHECKS, "approved", "All passed", "2026-06-16T00:00:00+00:00")

    mock_post.assert_called_once()
    payload = mock_post.call_args.kwargs["json"]
    assert payload["status"] == "approved"
    assert payload["ticket"] == "ZNRX-001"
    assert payload["checks"] == CHECKS


def test_sends_error_payload():
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("callback.requests.post", return_value=mock_resp) as mock_post, \
         patch("callback.time.sleep"):
        callback.send(TASK, [], None, None, "2026-06-16T00:00:00+00:00",
                      error="DB connection refused")

    payload = mock_post.call_args.kwargs["json"]
    assert payload["status"] == "error"
    assert payload["error"] == "DB connection refused"
    assert "command" not in payload


def test_retries_on_500():
    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with patch("callback.requests.post", return_value=mock_resp) as mock_post, \
         patch("callback.time.sleep"):
        callback.send(TASK, CHECKS, "approved", "All passed", "2026-06-16T00:00:00+00:00")

    assert mock_post.call_count == 3


def test_no_retry_on_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("callback.requests.post", return_value=mock_resp) as mock_post, \
         patch("callback.time.sleep"):
        callback.send(TASK, CHECKS, "approved", "All passed", "2026-06-16T00:00:00+00:00")

    assert mock_post.call_count == 1


def test_retries_on_connection_error():
    with patch("callback.requests.post", side_effect=Exception("connection refused")) as mock_post, \
         patch("callback.time.sleep"):
        callback.send(TASK, CHECKS, "approved", "All passed", "2026-06-16T00:00:00+00:00")

    assert mock_post.call_count == 3


def test_fallback_to_env_url(monkeypatch):
    task = {**TASK, "callback_url": None}
    monkeypatch.setenv("N8N_CALLBACK_URL", "http://env-n8n.host/webhook")

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("callback.requests.post", return_value=mock_resp) as mock_post, \
         patch("callback.time.sleep"):
        callback.send(task, CHECKS, "approved", "All passed", "2026-06-16T00:00:00+00:00")

    assert "env-n8n.host" in mock_post.call_args.args[0]
