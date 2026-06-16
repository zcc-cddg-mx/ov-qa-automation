from unittest.mock import patch, MagicMock
from checks.summary import format_log, executive_summary

TASK = {"ticket": "ZNRX-001", "task_id": "t001", "command": "ren-data", "module": "ams-policy"}
CHECKS = [
    {"name": "flyway_history", "status": "ok", "detail": "migration recorded"},
    {"name": "quote_flow", "status": "ok", "detail": "10/10 quotable plates ok"},
]


def test_format_log_contains_checks():
    log = format_log(TASK, CHECKS, "approved", "All 2 checks passed")
    assert "[CHECK]  flyway_history — ok" in log
    assert "[CHECK]  quote_flow — ok" in log
    assert "[DONE]   All 2 checks passed" in log


def test_executive_summary_no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = executive_summary("log text", "approved")
    assert result == ""


def test_executive_summary_calls_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")

    mock_choice = MagicMock()
    mock_choice.message.content = "El despliegue fue aprobado exitosamente."
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    with patch("checks.summary.OpenAI", return_value=mock_client):
        result = executive_summary("log text", "approved")

    assert result == "El despliegue fue aprobado exitosamente."


def test_executive_summary_openai_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    with patch("checks.summary.OpenAI", side_effect=Exception("API error")):
        result = executive_summary("log text", "approved")

    assert result == ""
