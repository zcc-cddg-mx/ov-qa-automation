import os
import requests

from checks.auth import get_token


def run(module: str) -> dict:
    host_var = "AMS_POLICY_HOST" if module == "ams-policy" else "AMS_RULE_HOST"
    base_url = os.environ[host_var].rstrip("/")
    path = os.environ.get("HEALTH_PATH", "/actuator/health").lstrip("/")
    url = f"{base_url}/{path}"
    tenant = os.environ.get("AUTH_TENANT", "ec")

    try:
        token = get_token()

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
