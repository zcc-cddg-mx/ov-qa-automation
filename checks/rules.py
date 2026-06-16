import os
import psycopg2


def run_entity_rows(entity: str, migration_name: str) -> dict:
    table = os.environ["RULES_TABLE"]
    entity_field = os.environ["RULES_ENTITY_FIELD"]
    id_field = os.environ["RULES_MIGRATION_ID_FIELD"]
    dsn = os.environ["DB_DSN"]

    try:
        with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {entity_field} = %s AND {id_field} = %s",
                (entity, migration_name),
            )
            count = cur.fetchone()[0]

        if count > 0:
            return {"name": "entity_rows", "status": "ok",
                    "detail": f"{count} rows found for entity '{entity}'"}
        return {"name": "entity_rows", "status": "failed",
                "detail": f"0 rows found for entity '{entity}' and migration '{migration_name}'"}

    except Exception as exc:
        raise RuntimeError(f"entity_rows: {exc}") from exc
