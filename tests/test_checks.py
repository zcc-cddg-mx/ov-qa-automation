import pytest
from unittest.mock import MagicMock, patch


def _mock_conn(count):
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (count,)
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur
    return mock_conn


# ── flyway ────────────────────────────────────────────────────────────────────

def test_flyway_ok(monkeypatch):
    monkeypatch.setenv("FLYWAY_HISTORY_TABLE", "schema_history")
    monkeypatch.setenv("RENEWAL_SCHEMA", "ECU_POLICY")
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    monkeypatch.setenv("DB_DSN", "jdbc:oracle:thin:@host:1521:sid")

    with patch("checks.db_conn.oracledb.connect", return_value=_mock_conn(1)):
        from checks import flyway
        result = flyway.run("INC23703493")

    assert result["status"] == "ok"
    assert result["name"] == "flyway_history"


def test_flyway_failed(monkeypatch):
    monkeypatch.setenv("FLYWAY_HISTORY_TABLE", "schema_history")
    monkeypatch.setenv("RENEWAL_SCHEMA", "ECU_POLICY")
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    monkeypatch.setenv("DB_DSN", "jdbc:oracle:thin:@host:1521:sid")

    with patch("checks.db_conn.oracledb.connect", return_value=_mock_conn(0)):
        from checks import flyway
        result = flyway.run("INC23703493")

    assert result["status"] == "failed"


def test_flyway_db_error(monkeypatch):
    monkeypatch.setenv("FLYWAY_HISTORY_TABLE", "schema_history")
    monkeypatch.setenv("RENEWAL_SCHEMA", "ECU_POLICY")
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    monkeypatch.setenv("DB_DSN", "jdbc:oracle:thin:@host:1521:sid")

    with patch("checks.db_conn.oracledb.connect", side_effect=Exception("connection refused")):
        from checks import flyway
        with pytest.raises(RuntimeError, match="flyway_history"):
            flyway.run("INC23703493")


# ── endpoint_health ───────────────────────────────────────────────────────────

def _mock_login_resp(token="test-token"):
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {"body": {"accessToken": token}}
    return m


def test_health_ok(monkeypatch):
    monkeypatch.setenv("AMS_POLICY_HOST", "https://uat-ov.zurich.com/portal")
    monkeypatch.setenv("HEALTH_PATH", "/policy/api/v1/health")
    monkeypatch.setenv("AUTH_LOGIN_URL", "https://uat-ov.zurich.com/login")
    monkeypatch.setenv("AUTH_USERNAME", "u")
    monkeypatch.setenv("AUTH_PASSWORD", "p")
    monkeypatch.setenv("AUTH_TENANT", "ec")

    mock_health_resp = MagicMock()
    mock_health_resp.status_code = 200
    mock_health_resp.content = b'{"status":"UP"}'
    mock_health_resp.json.return_value = {"status": "UP"}

    with patch("checks.health.requests.post", return_value=_mock_login_resp()), \
         patch("checks.health.requests.get", return_value=mock_health_resp):
        from checks import health
        result = health.run("ams-policy")

    assert result["status"] == "ok"
    assert result["name"] == "endpoint_health"


def test_health_non_200(monkeypatch):
    monkeypatch.setenv("AMS_POLICY_HOST", "https://uat-ov.zurich.com/portal")
    monkeypatch.setenv("HEALTH_PATH", "/policy/api/v1/health")
    monkeypatch.setenv("AUTH_LOGIN_URL", "https://uat-ov.zurich.com/login")
    monkeypatch.setenv("AUTH_USERNAME", "u")
    monkeypatch.setenv("AUTH_PASSWORD", "p")
    monkeypatch.setenv("AUTH_TENANT", "ec")

    mock_health_resp = MagicMock()
    mock_health_resp.status_code = 503
    mock_health_resp.content = b'{"status":"DOWN"}'
    mock_health_resp.json.return_value = {"status": "DOWN"}

    with patch("checks.health.requests.post", return_value=_mock_login_resp()), \
         patch("checks.health.requests.get", return_value=mock_health_resp):
        from checks import health
        result = health.run("ams-policy")

    assert result["status"] == "failed"


def test_health_timeout(monkeypatch):
    import requests as req
    monkeypatch.setenv("AMS_RULE_HOST", "https://uat-ov.zurich.com/portal")
    monkeypatch.setenv("HEALTH_PATH", "/rule/api/v1/health")
    monkeypatch.setenv("AUTH_LOGIN_URL", "https://uat-ov.zurich.com/login")
    monkeypatch.setenv("AUTH_USERNAME", "u")
    monkeypatch.setenv("AUTH_PASSWORD", "p")
    monkeypatch.setenv("AUTH_TENANT", "ec")

    with patch("checks.health.requests.post", return_value=_mock_login_resp()), \
         patch("checks.health.requests.get", side_effect=req.Timeout):
        from checks import health
        result = health.run("ams-rule")

    assert result["status"] == "failed"
    assert "timeout" in result["detail"]


# ── row_count ─────────────────────────────────────────────────────────────────

def test_row_count_ok_with_expected(monkeypatch):
    monkeypatch.setenv("RENEWAL_SCHEMA", "ECU_POLICY")
    monkeypatch.setenv("RENEWAL_TABLE", "FIXED_RENEWAL_DATA")
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    monkeypatch.setenv("DB_DSN", "jdbc:oracle:thin:@host:1521:sid")

    with patch("checks.db_conn.oracledb.connect", return_value=_mock_conn(100)):
        from checks import renewal
        result = renewal.run_row_count(2026, 7, expected=100)

    assert result["status"] == "ok"
    assert "100" in result["detail"]


def test_row_count_failed_mismatch(monkeypatch):
    monkeypatch.setenv("RENEWAL_SCHEMA", "ECU_POLICY")
    monkeypatch.setenv("RENEWAL_TABLE", "FIXED_RENEWAL_DATA")
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    monkeypatch.setenv("DB_DSN", "jdbc:oracle:thin:@host:1521:sid")

    with patch("checks.db_conn.oracledb.connect", return_value=_mock_conn(80)):
        from checks import renewal
        result = renewal.run_row_count(2026, 7, expected=100)

    assert result["status"] == "failed"
    assert "20 rows missing" in result["detail"]


def test_row_count_ok_no_expected(monkeypatch):
    monkeypatch.setenv("RENEWAL_SCHEMA", "ECU_POLICY")
    monkeypatch.setenv("RENEWAL_TABLE", "FIXED_RENEWAL_DATA")
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    monkeypatch.setenv("DB_DSN", "jdbc:oracle:thin:@host:1521:sid")

    with patch("checks.db_conn.oracledb.connect", return_value=_mock_conn(50)):
        from checks import renewal
        result = renewal.run_row_count(2026, 7, expected=None)

    assert result["status"] == "ok"


def test_row_count_failed_zero_no_expected(monkeypatch):
    monkeypatch.setenv("RENEWAL_SCHEMA", "ECU_POLICY")
    monkeypatch.setenv("RENEWAL_TABLE", "FIXED_RENEWAL_DATA")
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    monkeypatch.setenv("DB_DSN", "jdbc:oracle:thin:@host:1521:sid")

    with patch("checks.db_conn.oracledb.connect", return_value=_mock_conn(0)):
        from checks import renewal
        result = renewal.run_row_count(2026, 7, expected=None)

    assert result["status"] == "failed"


# ── no_renovar_count ──────────────────────────────────────────────────────────

def test_no_renovar_ok(monkeypatch):
    monkeypatch.setenv("RENEWAL_SCHEMA", "ECU_POLICY")
    monkeypatch.setenv("RENEWAL_TABLE", "FIXED_RENEWAL_DATA")
    monkeypatch.setenv("RENEWAL_BLOCKED_FIELD", "renewal_blocked")
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    monkeypatch.setenv("DB_DSN", "jdbc:oracle:thin:@host:1521:sid")

    with patch("checks.db_conn.oracledb.connect", return_value=_mock_conn(5)):
        from checks import renewal
        result = renewal.run_no_renovar_count(2026, 7)

    assert result["status"] == "ok"
    assert "5" in result["detail"]


def test_no_renovar_failed(monkeypatch):
    monkeypatch.setenv("RENEWAL_SCHEMA", "ECU_POLICY")
    monkeypatch.setenv("RENEWAL_TABLE", "FIXED_RENEWAL_DATA")
    monkeypatch.setenv("RENEWAL_BLOCKED_FIELD", "renewal_blocked")
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    monkeypatch.setenv("DB_DSN", "jdbc:oracle:thin:@host:1521:sid")

    with patch("checks.db_conn.oracledb.connect", return_value=_mock_conn(0)):
        from checks import renewal
        result = renewal.run_no_renovar_count(2026, 7)

    assert result["status"] == "failed"


# ── entity_rows ───────────────────────────────────────────────────────────────

def test_entity_rows_ok(monkeypatch):
    monkeypatch.setenv("RULES_SCHEMA", "ECU_RULE")
    monkeypatch.setenv("RULES_TABLE", "ams_rule_entry")
    monkeypatch.setenv("RULES_ENTITY_FIELD", "entity")
    monkeypatch.setenv("RULES_MIGRATION_ID_FIELD", "migration_id")
    monkeypatch.setenv("DB_RULE_USER", "u")
    monkeypatch.setenv("DB_RULE_PASSWORD", "p")
    monkeypatch.setenv("DB_DSN", "jdbc:oracle:thin:@host:1521:sid")

    with patch("checks.db_conn.oracledb.connect", return_value=_mock_conn(10)):
        from checks import rules
        result = rules.run_entity_rows("VHPlanRules", "V2026_test")

    assert result["status"] == "ok"
    assert "VHPlanRules" in result["detail"]


def test_entity_rows_failed(monkeypatch):
    monkeypatch.setenv("RULES_SCHEMA", "ECU_RULE")
    monkeypatch.setenv("RULES_TABLE", "ams_rule_entry")
    monkeypatch.setenv("RULES_ENTITY_FIELD", "entity")
    monkeypatch.setenv("RULES_MIGRATION_ID_FIELD", "migration_id")
    monkeypatch.setenv("DB_RULE_USER", "u")
    monkeypatch.setenv("DB_RULE_PASSWORD", "p")
    monkeypatch.setenv("DB_DSN", "jdbc:oracle:thin:@host:1521:sid")

    with patch("checks.db_conn.oracledb.connect", return_value=_mock_conn(0)):
        from checks import rules
        result = rules.run_entity_rows("VHPlanRules", "V2026_test")

    assert result["status"] == "failed"
