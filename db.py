import json
import os
import sqlite3

DB_PATH = os.environ.get("QA_TASKS_DB", "/data/qa_tasks.db")


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS qa_tasks (
                task_id        TEXT PRIMARY KEY,
                ticket         TEXT,
                status         TEXT NOT NULL,
                command        TEXT,
                module         TEXT,
                migration_name TEXT,
                branch         TEXT,
                aux_branch     TEXT,
                commit_id      TEXT,
                input_path     TEXT,
                sample_size    INTEGER,
                year           INTEGER,
                month          INTEGER,
                result         TEXT,
                checks         TEXT,
                summary        TEXT,
                error          TEXT,
                created_at     TEXT NOT NULL,
                updated_at     TEXT NOT NULL
            )
        """)
        # migrate existing databases that predate year/month columns
        for col in ("year", "month"):
            try:
                conn.execute(f"ALTER TABLE qa_tasks ADD COLUMN {col} INTEGER")
            except Exception:
                pass


def insert_task(task):
    with _conn() as conn:
        conn.execute("""
            INSERT INTO qa_tasks
                (task_id, ticket, status, command, module, migration_name,
                 branch, aux_branch, commit_id, input_path, sample_size,
                 year, month,
                 result, checks, summary, error, created_at, updated_at)
            VALUES
                (:task_id, :ticket, :status, :command, :module, :migration_name,
                 :branch, :aux_branch, :commit_id, :input_path, :sample_size,
                 :year, :month,
                 :result, :checks, :summary, :error, :created_at, :updated_at)
        """, task)


def update_task(task_id, **fields):
    if not fields:
        return
    sets = ", ".join(f"{k} = :{k}" for k in fields)
    fields["task_id"] = task_id
    with _conn() as conn:
        conn.execute(f"UPDATE qa_tasks SET {sets} WHERE task_id = :task_id", fields)


def get_task(task_id):
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM qa_tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_tasks(limit):
    limit = min(int(limit), 200)
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM qa_tasks ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row):
    d = dict(row)
    if d.get("checks"):
        d["checks"] = json.loads(d["checks"])
    return d
