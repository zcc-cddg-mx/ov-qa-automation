import os
import random
import requests

from checks.auth import get_token
from checks.db_conn import policy_conn

REFERENCE_PLATES = [
    "PDL8752", "PDG1948", "GSV4719", "PDD6509", "ABH3564",
    "PDG1254", "PDG9912", "PDI2045", "GTC5230", "PDK5119",
    "PDO4227", "PDO3417", "GTF2294", "PDS7078", "G03102894",
    "T03132732", "ABN6689", "GSZ9107", "PDD5333", "PDS7072",
    "GTK6410", "PDX4475", "GTC4154", "PDM3558", "PDE5465",
    "MBF7235", "PDS2190", "PFF3244", "PCW1338", "PFG6477",
    "GTC5216", "GTI3640", "PDS5476", "GTJ7171", "PDW5604",
    "PFG6804", "PFG63721", "TBL8519", "T03145808", "PDS7225",
    "PDS7455", "PFG7741", "PDS6020",
]


def sample_plates(n: int = 10) -> list[str]:
    return random.sample(REFERENCE_PLATES, min(n, len(REFERENCE_PLATES)))


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
        raise ValueError(f"vehicleData error: {data}")
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
        raise ValueError(f"calculatePlans error: {data}")
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


def run_plate(plate: str, year: int, month: int, token: str) -> dict:
    name = f"quote_flow:{plate}"
    try:
        car = _vehicle_data(plate, token)
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

        if premium_calc == premium_api:
            return {
                "name": name,
                "status": "ok",
                "detail": (
                    f"plate={plate} sumInsured={sum_insured} × factor={factor}"
                    f" = {premium_calc} ✓ (API={premium_api})"
                ),
            }

        return {
            "name": name,
            "status": "failed",
            "detail": (
                f"plate={plate} sumInsured={sum_insured} × factor={factor}"
                f" = {premium_calc} ≠ premiumAnnual={premium_api}"
            ),
        }

    except requests.Timeout:
        return {"name": name, "status": "failed",
                "detail": f"plate={plate} — timeout calling API (>30s)"}
    except Exception as exc:
        raise RuntimeError(f"quote_flow [{plate}]: {exc}") from exc


def run(plates: list[str], year: int, month: int) -> list[dict]:
    token = get_token()
    results = []
    for plate in plates:
        results.append(run_plate(plate, year, month, token))
    return results
