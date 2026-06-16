import os
from checks.db_conn import policy_conn


def run(migration_name: str) -> dict:
    schema = os.environ["RENEWAL_SCHEMA"]
    table = os.environ["FLYWAY_HISTORY_TABLE"]
    qualified = f'{schema}."{table}"'

    try:
        with policy_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT COUNT(*) FROM {qualified} WHERE "description" LIKE :1',
                    (f"%{migration_name}%",),
                )
                count = cur.fetchone()[0]

        if count >= 1:
            return {"name": "flyway_history", "status": "ok",
                    "detail": f"migration recorded in {qualified}"}
        return {"name": "flyway_history", "status": "failed",
                "detail": f"migration not found in {qualified} (count={count})"}

    except Exception as exc:
        raise RuntimeError(f"flyway_history: {exc}") from exc
