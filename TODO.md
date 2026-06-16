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

## Validación DEV real (previa a Fase 6) ✅

- [x] Oracle DB — `oracledb` thin mode, JDBC DSN parser, credenciales separadas por schema
- [x] `flyway_history` — tabla `ECU_POLICY."schema_history"`, filtro por `"description"`
- [x] `row_count` + `no_renovar_count` — filtro YEAR/MONTH, `BLOCKED_RENEWAL = 'YES'`
- [x] `endpoint_health` — login JWT → `body.accessToken` → GET con Bearer token
- [x] 43 tests pasando (mocks actualizados para Oracle + JWT)

## Fase 5.1 — Verificacion via endpoints ✅

- [x] Entendimiento del flujo de cotizacion (vehicleData → calculatePlans)
- [x] `checks/auth.py` — get_token() compartido (JWT login)
- [x] `checks/quote.py` — verifica sumInsured × FACTOR == premiumAnnual por placa
- [x] `checks/excel.py` — lee Excel, extrae placas, muestrea `sample_size` al azar
- [x] `POST /validate` migrado a `multipart/form-data` con campo `file` (Excel)
- [x] Placas leídas del Excel (no del request) — `RENEWAL_PLATE_FIELD`, `QA_SAMPLE_SIZE`
- [x] SQLite: columnas `input_path` y `sample_size`
- [x] 54 tests pasando
- [x] Pruebas reales contra UAT — verificación sumInsured × FACTOR == premiumAnnual confirmada

## Fase 6 — Deploy

- [ ] Build `qa-agent-base` y `ov-qa-agent`
- [ ] Smoke test local con env vars reales (POST /validate con payload real)
- [ ] Deploy en SERVICIOSIAS
- [ ] Prueba end-to-end con ticket real desde n8n
