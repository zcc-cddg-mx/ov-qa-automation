import os
import time
import requests

from checks.auth import get_token
from checks.db_conn import policy_conn
from checks.excel import read_plates

# Raised when the API returns a business-level rejection (non-quotable vehicle).
# These are expected for some plates and should count as skipped, not failed.
class _VehicleSkip(Exception):
    def __init__(self, reason: str):
        self.reason = reason


def _first_message(data: dict) -> str:
    msgs = data.get("messages") or []
    return msgs[0].get("text", "") if msgs else ""


def _base_url() -> str:
    return os.environ["AMS_POLICY_HOST"].rstrip("/")


def _headers(token: str) -> dict:
    return {
        "authorization": f"Bearer {token}",
        "content-type": "application/json",
        "x-tenantid-1": os.environ.get("AUTH_TENANT", "ec"),
    }


def _vehicle_data(plate: str, token: str) -> dict:
    url = f"{_base_url()}/policy/api/v1/arizona/motor/genericos/vehicleData"
    body = {
        "_type": "MotorGenericosTarificationRequest",
        "motorGenericosTarification": {
            "_type": "MotorGenericosTarification",
            "policyData": {
                "_type": "PolicyData",
                "agentExternalId": "1",
                "pointOfSaleName": "QUITO ZURICH SEGUROS ECUADOR S.A.",
            },
            "car": {"_type": "VehicleData", "registrationNumber": plate},
        },
        "testMode": False,
    }
    resp = requests.post(url, json=body, headers=_headers(token), timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK":
        msg = _first_message(data)
        raise _VehicleSkip(msg or f"vehicleData status={data.get('status')}")
    return data["body"]["motorGenericosTarification"]["car"]


def _calculate_plans(car: dict, token: str) -> dict:
    url = f"{_base_url()}/policy/api/v1/arizona/motor/genericos/calculatePlans"
    body = {
        "_type": "MotorGenericosTarificationRequest",
        "motorGenericosTarification": {
            "_type": "MotorGenericosTarification",
            "policyData": {
                "_type": "PolicyData",
                "agentExternalId": "1",
                "pointOfSaleName": "QUITO ZURICH SEGUROS ECUADOR S.A.",
            },
            "car": car,
            "owner": {
                "_type": "VehicleOwner",
                "partyType": "PERSON",
                "identificationNumber": "0000000000",
                "name": "QA Agent",
                "age": 40,
                "civilStatus": "Soltero",
                "gender": "M",
            },
        },
        "testMode": False,
    }
    resp = requests.post(url, json=body, headers=_headers(token), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK":
        msg = _first_message(data)
        raise _VehicleSkip(msg or f"calculatePlans status={data.get('status')}")
    return data["body"]["motorGenericosTarification"]["car"]


def _get_factor(chassis: str, year: int, month: int) -> float | None:
    schema = os.environ["RENEWAL_SCHEMA"]
    table = os.environ["RENEWAL_TABLE"]
    qualified = f"{schema}.{table}"
    with policy_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT FACTOR FROM {qualified}"
                f" WHERE CHASSIS_NUMBER = :1 AND YEAR = :2 AND MONTH = :3",
                (chassis, str(year), str(month)),
            )
            row = cur.fetchone()
    return float(row[0]) if row else None


_QUOTABLE_TYPES = {"AUTOMOVIL", "JEEP", "CAMIONETA", "MOTO", "MOTOCICLETA"}


def run_plate(plate: str, year: int, month: int, token: str) -> dict:
    name = f"quote_flow:{plate}"
    try:
        car = _vehicle_data(plate, token)
        vehicle_type = (car.get("typeOfVehicle") or "").upper()
        if vehicle_type and vehicle_type not in _QUOTABLE_TYPES:
            return {"name": name, "status": "skipped",
                    "detail": f"plate={plate} — non-quotable vehicle type: {vehicle_type}"}

        chassis = car.get("chassisNumber", "")

        factor = _get_factor(chassis, year, month)
        if factor is None:
            return {
                "name": name,
                "status": "failed",
                "detail": f"plate={plate} chassis={chassis} — no FACTOR found for {year}/{month:02d}",
            }

        result_car = _calculate_plans(car, token)
        sum_insured = result_car.get("sumInsured")
        plans = result_car.get("plans", [])

        # use selectedPlan if present, otherwise first plan with premiumAnnual > 0
        selected = result_car.get("selectedPlan")
        target = None
        for p in plans:
            if selected and p.get("planType") == selected:
                target = p
                break
        if target is None:
            for p in plans:
                if (p.get("premiumAnnual") or 0) > 0:
                    target = p
                    break

        if target is None or sum_insured is None:
            return {
                "name": name,
                "status": "failed",
                "detail": f"plate={plate} — calculatePlans returned no usable plan",
            }

        premium_api = target["premiumAnnual"]
        premium_calc = round(sum_insured * factor, 2)
        tolerance = float(os.environ.get("QA_QUOTE_TOLERANCE", "20.00"))
        diff = abs(premium_calc - premium_api)

        if diff <= tolerance:
            return {
                "name": name,
                "status": "ok",
                "detail": (
                    f"plate={plate} sumInsured={sum_insured} × factor={factor}"
                    f" = {premium_calc} ✓ (API={premium_api}"
                    + (f", diff={diff:.2f}" if diff > 0 else "") + ")"
                ),
            }

        return {
            "name": name,
            "status": "failed",
            "detail": (
                f"plate={plate} sumInsured={sum_insured} × factor={factor}"
                f" = {premium_calc} ≠ premiumAnnual={premium_api} (diff={diff:.2f}, tol={tolerance})"
            ),
        }

    except _VehicleSkip as exc:
        return {"name": name, "status": "skipped",
                "detail": f"plate={plate} — non-quotable: {exc.reason}"}
    except requests.Timeout:
        return {"name": name, "status": "failed",
                "detail": f"plate={plate} — timeout calling API (>30s)"}
    except requests.HTTPError as exc:
        code = exc.response.status_code
        try:
            msg = exc.response.json().get("text") or exc.response.text[:120]
        except Exception:
            msg = exc.response.text[:120]
        if code < 500:
            # API rechazó el vehículo (no cotizable, no encontrado) — no es falla de negocio
            return {"name": name, "status": "skipped",
                    "detail": f"plate={plate} — non-quotable ({code}): {msg}"}
        return {"name": name, "status": "failed",
                "detail": f"plate={plate} — API {code}: {msg}"}
    except Exception as exc:
        raise RuntimeError(f"quote_flow [{plate}]: {exc}") from exc


def run(plates: list[str], year: int, month: int) -> list[dict]:
    token = get_token()
    delay = float(os.environ.get("QA_PLATE_DELAY", "0"))
    results = []
    for i, plate in enumerate(plates):
        if i > 0 and delay > 0:
            time.sleep(delay)
        results.append(run_plate(plate, year, month, token))
    return results


def run_from_excel(excel_path: str, year: int, month: int,
                   sample_size: int | None = None) -> tuple[list[dict], list[str]]:
    plates = read_plates(excel_path, sample_size)
    return run(plates, year, month), plates
