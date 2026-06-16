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
    data = resp.json()
    return data["body"]["accessToken"]


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
        if resp.status_code == 200:
            try:
                body = resp.json()
                up = body.get("status") == "UP"
                detail = f"GET {url} → 200 {body.get('status', 'OK')}"
            except Exception:
                up = resp.text.strip().upper() in ("OK", "UP")
                detail = f"GET {url} → 200 {resp.text.strip()}"

            if up:
                return {"name": "endpoint_health", "status": "ok", "detail": detail}
            return {"name": "endpoint_health", "status": "failed", "detail": detail}

        try:
            body = resp.json()
        except Exception:
            body = {}
        return {"name": "endpoint_health", "status": "failed",
                "detail": f"GET {url} → {resp.status_code} {body or resp.text[:100]}"}

    except requests.Timeout:
        return {"name": "endpoint_health", "status": "failed",
                "detail": f"GET {url} → timeout (10s)"}
    except Exception as exc:
        raise RuntimeError(f"endpoint_health: {exc}") from exc
