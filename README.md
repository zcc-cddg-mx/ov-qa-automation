# ov-qa-automation

QA Agent — servicio HTTP containerizado que valida deploys automáticos en el entorno DEV como parte del pipeline de automatización OV Suscripciones.

- Contrato completo: [architecture/qa_agent_contract.md](architecture/qa_agent_contract.md)
- Arquitectura global del pipeline: [architecture/info.md](architecture/info.md)

---

## Rol en el pipeline

El QA Agent es el **Step 6 de 9**. Se activa después de que Azure DevOps completa el deploy a DEV:

```
Jira → n8n → Enricher Agent → Code Agent → n8n (crea PR) → Azure DevOps (deploy DEV)
  → n8n → QA Agent ← este repo
  → n8n → Jira (cierra / reabre ticket)
```

Recibe un request de n8n con el contexto de la migración, ejecuta checks de validación, y devuelve el resultado vía callback. **Solo lee** — no hace push, no crea PRs, no modifica datos (HTTP GET + SQL SELECT únicamente).

---

## API

| Endpoint | Descripción |
|---|---|
| `POST /validate` | Encola una validación; responde 202 inmediatamente |
| `GET /status/<task_id>` | Consulta estado de una tarea (`queued → running → done\|error`) |
| `GET /tasks?limit=50` | Historial de validaciones (máx 200, persiste en SQLite) |
| `GET /health` | Liveness check |

Un check activo a la vez. Si llega una segunda solicitud mientras hay una en curso, se rechaza con `202 {"status": "rejected"}`.

---

## Checks de validación

| Check | Tipo | `ren-data` | `rules` |
|---|---|---|---|
| `flyway_history` | SQL | ✓ | ✓ |
| `endpoint_health` | HTTP | ✓ | ✓ |
| `row_count` | SQL | ✓ | — |
| `no_renovar_count` | SQL | ✓ | — |
| `entity_rows` | SQL | — | ✓ |

Todos los checks se ejecutan antes de resolver el resultado global. El resultado es `approved` si todos pasan; cualquier fallo → `rejected`.

---

## Variables de entorno

**Conectividad**

| Variable | Descripción |
|---|---|
| `AMS_POLICY_HOST` | `host:puerto` del servicio ams-policy en DEV |
| `AMS_RULE_HOST` | `host:puerto` del servicio ams-rule en DEV |
| `HEALTH_PATH` | Path del endpoint de salud (default `/actuator/health`) |
| `DB_DSN` | DSN PostgreSQL DEV (`postgresql://user:pass@host:5432/db`) |
| `N8N_CALLBACK_URL` | URL webhook n8n (fallback si `callback_url` no viene en el request) |

**Esquema BD — `ren-data`**

| Variable | Descripción |
|---|---|
| `FLYWAY_HISTORY_TABLE` | Tabla de historial Flyway (ej. `flyway_schema_history`) |
| `RENEWAL_TABLE` | Tabla con filas de vencimientos (ej. `frd_fixed_renewal_data`) |
| `RENEWAL_MIGRATION_ID_FIELD` | Campo que vincula filas a la migración (ej. `migration_id`) |
| `RENEWAL_BLOCKED_FIELD` | Campo de bloqueo de renovación (ej. `renewal_blocked`) |

**Esquema BD — `rules`**

| Variable | Descripción |
|---|---|
| `RULES_TABLE` | Tabla con reglas de tarificación (ej. `ams_rule_entry`) |
| `RULES_ENTITY_FIELD` | Campo de entidad en `RULES_TABLE` (ej. `entity`) |
| `RULES_MIGRATION_ID_FIELD` | Campo que vincula filas a la migración (ej. `migration_id`) |

**Operación**

| Variable | Descripción |
|---|---|
| `QA_TASKS_DB` | Path SQLite (default `/data/qa_tasks.db`) |
| `PORT` | Puerto HTTP (default `5000`) |

---

## Stack

Python · Flask · psycopg2 · SQLite · Docker (`ams-ubuntu-lite:latest`)
