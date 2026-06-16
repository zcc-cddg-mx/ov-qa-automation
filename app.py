import json
import os
import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, request

import db
import worker

app = Flask(__name__)

REQUIRED_FIELDS = ["ticket", "command", "module", "migration_name",
                   "branch", "aux_branch", "commit_id"]
REQUIRED_REN_DATA = ["year", "month"]
REQUIRED_RULES = ["entity"]
MAX_PLATES = 50


def _now():
    return datetime.now(timezone.utc).isoformat()


@app.post("/validate")
def validate():
    body = request.get_json(silent=True) or {}

    missing = [f for f in REQUIRED_FIELDS if not body.get(f)]
    if body.get("command") == "ren-data":
        missing += [f for f in REQUIRED_REN_DATA if body.get(f) is None]
    if body.get("command") == "rules":
        missing += [f for f in REQUIRED_RULES if not body.get(f)]
    if missing:
        return jsonify({"status": "error",
                        "error": f"Missing required field(s): {', '.join(missing)}"}), 400

    plates = body.get("plates") or []
    if not isinstance(plates, list) or any(not isinstance(p, str) for p in plates):
        return jsonify({"status": "error", "error": "'plates' must be a list of strings"}), 400
    if len(plates) > MAX_PLATES:
        return jsonify({"status": "error",
                        "error": f"'plates' exceeds maximum of {MAX_PLATES}"}), 400

    if worker.is_locked():
        active = worker.get_active()
        return jsonify({"status": "rejected",
                        "active_task": active}), 202

    task_id = uuid.uuid4().hex[:8]
    now = _now()
    task = {
        "task_id":        task_id,
        "ticket":         body["ticket"],
        "status":         "queued",
        "command":        body["command"],
        "module":         body["module"],
        "migration_name": body["migration_name"],
        "branch":         body["branch"],
        "aux_branch":     body["aux_branch"],
        "commit_id":      body["commit_id"],
        "result":         None,
        "checks":         json.dumps([]),
        "summary":        None,
        "error":          None,
        "created_at":     now,
        "updated_at":     now,
        # extra fields passed through to worker but not in qa_tasks schema
        "year":           body.get("year"),
        "month":          body.get("month"),
        "row_count":      body.get("row_count"),
        "entity":         body.get("entity"),
        "plates":         plates,
        "callback_url":   body.get("callback_url"),
    }

    db.insert_task({k: task[k] for k in [
        "task_id", "ticket", "status", "command", "module", "migration_name",
        "branch", "aux_branch", "commit_id", "result", "checks", "summary",
        "error", "created_at", "updated_at"
    ]})

    worker._set_active({"task_id": task_id, "ticket": task["ticket"], "started_at": now})
    print(f"[RECV]   task_id={task_id} ticket={task['ticket']} ACCEPTED")
    worker.run(task)

    return jsonify({"status": "queued", "task_id": task_id}), 202


@app.get("/status/<task_id>")
def status(task_id):
    task = db.get_task(task_id)
    if not task:
        return jsonify({"status": "error", "error": "task not found"}), 404
    return jsonify(task)


@app.get("/tasks")
def tasks():
    limit = request.args.get("limit", 50)
    return jsonify(db.list_tasks(limit))


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "qa-agent"})


if __name__ == "__main__":
    db.init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
