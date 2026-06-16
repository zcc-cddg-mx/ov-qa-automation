import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request

import db
import worker

app = Flask(__name__)

def _upload_dir() -> Path:
    return Path(os.environ.get("QA_UPLOAD_DIR", "/data/uploads"))
REQUIRED_FIELDS = ["ticket", "command", "module", "migration_name",
                   "branch", "aux_branch", "commit_id"]
REQUIRED_REN_DATA = ["year", "month"]
REQUIRED_RULES = ["entity"]


def _now():
    return datetime.now(timezone.utc).isoformat()


@app.post("/validate")
def validate():
    body = request.form

    missing = [f for f in REQUIRED_FIELDS if not body.get(f)]
    if body.get("command") == "ren-data":
        missing += [f for f in REQUIRED_REN_DATA if body.get(f) is None]
        if "file" not in request.files or request.files["file"].filename == "":
            missing.append("file")
    if body.get("command") == "rules":
        missing += [f for f in REQUIRED_RULES if not body.get(f)]
    if missing:
        return jsonify({"status": "error",
                        "error": f"Missing required field(s): {', '.join(missing)}"}), 400

    if worker.is_locked():
        active = worker.get_active()
        return jsonify({"status": "rejected", "active_task": active}), 202

    # save uploaded file
    input_path = None
    if "file" in request.files:
        f = request.files["file"]
        upload_dir = _upload_dir()
        upload_dir.mkdir(parents=True, exist_ok=True)
        task_id_tmp = uuid.uuid4().hex[:8]
        filename = f"{task_id_tmp}_{f.filename}"
        input_path = str(upload_dir / filename)
        f.save(input_path)

    task_id = uuid.uuid4().hex[:8]
    now = _now()
    sample_size = int(body.get("sample_size") or os.environ.get("QA_SAMPLE_SIZE", 50))
    sample_size = min(sample_size, 200)

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
        "input_path":     input_path,
        "sample_size":    sample_size,
        "result":         None,
        "checks":         json.dumps([]),
        "summary":        None,
        "error":          None,
        "created_at":     now,
        "updated_at":     now,
        # extra fields for worker — not stored in qa_tasks
        "year":           int(body["year"]) if body.get("year") else None,
        "month":          int(body["month"]) if body.get("month") else None,
        "row_count":      int(body["row_count"]) if body.get("row_count") else None,
        "entity":         body.get("entity"),
        "callback_url":   body.get("callback_url"),
    }

    db.insert_task({k: task[k] for k in [
        "task_id", "ticket", "status", "command", "module", "migration_name",
        "branch", "aux_branch", "commit_id", "input_path", "sample_size",
        "result", "checks", "summary", "error", "created_at", "updated_at"
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
