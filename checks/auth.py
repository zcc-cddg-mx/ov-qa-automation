import os
import requests


def get_token() -> str:
    login_url = os.environ["AUTH_LOGIN_URL"]
    tenant = os.environ.get("AUTH_TENANT", "ec")
    resp = requests.post(
        login_url,
        json={"username": os.environ["AUTH_USERNAME"], "password": os.environ["AUTH_PASSWORD"]},
        headers={"content-type": "application/json", "x-tenantid-1": tenant},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["body"]["accessToken"]
