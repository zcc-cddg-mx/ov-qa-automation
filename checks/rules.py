import os
from checks.db_conn import rule_conn


def run_entity_rows(entity: str, migration_name: str) -> dict:
    schema = os.environ["RULES_SCHEMA"]
    table = os.environ["RULES_TABLE"]
    entity_field = os.environ["RULES_ENTITY_FIELD"]
    id_field = os.environ["RULES_MIGRATION_ID_FIELD"]
    qualified = f"{schema}.{table}"

    try:
        with rule_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) FROM {qualified} "
                    f"WHERE {entity_field} = :1 AND {id_field} = :2",
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
