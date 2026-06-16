# Plan de ejecución — QA Agent

> Basado en el contrato v1.0 (`qa_agent_contract.md`).  
> Prerequisito: los valores de las env vars de esquema BD deben ser provistos por el equipo de backend antes de la Fase 3.

---

## Fase 1 — Scaffolding del proyecto

Crear la estructura base del repositorio. Sin lógica de negocio aún.

- [ ] `requirements.txt` — `flask>=3.1`, `requests>=2.31`, `psycopg2-binary>=2.9`
- [ ] `app.py` — entrada principal; arranca Flask en `$PORT` (default 5000)
- [ ] `docker-entrypoint.sh` — script de arranque del container
- [ ] `Dockerfile.base` — `ams-ubuntu-lite` + Python venv + deps
- [ ] `Dockerfile` — `FROM qa-agent-base` + código
- [ ] `config.json.example` — plantilla de env vars (sin valores reales)
- [ ] `.env.example` — ídem para desarrollo local
- [ ] Verificar que `python app.py` levanta y responde `GET /health → 200`

---

## Fase 2 — API HTTP y persistencia

Implementar los 4 endpoints y la capa SQLite. Sin checks reales aún — el worker solo persiste y devuelve un resultado mock.

- [ ] `db.py` — inicialización SQLite, schema `qa_tasks` (ver contrato §7)
- [ ] `POST /validate` — validar campos requeridos, adquirir lock, encolar worker, responder 202
- [ ] `GET /status/<task_id>` — leer de SQLite, responder estado
- [ ] `GET /tasks?limit=N` — historial, máx 200, orden DESC
- [ ] `GET /health` — liveness check
- [ ] Concurrencia: `threading.Lock` adquirido en el handler (no en el worker)
- [ ] Rechazo inmediato con `active_task` si el lock está tomado
- [ ] Worker stub: persiste `status=done`, `result=approved`, checks vacíos
- [ ] Prueba manual: enviar `POST /validate` con payload de ejemplo del contrato

---

## Fase 3 — Checks de validación *(requiere env vars de backend)*

Implementar los 5 checks reales en el worker. Prerequisito: valores confirmados de `RENEWAL_TABLE`, `RULES_TABLE`, etc.

- [ ] `checks/flyway.py` — `flyway_history`: SQL contra `$FLYWAY_HISTORY_TABLE`
- [ ] `checks/health.py` — `endpoint_health`: HTTP GET a `$HEALTH_PATH`, timeout 10s
- [ ] `checks/renewal.py` — `row_count` y `no_renovar_count`: SQL contra `$RENEWAL_TABLE`
- [ ] `checks/rules.py` — `entity_rows`: SQL contra `$RULES_TABLE`
- [ ] Worker real: ejecuta checks según `command`, acumula resultados, nunca aborta al primer fallo
- [ ] Resultado global: `approved` si todos pasan, `rejected` si alguno falla
- [ ] Distinguir `rejected` (checks fallaron) de `error` (infraestructura — DB/HTTP inaccesible)

---

## Fase 4 — Callback a n8n

- [ ] `callback.py` — POST al `callback_url` del request (o `$N8N_CALLBACK_URL` como fallback)
- [ ] Retry: 3 intentos, backoff 2s / 4s / 8s
- [ ] Disparar siempre en bloque `finally` del worker (éxito, rechazo y error)
- [ ] Log `[N8N]` con URL, status HTTP y número de intento

---

## Fase 5 — Tests

- [ ] `tests/test_api.py` — endpoints HTTP (Flask test client): 202 accepted, 202 rejected, 400 campos faltantes, 200 status/tasks/health
- [ ] `tests/test_checks.py` — checks unitarios con mocks de DB y HTTP
- [ ] `tests/test_worker.py` — flujo completo: worker ejecuta checks, persiste resultado, dispara callback
- [ ] `tests/test_db.py` — inicialización SQLite, insert/query de `qa_tasks`
- [ ] Confirmar `pytest` pasa en verde

---

## Fase 6 — Build y despliegue en SERVICIOSIAS

- [ ] Build `qa-agent-base`: `docker build -f Dockerfile.base -t qa-agent-base:latest .`
- [ ] Build `ov-qa-agent`: `docker build -t ov-qa-agent:latest .`
- [ ] Smoke test local con todas las env vars reales
- [ ] Transferir imagen a SERVICIOSIAS
- [ ] Levantar container con `docker run` completo (ver contrato §10)
- [ ] Verificar `GET /health` desde n8n
- [ ] Prueba end-to-end: lanzar un ticket real por el pipeline completo

---

## Dependencias entre fases

```
Fase 1 → Fase 2 → Fase 3* → Fase 4 → Fase 5 → Fase 6
                  ↑
          requiere env vars de backend (tablas y campos reales)
```

Las fases 1, 2 y 4 son independientes del equipo de backend y pueden avanzarse en paralelo con la confirmación del esquema.
