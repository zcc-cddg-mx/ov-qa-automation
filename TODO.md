# TODO

Plan completo: [architecture/execution_plan.md](architecture/execution_plan.md)

---

## Fase 1 — Scaffolding

- [x] `requirements.txt`
- [x] `environment.yml` (conda)
- [x] `app.py` (Flask, arranca en `$PORT`)
- [x] `docker-entrypoint.sh`
- [x] `Dockerfile.base`
- [x] `Dockerfile`
- [x] `.env.example`
- [x] Verificar `GET /health → 200`

## Fase 2 — API + persistencia

- [x] `db.py` — SQLite schema `qa_tasks`
- [x] `POST /validate` — validación de campos, lock, worker, 202
- [x] `GET /status/<task_id>`
- [x] `GET /tasks?limit=N`
- [x] `GET /health`
- [x] Rechazo con `active_task` si lock tomado
- [x] Worker stub (mock approved)

## Fase 3 — Checks ⚠️ requiere env vars de backend

- [x] `checks/flyway.py` — `flyway_history`
- [x] `checks/health.py` — `endpoint_health`
- [x] `checks/renewal.py` — `row_count` + `no_renovar_count`
- [x] `checks/rules.py` — `entity_rows`
- [x] Worker real — acumula resultados, nunca aborta al primer fallo

## Fase 4 — Callback

- [x] `callback.py` — POST a n8n, retry 3x (2s/4s/8s), en `finally`

## Fase 5 — Tests

- [x] `tests/test_api.py`
- [x] `tests/test_checks.py`
- [x] `tests/test_worker.py`
- [x] `tests/test_db.py`

## Fase 6 — Deploy

- [ ] Build `qa-agent-base` y `ov-qa-agent`
- [ ] Smoke test local con env vars reales
- [ ] Deploy en SERVICIOSIAS
- [ ] Prueba end-to-end con ticket real
