import pytest
import requests.exceptions
from unittest.mock import MagicMock, patch


# shared mock helpers ──────────────────────────────────────────────────────────

def _mock_vehicle_data_resp(chassis="VF3M45GYVMS000345", vehicle_id="232705047"):
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {
        "_type": "MessageResponseSingleEntity",
        "status": "OK",
        "body": {
            "motorGenericosTarification": {
                "car": {
                    "_type": "VehicleData",
                    "registrationNumber": "GTF2294",
                    "chassisNumber": chassis,
                    "ensuranceVehicleId": vehicle_id,
                    "productionYear": 2021,
                    "make": "PEUGEOT",
                }
            }
        },
    }
    return m


def _mock_calculate_plans_resp(sum_insured=29657.31, premium_annual=649.50, plan="SENIOR"):
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {
        "_type": "MessageResponseSingleEntity",
        "status": "OK",
        "body": {
            "motorGenericosTarification": {
                "car": {
                    "sumInsured": sum_insured,
                    "selectedPlan": plan,
                    "plans": [
                        {"planType": plan, "premiumAnnual": premium_annual},
                    ],
                }
            }
        },
    }
    return m


def _mock_conn_factor(factor):
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (factor,) if factor is not None else None
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cur
    return mock_conn


def _base_env(monkeypatch):
    monkeypatch.setenv("AMS_POLICY_HOST", "https://uat-ov.zurich.com/portal")
    monkeypatch.setenv("AUTH_LOGIN_URL", "https://uat-ov.zurich.com/login")
    monkeypatch.setenv("AUTH_USERNAME", "u")
    monkeypatch.setenv("AUTH_PASSWORD", "p")
    monkeypatch.setenv("AUTH_TENANT", "ec")
    monkeypatch.setenv("RENEWAL_SCHEMA", "ECU_POLICY")
    monkeypatch.setenv("RENEWAL_TABLE", "FIXED_RENEWAL_DATA")
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    monkeypatch.setenv("DB_DSN", "jdbc:oracle:thin:@host:1521:sid")


def _mock_login():
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {"body": {"accessToken": "tok"}}
    return m


# ── tests ─────────────────────────────────────────────────────────────────────

def test_quote_flow_ok(monkeypatch):
    _base_env(monkeypatch)
    # 29657.31 × 0.0219 = 649.50
    factor = 0.0219

    with patch("checks.quote.get_token", return_value="tok"), \
         patch("checks.quote.requests.post", side_effect=[
             _mock_vehicle_data_resp(),
             _mock_calculate_plans_resp(sum_insured=29657.31, premium_annual=649.50),
         ]), \
         patch("checks.db_conn.oracledb.connect", return_value=_mock_conn_factor(factor)):
        from checks import quote
        result = quote.run_plate("GTF2294", 2027, 7, "tok")

    assert result["status"] == "ok"
    assert "649.5" in result["detail"]


def test_quote_flow_within_tolerance(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.setenv("QA_QUOTE_TOLERANCE", "2.00")
    factor = 0.0219
    # 29657.31 × 0.0219 = 649.50, API returns 650.75 → diff=1.25 <= 2.00

    with patch("checks.quote.requests.post", side_effect=[
             _mock_vehicle_data_resp(),
             _mock_calculate_plans_resp(sum_insured=29657.31, premium_annual=650.75),
         ]), \
         patch("checks.db_conn.oracledb.connect", return_value=_mock_conn_factor(factor)):
        from checks import quote
        result = quote.run_plate("GTF2294", 2027, 7, "tok")

    assert result["status"] == "ok"
    assert "diff=1.25" in result["detail"]


def test_quote_flow_mismatch(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.setenv("QA_QUOTE_TOLERANCE", "2.00")
    factor = 0.0219
    # 29657.31 × 0.0219 = 649.50, API returns 700.00 → diff=50.50 > 2.00

    with patch("checks.quote.requests.post", side_effect=[
             _mock_vehicle_data_resp(),
             _mock_calculate_plans_resp(sum_insured=29657.31, premium_annual=700.00),
         ]), \
         patch("checks.db_conn.oracledb.connect", return_value=_mock_conn_factor(factor)):
        from checks import quote
        result = quote.run_plate("GTF2294", 2027, 7, "tok")

    assert result["status"] == "failed"
    assert "≠" in result["detail"]
    assert "tol=2.0" in result["detail"]


def test_quote_flow_no_factor(monkeypatch):
    _base_env(monkeypatch)

    with patch("checks.quote.requests.post", return_value=_mock_vehicle_data_resp()), \
         patch("checks.db_conn.oracledb.connect", return_value=_mock_conn_factor(None)):
        from checks import quote
        result = quote.run_plate("GTF2294", 2027, 7, "tok")

    assert result["status"] == "failed"
    assert "no FACTOR" in result["detail"]


def test_quote_flow_http_4xx_is_skipped(monkeypatch):
    _base_env(monkeypatch)
    factor = 0.0219

    bad_resp = MagicMock()
    bad_resp.status_code = 400
    bad_resp.json.return_value = {"text": "El tipo de vehículo no puede ser cotizado"}
    http_err = requests.exceptions.HTTPError(response=bad_resp)

    with patch("checks.quote.requests.post", side_effect=[
             _mock_vehicle_data_resp(),
             http_err,
         ]), \
         patch("checks.db_conn.oracledb.connect", return_value=_mock_conn_factor(factor)):
        from checks import quote
        result = quote.run_plate("MBC8721", 2026, 7, "tok")

    assert result["status"] == "skipped"
    assert "MBC8721" in result["detail"]


def test_quote_flow_http_5xx_is_failed(monkeypatch):
    _base_env(monkeypatch)
    factor = 0.0219

    bad_resp = MagicMock()
    bad_resp.status_code = 500
    bad_resp.json.side_effect = Exception("not json")
    bad_resp.text = "Internal Server Error"
    http_err = requests.exceptions.HTTPError(response=bad_resp)

    with patch("checks.quote.requests.post", side_effect=[
             _mock_vehicle_data_resp(),
             http_err,
         ]), \
         patch("checks.db_conn.oracledb.connect", return_value=_mock_conn_factor(factor)):
        from checks import quote
        result = quote.run_plate("MBC8721", 2026, 7, "tok")

    assert result["status"] == "failed"
    assert "500" in result["detail"]


def test_quote_flow_non_quotable_vehicle_type_is_skipped(monkeypatch):
    _base_env(monkeypatch)

    furgoneta = _mock_vehicle_data_resp()
    furgoneta.json.return_value["body"]["motorGenericosTarification"]["car"]["typeOfVehicle"] = "FURGONETA"

    with patch("checks.quote.requests.post", return_value=furgoneta):
        from checks import quote
        result = quote.run_plate("MBC8721", 2026, 7, "tok")

    assert result["status"] == "skipped"
    assert "FURGONETA" in result["detail"]


def test_quote_flow_vehicle_blocked_is_skipped(monkeypatch):
    _base_env(monkeypatch)

    blocked_resp = MagicMock()
    blocked_resp.status_code = 200
    blocked_resp.json.return_value = {
        "status": "ERROR",
        "messages": [{"code": "VEHICLE BLOCKED", "type": "ERROR",
                       "text": "No es posible gestionar la renovación de este vehículo"}],
    }

    with patch("checks.quote.requests.post", return_value=blocked_resp):
        from checks import quote
        result = quote.run_plate("MBC8721", 2026, 7, "tok")

    assert result["status"] == "skipped"
    assert "renovación" in result["detail"]


def test_quote_run_multiple(monkeypatch):
    _base_env(monkeypatch)
    factor = 0.0219

    with patch("checks.quote.get_token", return_value="tok"), \
         patch("checks.quote.requests.post", side_effect=[
             _mock_vehicle_data_resp(), _mock_calculate_plans_resp(),
             _mock_vehicle_data_resp(), _mock_calculate_plans_resp(),
         ]), \
         patch("checks.db_conn.oracledb.connect", return_value=_mock_conn_factor(factor)):
        from checks import quote
        results = quote.run(["GTF2294", "PDL8752"], 2027, 7)

    assert len(results) == 2
    assert all(r["status"] == "ok" for r in results)
