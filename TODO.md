# TODO

Plan completo: [architecture/execution_plan.md](architecture/execution_plan.md)

---

## Fase 1 — Scaffolding

- [x] `requirements.txt`
- [x] `app.py` (Flask, arranca en `$PORT`)
- [x] `docker-entrypoint.sh`
- [x] `Dockerfile.base`
- [x] `Dockerfile`
- [x] `.env.example`
- [x] Verificar `GET /health → 200`

## Fase 2 — API + persistencia

- [ ] `db.py` — SQLite schema `qa_tasks`
- [ ] `POST /validate` — validación de campos, lock, worker, 202
- [ ] `GET /status/<task_id>`
- [ ] `GET /tasks?limit=N`
- [ ] `GET /health`
- [ ] Rechazo con `active_task` si lock tomado
- [ ] Worker stub (mock approved)

## Fase 3 — Checks ⚠️ requiere env vars de backend

- [ ] `checks/flyway.py` — `flyway_history`
- [ ] `checks/health.py` — `endpoint_health`
- [ ] `checks/renewal.py` — `row_count` + `no_renovar_count`
- [ ] `checks/rules.py` — `entity_rows`
- [ ] Worker real — acumula resultados, nunca aborta al primer fallo

## Fase 4 — Callback

- [ ] `callback.py` — POST a n8n, retry 3x (2s/4s/8s), en `finally`

## Fase 5 — Tests

- [ ] `tests/test_api.py`
- [ ] `tests/test_checks.py`
- [ ] `tests/test_worker.py`
- [ ] `tests/test_db.py`

## Fase 6 — Deploy

- [ ] Build `qa-agent-base` y `ov-qa-agent`
- [ ] Smoke test local con env vars reales
- [ ] Deploy en SERVICIOSIAS
- [ ] Prueba end-to-end con ticket real
