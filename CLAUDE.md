# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

This repository is in the **specification phase** — no implementation exists yet. The full design contract lives in `architecture/qa_agent_contract.md`. Implementation will be Python (Flask/FastAPI + psycopg2 + requests + SQLite).

Once the project is scaffolded, expected commands will be:
- `pip install -r requirements.txt` — install dependencies
- `python app.py` — start the HTTP server (port 5000)
- `pytest` — run tests
- `pytest tests/test_<module>.py` — run a single test file

## Pipeline Context

The QA Agent is **Step 6 of 9** in an automated Jira-to-production pipeline:

```
Jira webhook → n8n → Enricher Agent (LLM in n8n) → Code Agent
  → n8n creates PR → Azure DevOps (build + DEV deploy)
  → n8n triggers → QA Agent ← this repo
  → n8n updates Jira → closes/reopens ticket
```

The QA Agent receives a JSON request from n8n *after* Azure DevOps completes a DEV deploy. It validates the deploy by running SQL checks against the DEV database and HTTP checks against the deployed services. It never writes to the database (SELECT only) and never creates PRs or pushes code.

## API Contract

Four endpoints — full schemas in `architecture/qa_agent_contract.md`:

| Endpoint | Purpose |
|---|---|
| `POST /validate` | Enqueue a validation task; responds 202 immediately |
| `GET /status/<task_id>` | Poll task status (`queued → running → done\|error`) |
| `GET /tasks?limit=50` | Validation history from SQLite |
| `GET /health` | Liveness check |

The agent runs **one validation at a time**. If a second request arrives while one is running, it is rejected with `202 {"status": "rejected", "active_task": {...}}`. The lock is acquired in the HTTP handler (not the worker) to avoid race conditions.

Upon completion, the agent POSTs a callback to `callback_url` from the request (or `N8N_CALLBACK_URL` env fallback). Retry: 3 attempts with 2s/4s/8s exponential backoff, fired in `finally` on both success and error paths.

## Validation Checks

| Check | Command | Type | What it verifies |
|---|---|---|---|
| `flyway_history` | both | SQL | Migration recorded in `$FLYWAY_HISTORY_TABLE` with `success = TRUE` |
| `endpoint_health` | both | HTTP | `GET http://<host>/$HEALTH_PATH` returns 200 with `"status": "UP"` (10s timeout) |
| `row_count` | `ren-data` only | SQL | Row count in `$RENEWAL_TABLE` matches `row_count` from request (or > 0 if absent) |
| `no_renovar_count` | `ren-data` only | SQL | At least 1 row with `$RENEWAL_BLOCKED_FIELD = 'Yes'` |
| `entity_rows` | `rules` only | SQL | COUNT > 0 in `$RULES_TABLE` for given `entity` and `migration_name` |

All checks run before resolving the global result — never abort on first failure. Global result is `approved` only if all checks pass; any failure → `rejected`.

All table and field names are injected via env vars — the code has no hardcoded schema knowledge.

## Environment Variables

**Connectivity**

| Variable | Default | Description |
|---|---|---|
| `AMS_POLICY_HOST` | — | `host:port` for ams-policy DEV |
| `AMS_RULE_HOST` | — | `host:port` for ams-rule DEV |
| `HEALTH_PATH` | `/actuator/health` | Health endpoint path |
| `DB_DSN` | — | `postgresql://user:pass@host:5432/db` |
| `N8N_CALLBACK_URL` | — | Fallback webhook URL for n8n |

**DB schema — `ren-data`**

| Variable | Example | Description |
|---|---|---|
| `FLYWAY_HISTORY_TABLE` | `flyway_schema_history` | Flyway history table name |
| `RENEWAL_TABLE` | `frd_fixed_renewal_data` | Table populated by the migration |
| `RENEWAL_MIGRATION_ID_FIELD` | `migration_id` | Column linking rows to a migration |
| `RENEWAL_BLOCKED_FIELD` | `renewal_blocked` | Column for "No Renovar" flag (`'Yes'`/`'No'`) |

**DB schema — `rules`**

| Variable | Example | Description |
|---|---|---|
| `RULES_TABLE` | `ams_rule_entry` | Table containing loaded rules |
| `RULES_ENTITY_FIELD` | `entity` | Entity column in `RULES_TABLE` |
| `RULES_MIGRATION_ID_FIELD` | `migration_id` | Column linking rows to a migration |

**Operation**

| Variable | Default | Description |
|---|---|---|
| `QA_TASKS_DB` | `/data/qa_tasks.db` | SQLite persistence path |
| `RETENTION_DAYS` | `90` | SQLite record retention |
| `PORT` | `5000` | HTTP server port |

`DB_DSN` contains credentials — inject via Docker env only, never commit. Example `docker run` with all vars in `architecture/qa_agent_contract.md §10`.

## Log Format Convention

Follow the same `[TAG] message` convention as the Code Agent:

```
[RECV]   task_id=a1b2c3d4 ticket=ZNRX-67108 ACCEPTED
[CHECK]  flyway_history — ok (migration recorded)
[CHECK]  row_count — failed (found 1300, expected 1342)
[DONE]   task_id=a1b2c3d4 result=rejected (1 check failed)
[N8N]    callback → https://n8n.host/webhook/qa-result status=200 (attempt 1)
```

## Docker Build Pattern

Two-image pattern (same as the sibling Code Agent in `ov-suscripcion-automation`):

- **`qa-agent-base`** — `ams-ubuntu-lite:latest` + Python venv + pip deps. Rebuild only when `requirements.txt` changes.
- **`ov-qa-agent`** — `FROM qa-agent-base` + Python source. Fast rebuild (seconds).

SQLite volume: `docker run -v qa-agent-data:/data ... ov-qa-agent:latest`

The QA Agent does **not** need Java or Gradle — the base image is lighter than the Code Agent's `ov-agent-base`.

## Sibling Repo

`ov-suscripcion-automation` (Code Agent) is the upstream step in the same pipeline. Its architecture is documented in `architecture/agent_architecture.md` and serves as the implementation reference for concurrency model, callback retry, logging conventions, Docker pattern, and SQLite persistence schema.
