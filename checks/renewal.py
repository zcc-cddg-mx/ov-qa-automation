import os
import psycopg2


def _query_count(cur, table, id_field, migration_name, extra_where=""):
    sql = f"SELECT COUNT(*) FROM {table} WHERE {id_field} = %s"
    if extra_where:
        sql += f" AND {extra_where}"
    cur.execute(sql, (migration_name,))
    return cur.fetchone()[0]


def run_row_count(migration_name: str, expected: int | None) -> dict:
    table = os.environ["RENEWAL_TABLE"]
    id_field = os.environ["RENEWAL_MIGRATION_ID_FIELD"]
    dsn = os.environ["DB_DSN"]

    try:
        with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
            count = _query_count(cur, table, id_field, migration_name)

        if expected is not None:
            if count == expected:
                return {"name": "row_count", "status": "ok",
                        "detail": f"{count} rows found, expected {expected}"}
            return {"name": "row_count", "status": "failed",
                    "detail": f"found {count} rows, expected {expected} — {abs(expected - count)} rows missing"}

        if count > 0:
            return {"name": "row_count", "status": "ok",
                    "detail": f"{count} rows found"}
        return {"name": "row_count", "status": "failed",
                "detail": "0 rows found, expected > 0"}

    except Exception as exc:
        raise RuntimeError(f"row_count: {exc}") from exc


def run_no_renovar_count(migration_name: str) -> dict:
    table = os.environ["RENEWAL_TABLE"]
    id_field = os.environ["RENEWAL_MIGRATION_ID_FIELD"]
    blocked_field = os.environ["RENEWAL_BLOCKED_FIELD"]
    dsn = os.environ["DB_DSN"]

    try:
        with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
            count = _query_count(cur, table, id_field, migration_name,
                                 extra_where=f"{blocked_field} = 'Yes'")

        if count >= 1:
            return {"name": "no_renovar_count", "status": "ok",
                    "detail": f"{count} 'No Renovar' rows found"}
        return {"name": "no_renovar_count", "status": "failed",
                "detail": f"found 0 'No Renovar' rows, expected >= 1"}

    except Exception as exc:
        raise RuntimeError(f"no_renovar_count: {exc}") from exc
