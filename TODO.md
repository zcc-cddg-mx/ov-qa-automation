# TODO

Plan completo: [architecture/execution_plan.md](architecture/execution_plan.md)

---

## Fase 1 — Scaffolding ✅

- [x] `requirements.txt`
- [x] `environment.yml` (conda)
- [x] `app.py` (Flask, arranca en `$PORT`)
- [x] `docker-entrypoint.sh`
- [x] `Dockerfile.base`
- [x] `Dockerfile`
- [x] `.env.example`
- [x] Verificar `GET /health → 200`

## Fase 2 — API + persistencia ✅

- [x] `db.py` — SQLite schema `qa_tasks` (columnas: `year`, `month`, `input_path`, `sample_size`)
- [x] `POST /validate` — multipart/form-data, validación de campos, lock, worker, 202
- [x] `GET /status/<task_id>`
- [x] `GET /tasks?limit=N`
- [x] `GET /health`
- [x] Rechazo con `active_task` si lock tomado
- [x] Worker stub (mock approved)

## Fase 3 — Checks ✅

- [x] `checks/auth.py` — JWT login → `body.accessToken`, compartido por health y quote
- [x] `checks/db_conn.py` — Oracle thin mode, parser JDBC DSN, conexiones separadas `policy_conn` / `rule_conn`
- [x] `checks/flyway.py` — `flyway_history` (tabla `RENEWAL_SCHEMA."FLYWAY_HISTORY_TABLE"`)
- [x] `checks/health.py` — `endpoint_health` (GET con Bearer token + `x-tenantid-1`)
- [x] `checks/renewal.py` — `row_count` + `no_renovar_count` (filtro YEAR/MONTH dinámicos)
- [x] `checks/rules.py` — `entity_rows`
- [x] `checks/excel.py` — lee Excel, extrae placas, muestrea `QA_SAMPLE_SIZE` al azar
- [x] `checks/quote.py` — `quote_flow`: `vehicleData` → tipo cotizable → FACTOR en DB → `calculatePlans` → tolerancia `QA_QUOTE_TOLERANCE`
- [x] Worker real — acumula todos los checks antes de resolver, nunca aborta al primer fallo
- [x] Vehículos no cotizables (tipo incorrecto, VEHICLE BLOCKED, 4xx) → `skipped`, no `failed`
- [x] Batch quote aprobado si `ok_count >= QA_QUOTE_MIN_OK_COUNT` (default 1)

## Fase 4 — Callback ✅

- [x] `callback.py` — multipart/form-data a n8n (campos + `checks_{task_id}.txt`)
- [x] `checks/summary.py` — resumen ejecutivo vía Anthropic (proxy Zurich) con fallback OpenAI
- [x] Fallback estático en español con `year`/`month` del ticket cuando la IA no responde (solo `approved`)
- [x] Prompt en español — salida: Resumen Ejecutivo, Conclusión, Nivel de Riesgo, Comentario Jira
- [x] Retry 3x (2s/4s/8s), siempre en `finally` (éxito y error)

## Fase 5 — Tests ✅

- [x] `tests/test_api.py`
- [x] `tests/test_checks.py`
- [x] `tests/test_db.py`
- [x] `tests/test_worker.py`
- [x] `tests/test_quote.py`
- [x] `tests/test_summary.py`
- [x] 71 tests pasando
- [x] Pruebas reales UAT — 15/15 checks aprobados (tarea `1f87e04f`)
- [x] Callback real verificado — Anthropic responde en español con formato correcto

## Fase 6 — Deploy

- [x] Dockerfile single-stage — `FROM ams-ubuntu-lite:latest` + python3-venv + pip + código
- [x] Smoke test local — `GET /health → 200`, end-to-end con mock n8n (`task b8a5d998`, 7/7 checks ok)
- [x] Callback verificado — multipart/form-data con `checks_log.txt` + `executive_summary` en español
- [x] `ov-qa-agent-build.tar.gz` generado (12 KB) — código fuente + Dockerfile para build en SERVICIOSIAS
- [ ] Transferir `ov-qa-agent-build.tar.gz` + `.env` a SERVICIOSIAS
- [ ] Build en SERVICIOSIAS: `docker build -t ov-qa-agent:latest .`
- [ ] Levantar container: `docker run -d --name ov-qa-agent --restart unless-stopped -p 5000:5000 -v qa-agent-data:/data --env-file .env ov-qa-agent:latest`
- [ ] Verificar `GET /health` desde SERVICIOSIAS
- [ ] Prueba end-to-end con ticket real desde n8n
