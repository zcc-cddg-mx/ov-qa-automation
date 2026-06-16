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


def _mock_resp(status=200):
    m = MagicMock()
    m.status_code = status
    return m


def test_no_url_skips(monkeypatch, capsys):
    task = {**TASK, "callback_url": None}
    monkeypatch.delenv("N8N_CALLBACK_URL", raising=False)
    callback.send(task, CHECKS, "approved", "All passed", "2026-06-16T00:00:00+00:00")
    assert "skipping" in capsys.readouterr().out


def test_sends_approved_payload(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with patch("callback.requests.post", return_value=_mock_resp()) as mock_post, \
         patch("callback.time.sleep"):
        callback.send(TASK, CHECKS, "approved", "All passed", "2026-06-16T00:00:00+00:00")

    mock_post.assert_called_once()
    data = mock_post.call_args.kwargs["data"]
    files = mock_post.call_args.kwargs["files"]
    assert data["status"] == "approved"
    assert data["ticket"] == "ZNRX-001"
    assert "checks_log" in files


def test_sends_error_payload(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with patch("callback.requests.post", return_value=_mock_resp()) as mock_post, \
         patch("callback.time.sleep"):
        callback.send(TASK, [], None, None, "2026-06-16T00:00:00+00:00",
                      error="DB connection refused")

    data = mock_post.call_args.kwargs["data"]
    assert data["status"] == "error"
    assert data["error"] == "DB connection refused"
    assert mock_post.call_args.kwargs["files"] is None


def test_executive_summary_included(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    with patch("callback.executive_summary", return_value="El despliegue fue exitoso.") as mock_ai, \
         patch("callback.requests.post", return_value=_mock_resp()), \
         patch("callback.time.sleep"):
        callback.send(TASK, CHECKS, "approved", "All passed", "2026-06-16T00:00:00+00:00")

    mock_ai.assert_called_once()
    data = callback.requests.post.call_args.kwargs["data"] if hasattr(callback.requests.post, "call_args") else None


def test_executive_summary_included_in_data(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    with patch("callback.executive_summary", return_value="El despliegue fue exitoso."), \
         patch("callback.requests.post", return_value=_mock_resp()) as mock_post, \
         patch("callback.time.sleep"):
        callback.send(TASK, CHECKS, "approved", "All passed", "2026-06-16T00:00:00+00:00")

    data = mock_post.call_args.kwargs["data"]
    assert data["executive_summary"] == "El despliegue fue exitoso."


def test_retries_on_500(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with patch("callback.requests.post", return_value=_mock_resp(500)) as mock_post, \
         patch("callback.time.sleep"):
        callback.send(TASK, CHECKS, "approved", "All passed", "2026-06-16T00:00:00+00:00")

    assert mock_post.call_count == 3


def test_no_retry_on_success(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with patch("callback.requests.post", return_value=_mock_resp()) as mock_post, \
         patch("callback.time.sleep"):
        callback.send(TASK, CHECKS, "approved", "All passed", "2026-06-16T00:00:00+00:00")

    assert mock_post.call_count == 1


def test_retries_on_connection_error(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with patch("callback.requests.post", side_effect=Exception("connection refused")) as mock_post, \
         patch("callback.time.sleep"):
        callback.send(TASK, CHECKS, "approved", "All passed", "2026-06-16T00:00:00+00:00")

    assert mock_post.call_count == 3


def test_fallback_to_env_url(monkeypatch):
    task = {**TASK, "callback_url": None}
    monkeypatch.setenv("N8N_CALLBACK_URL", "http://env-n8n.host/webhook")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with patch("callback.requests.post", return_value=_mock_resp()) as mock_post, \
         patch("callback.time.sleep"):
        callback.send(task, CHECKS, "approved", "All passed", "2026-06-16T00:00:00+00:00")

    assert "env-n8n.host" in mock_post.call_args.args[0]
