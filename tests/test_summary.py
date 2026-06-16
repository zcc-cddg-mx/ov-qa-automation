from unittest.mock import patch, MagicMock
from checks.summary import format_log, executive_summary, _group_checks

TASK = {
    "ticket": "ZNRX-001", "task_id": "t001",
    "command": "ren-data", "module": "ams-policy", "sample_size": 10,
    "summary": "All 15 checks passed",
}
CHECKS = [
    {"name": "flyway_history",   "status": "ok", "detail": "migration recorded"},
    {"name": "endpoint_health",  "status": "ok", "detail": "200 OK"},
    {"name": "row_count",        "status": "ok", "detail": "1589 rows"},
    {"name": "no_renovar_count", "status": "ok", "detail": "14 rows"},
    {"name": "quote_flow:P001",  "status": "ok", "detail": "ok"},
    {"name": "quote_flow",       "status": "ok", "detail": "10/10 ok"},
]


def test_format_log_contains_checks():
    log = format_log(TASK, CHECKS, "approved", "All 15 checks passed")
    assert "[CHECK]  flyway_history — ok" in log
    assert "[CHECK]  quote_flow — ok" in log
    assert "[DONE]   All 15 checks passed" in log


def test_group_checks():
    groups = {c["category"]: c["status"] for c in _group_checks(CHECKS)}
    assert groups["database"]       == "ok"
    assert groups["api"]            == "ok"
    assert groups["data"]           == "ok"
    assert groups["business_rules"] == "ok"


def test_executive_summary_no_credentials_rejected(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = executive_summary("log", "rejected", TASK, CHECKS)
    assert result == ""


def test_executive_summary_uses_anthropic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "sk-test")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://mock.zurich.com")

    with patch("checks.summary._call_anthropic", return_value="Resumen ejecutivo.") as mock_a, \
         patch("checks.summary._call_openai") as mock_o:
        result = executive_summary("log", "approved", TASK, CHECKS)

    assert result == "Resumen ejecutivo."
    mock_a.assert_called_once()
    mock_o.assert_not_called()


def test_executive_summary_fallback_openai(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    with patch("checks.summary._call_openai", return_value="OpenAI summary.") as mock_o:
        result = executive_summary("log", "approved", TASK, CHECKS)

    assert result == "OpenAI summary."
    mock_o.assert_called_once()


def test_executive_summary_anthropic_error_fallback(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "sk-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-oai-test")

    with patch("checks.summary._call_anthropic", side_effect=Exception("timeout")), \
         patch("checks.summary._call_openai", return_value="Fallback summary."):
        result = executive_summary("log", "approved", TASK, CHECKS)

    assert result == "Fallback summary."


def test_executive_summary_static_fallback_approved(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("QA_ENVIRONMENT", "UAT")
    task_with_date = {**TASK, "year": 2026, "month": 3}
    result = executive_summary("log", "approved", task_with_date, CHECKS)
    assert "marzo 2026" in result
    assert TASK["ticket"] in result
    assert TASK["module"] in result


def test_executive_summary_static_fallback_not_used_on_rejected(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = executive_summary("log", "rejected", TASK, CHECKS)
    assert result == ""
