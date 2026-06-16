import os
import requests


def _get_token() -> str:
    login_url = os.environ["AUTH_LOGIN_URL"]
    tenant = os.environ.get("AUTH_TENANT", "ec")

    resp = requests.post(
        login_url,
        json={
            "username": os.environ["AUTH_USERNAME"],
            "password": os.environ["AUTH_PASSWORD"],
        },
        headers={"content-type": "application/json", "x-tenantid-1": tenant},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["token"]


def run(module: str) -> dict:
    host_var = "AMS_POLICY_HOST" if module == "ams-policy" else "AMS_RULE_HOST"
    base_url = os.environ[host_var].rstrip("/")
    path = os.environ.get("HEALTH_PATH", "/actuator/health").lstrip("/")
    url = f"{base_url}/{path}"
    tenant = os.environ.get("AUTH_TENANT", "ec")

    try:
        token = _get_token()

        resp = requests.get(
            url,
            headers={
                "authorization": f"Bearer {token}",
                "content-type": "application/json",
                "x-tenantid-1": tenant,
            },
            timeout=10,
        )
        body = resp.json() if resp.content else {}

        if resp.status_code == 200 and body.get("status") == "UP":
            return {"name": "endpoint_health", "status": "ok",
                    "detail": f"GET {url} → 200 UP"}

        return {"name": "endpoint_health", "status": "failed",
                "detail": f"GET {url} → {resp.status_code} status={body.get('status')}"}

    except requests.Timeout:
        return {"name": "endpoint_health", "status": "failed",
                "detail": f"GET {url} → timeout (10s)"}
    except Exception as exc:
        raise RuntimeError(f"endpoint_health: {exc}") from exc
