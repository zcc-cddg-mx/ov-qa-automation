import os
import psycopg2


def run(migration_name: str) -> dict:
    table = os.environ["FLYWAY_HISTORY_TABLE"]
    dsn = os.environ["DB_DSN"]

    try:
        with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM {table} WHERE script LIKE %s AND success = TRUE",
                (f"%{migration_name}%",),
            )
            count = cur.fetchone()[0]

        if count == 1:
            return {"name": "flyway_history", "status": "ok",
                    "detail": f"migration recorded in {table}"}
        return {"name": "flyway_history", "status": "failed",
                "detail": f"migration not found in {table} (count={count})"}

    except Exception as exc:
        raise RuntimeError(f"flyway_history: {exc}") from exc
