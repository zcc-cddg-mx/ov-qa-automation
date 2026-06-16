import os
from checks.db_conn import policy_conn


def _qualified_table():
    schema = os.environ["RENEWAL_SCHEMA"]
    table = os.environ["RENEWAL_TABLE"]
    return f"{schema}.{table}"


def run_row_count(year: int, month: int, expected: int | None) -> dict:
    table = _qualified_table()

    try:
        with policy_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(ID) FROM {table} WHERE YEAR = :1 AND MONTH = :2",
                    (str(year), str(month)),
                )
                count = cur.fetchone()[0]

        if expected is not None:
            if count == expected:
                return {"name": "row_count", "status": "ok",
                        "detail": f"{count} rows found, expected {expected}"}
            return {"name": "row_count", "status": "failed",
                    "detail": f"found {count} rows, expected {expected} — {abs(expected - count)} rows missing"}

        if count > 0:
            return {"name": "row_count", "status": "ok",
                    "detail": f"{count} rows found for {year}/{month:02d}"}
        return {"name": "row_count", "status": "failed",
                "detail": f"0 rows found for {year}/{month:02d}, expected > 0"}

    except Exception as exc:
        raise RuntimeError(f"row_count: {exc}") from exc


def run_no_renovar_count(year: int, month: int) -> dict:
    table = _qualified_table()
    blocked_field = os.environ["RENEWAL_BLOCKED_FIELD"]

    try:
        with policy_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(ID) FROM {table} "
                    f"WHERE YEAR = :1 AND MONTH = :2 AND {blocked_field} = 'YES'",
                    (str(year), str(month)),
                )
                count = cur.fetchone()[0]

        if count >= 1:
            return {"name": "no_renovar_count", "status": "ok",
                    "detail": f"{count} 'No Renovar' rows found"}
        return {"name": "no_renovar_count", "status": "failed",
                "detail": "found 0 'No Renovar' rows, expected >= 1"}

    except Exception as exc:
        raise RuntimeError(f"no_renovar_count: {exc}") from exc
