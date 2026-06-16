import os
import requests


def run(module: str) -> dict:
    host_var = "AMS_POLICY_HOST" if module == "ams-policy" else "AMS_RULE_HOST"
    host = os.environ[host_var]
    path = os.environ.get("HEALTH_PATH", "/actuator/health")
    url = f"http://{host}{path}"

    try:
        resp = requests.get(url, timeout=10)
        body = resp.json() if resp.content else {}

        if resp.status_code == 200 and body.get("status") == "UP":
            return {"name": "endpoint_health", "status": "ok",
                    "detail": f"GET {path} → 200 UP"}

        return {"name": "endpoint_health", "status": "failed",
                "detail": f"GET {path} → {resp.status_code} status={body.get('status')}"}

    except requests.Timeout:
        return {"name": "endpoint_health", "status": "failed",
                "detail": f"GET {path} → timeout (10s)"}
    except Exception as exc:
        raise RuntimeError(f"endpoint_health: {exc}") from exc
