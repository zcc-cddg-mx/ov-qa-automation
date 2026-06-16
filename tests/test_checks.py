import pytest
from unittest.mock import MagicMock, patch


# ── flyway ────────────────────────────────────────────────────────────────────

def test_flyway_ok(monkeypatch):
    monkeypatch.setenv("FLYWAY_HISTORY_TABLE", "flyway_schema_history")
    monkeypatch.setenv("DB_DSN", "postgresql://fake/db")

    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (1,)
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("checks.flyway.psycopg2.connect", return_value=mock_conn):
        from checks import flyway
        result = flyway.run("V2026_test")

    assert result["status"] == "ok"
    assert result["name"] == "flyway_history"


def test_flyway_failed(monkeypatch):
    monkeypatch.setenv("FLYWAY_HISTORY_TABLE", "flyway_schema_history")
    monkeypatch.setenv("DB_DSN", "postgresql://fake/db")

    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (0,)
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("checks.flyway.psycopg2.connect", return_value=mock_conn):
        from checks import flyway
        result = flyway.run("V2026_test")

    assert result["status"] == "failed"


def test_flyway_db_error(monkeypatch):
    monkeypatch.setenv("FLYWAY_HISTORY_TABLE", "flyway_schema_history")
    monkeypatch.setenv("DB_DSN", "postgresql://fake/db")

    with patch("checks.flyway.psycopg2.connect", side_effect=Exception("connection refused")):
        from checks import flyway
        with pytest.raises(RuntimeError, match="flyway_history"):
            flyway.run("V2026_test")


# ── endpoint_health ───────────────────────────────────────────────────────────

def test_health_ok(monkeypatch):
    monkeypatch.setenv("AMS_POLICY_HOST", "ams-policy-dev:8080")
    monkeypatch.setenv("HEALTH_PATH", "/actuator/health")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b'{"status":"UP"}'
    mock_resp.json.return_value = {"status": "UP"}

    with patch("checks.health.requests.get", return_value=mock_resp):
        from checks import health
        result = health.run("ams-policy")

    assert result["status"] == "ok"
    assert result["name"] == "endpoint_health"


def test_health_non_200(monkeypatch):
    monkeypatch.setenv("AMS_POLICY_HOST", "ams-policy-dev:8080")
    monkeypatch.setenv("HEALTH_PATH", "/actuator/health")

    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.content = b'{"status":"DOWN"}'
    mock_resp.json.return_value = {"status": "DOWN"}

    with patch("checks.health.requests.get", return_value=mock_resp):
        from checks import health
        result = health.run("ams-policy")

    assert result["status"] == "failed"


def test_health_timeout(monkeypatch):
    import requests as req
    monkeypatch.setenv("AMS_RULE_HOST", "ams-rule-dev:8080")
    monkeypatch.setenv("HEALTH_PATH", "/actuator/health")

    with patch("checks.health.requests.get", side_effect=req.Timeout):
        from checks import health
        result = health.run("ams-rule")

    assert result["status"] == "failed"
    assert "timeout" in result["detail"]


# ── row_count ─────────────────────────────────────────────────────────────────

def _mock_conn(count):
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (count,)
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn


def test_row_count_ok_with_expected(monkeypatch):
    monkeypatch.setenv("RENEWAL_TABLE", "frd_fixed_renewal_data")
    monkeypatch.setenv("RENEWAL_MIGRATION_ID_FIELD", "migration_id")
    monkeypatch.setenv("DB_DSN", "postgresql://fake/db")

    with patch("checks.renewal.psycopg2.connect", return_value=_mock_conn(100)):
        from checks import renewal
        result = renewal.run_row_count("V2026_test", expected=100)

    assert result["status"] == "ok"


def test_row_count_failed_mismatch(monkeypatch):
    monkeypatch.setenv("RENEWAL_TABLE", "frd_fixed_renewal_data")
    monkeypatch.setenv("RENEWAL_MIGRATION_ID_FIELD", "migration_id")
    monkeypatch.setenv("DB_DSN", "postgresql://fake/db")

    with patch("checks.renewal.psycopg2.connect", return_value=_mock_conn(80)):
        from checks import renewal
        result = renewal.run_row_count("V2026_test", expected=100)

    assert result["status"] == "failed"
    assert "20 rows missing" in result["detail"]


def test_row_count_ok_no_expected(monkeypatch):
    monkeypatch.setenv("RENEWAL_TABLE", "frd_fixed_renewal_data")
    monkeypatch.setenv("RENEWAL_MIGRATION_ID_FIELD", "migration_id")
    monkeypatch.setenv("DB_DSN", "postgresql://fake/db")

    with patch("checks.renewal.psycopg2.connect", return_value=_mock_conn(50)):
        from checks import renewal
        result = renewal.run_row_count("V2026_test", expected=None)

    assert result["status"] == "ok"


def test_row_count_failed_zero_no_expected(monkeypatch):
    monkeypatch.setenv("RENEWAL_TABLE", "frd_fixed_renewal_data")
    monkeypatch.setenv("RENEWAL_MIGRATION_ID_FIELD", "migration_id")
    monkeypatch.setenv("DB_DSN", "postgresql://fake/db")

    with patch("checks.renewal.psycopg2.connect", return_value=_mock_conn(0)):
        from checks import renewal
        result = renewal.run_row_count("V2026_test", expected=None)

    assert result["status"] == "failed"


# ── no_renovar_count ──────────────────────────────────────────────────────────

def test_no_renovar_ok(monkeypatch):
    monkeypatch.setenv("RENEWAL_TABLE", "frd_fixed_renewal_data")
    monkeypatch.setenv("RENEWAL_MIGRATION_ID_FIELD", "migration_id")
    monkeypatch.setenv("RENEWAL_BLOCKED_FIELD", "renewal_blocked")
    monkeypatch.setenv("DB_DSN", "postgresql://fake/db")

    with patch("checks.renewal.psycopg2.connect", return_value=_mock_conn(5)):
        from checks import renewal
        result = renewal.run_no_renovar_count("V2026_test")

    assert result["status"] == "ok"
    assert "5" in result["detail"]


def test_no_renovar_failed(monkeypatch):
    monkeypatch.setenv("RENEWAL_TABLE", "frd_fixed_renewal_data")
    monkeypatch.setenv("RENEWAL_MIGRATION_ID_FIELD", "migration_id")
    monkeypatch.setenv("RENEWAL_BLOCKED_FIELD", "renewal_blocked")
    monkeypatch.setenv("DB_DSN", "postgresql://fake/db")

    with patch("checks.renewal.psycopg2.connect", return_value=_mock_conn(0)):
        from checks import renewal
        result = renewal.run_no_renovar_count("V2026_test")

    assert result["status"] == "failed"


# ── entity_rows ───────────────────────────────────────────────────────────────

def test_entity_rows_ok(monkeypatch):
    monkeypatch.setenv("RULES_TABLE", "ams_rule_entry")
    monkeypatch.setenv("RULES_ENTITY_FIELD", "entity")
    monkeypatch.setenv("RULES_MIGRATION_ID_FIELD", "migration_id")
    monkeypatch.setenv("DB_DSN", "postgresql://fake/db")

    with patch("checks.rules.psycopg2.connect", return_value=_mock_conn(10)):
        from checks import rules
        result = rules.run_entity_rows("VHPlanRules", "V2026_test")

    assert result["status"] == "ok"
    assert "VHPlanRules" in result["detail"]


def test_entity_rows_failed(monkeypatch):
    monkeypatch.setenv("RULES_TABLE", "ams_rule_entry")
    monkeypatch.setenv("RULES_ENTITY_FIELD", "entity")
    monkeypatch.setenv("RULES_MIGRATION_ID_FIELD", "migration_id")
    monkeypatch.setenv("DB_DSN", "postgresql://fake/db")

    with patch("checks.rules.psycopg2.connect", return_value=_mock_conn(0)):
        from checks import rules
        result = rules.run_entity_rows("VHPlanRules", "V2026_test")

    assert result["status"] == "failed"
