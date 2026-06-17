# Análisis de contenedores — QA Agent

## 1. Imagen actual

| Campo | Valor |
|---|---|
| Base | `ams-ubuntu-lite:latest` |
| Python | venv en `/opt/venv` (instalado vía apt `python3-venv`) |
| Dependencias | pip desde `requirements.txt` |
| Código | `/app/` |
| Entrypoint | `/app/docker-entrypoint.sh` |
| CMD | `python app.py` |
| Puerto expuesto | `5000` |

### Dockerfile (single-stage)

```
ams-ubuntu-lite:latest
  └── apt: python3-pip, python3-venv
  └── /opt/venv  ← pip install requirements.txt
  └── /app       ← código fuente
```

> **Local (sin acceso a apt):** usar `Dockerfile.local-test` con base `ov-agent-base:latest`.
> Ese archivo **no se incluye en el repo** ni se despliega en SERVICIOSIAS.

---

## 2. Persistencia — volumen `/data`

| Ruta | Contenido | Variable |
|---|---|---|
| `/data/qa_tasks.db` | SQLite — historial de tareas | `QA_TASKS_DB` |
| `/data/uploads/` | Archivos Excel recibidos en `/validate` | `QA_UPLOAD_DIR` |

El entrypoint crea el directorio padre de `QA_TASKS_DB` antes de arrancar el proceso.

```sh
# docker-entrypoint.sh
mkdir -p "$(dirname "${QA_TASKS_DB:-/data/qa_tasks.db}")"
exec "$@"
```

Montar el volumen nombrado es obligatorio para no perder el historial entre reinicios:

```sh
docker run -v qa-agent-data:/data ...
```

---

## 3. Variables de entorno requeridas

Se inyectan en tiempo de ejecución vía `--env-file .env`. **Nunca se commitean.**

### Conectividad

| Variable | Descripción |
|---|---|
| `AMS_POLICY_HOST` | Base URL del servicio ams-policy DEV |
| `AMS_RULE_HOST` | Base URL del servicio ams-rule DEV |
| `HEALTH_PATH` | Path del endpoint de salud (default `/actuator/health`) |
| `DB_DSN` | JDBC DSN Oracle (`jdbc:oracle:thin:@host:1521:sid`) |
| `N8N_CALLBACK_URL` | Webhook n8n destino del callback |

### Auth JWT

| Variable | Descripción |
|---|---|
| `AUTH_LOGIN_URL` | URL de login (retorna `{"accessToken": "..."}`) |
| `AUTH_USERNAME` | Usuario de servicio |
| `AUTH_PASSWORD` | Contraseña |
| `AUTH_TENANT` | Header `x-tenantid-1` (default `ec`) |

### Credenciales Oracle (dos esquemas)

| Variable | Esquema |
|---|---|
| `DB_USER` / `DB_PASSWORD` | ECU_POLICY |
| `DB_RULE_USER` / `DB_RULE_PASSWORD` | ECU_RULE |

### IA

| Variable | Descripción |
|---|---|
| `ANTHROPIC_AUTH_TOKEN` | API key Anthropic (proxy corporativo) |
| `ANTHROPIC_BASE_URL` | URL proxy Zurich para Anthropic |
| `OPENAI_API_KEY` | Fallback OpenAI |

### Operación

| Variable | Default | Descripción |
|---|---|---|
| `PORT` | `5000` | Puerto HTTP |
| `QA_TASKS_DB` | `/data/qa_tasks.db` | Ruta SQLite |
| `QA_UPLOAD_DIR` | `/data/uploads` | Directorio uploads Excel |
| `QA_SAMPLE_SIZE` | `10` | Placas a muestrear por tarea |
| `RETENTION_DAYS` | `90` | Retención de registros SQLite |

---

## 4. Normalización de env vars (import-time)

`app.py` ejecuta al importarse (antes de cualquier request) tres correcciones:

1. **Typos heredados** — `RENEWAL_SHEMA` → `RENEWAL_SCHEMA`, `RULES_SHEMA` → `RULES_SCHEMA`
2. **Alias de host** — si `AMS_POLICY_HOST=OV_HOST`, resuelve el valor de `OV_HOST`
3. **Quitar comillas** — `.env` puede guardar `FLYWAY_HISTORY_TABLE="schema_history"` con comillas literales; se hace `.strip('"').strip("'")`

Esto corre a nivel de módulo para que funcione bajo cualquier modo de arranque (`python app.py`, gunicorn, Docker CMD).

---

## 5. Logs

`PYTHONUNBUFFERED=1` está seteado en el Dockerfile. Sin esto, los `print()` del worker quedan en buffer y no aparecen en `docker logs` hasta que el proceso termina o el buffer se llena.

Formato de logs:

```
[RECV]   task_id=ed9e844d ticket=INC23703493-001 ACCEPTED
[CHECK]  flyway_history — ok (migration recorded in ECU_POLICY."schema_history")
[CHECK]  row_count — ok (1589 rows found for 2026/07)
[DONE]   task_id=ed9e844d result=approved (All 6 checks passed)
[N8N]    callback → https://n8n.host/webhook/qa-result status=200 (attempt 1)
```

---

## 6. Comando de deploy en SERVICIOSIAS

```sh
# Build
docker build -t ov-qa-agent:latest .

# Run
docker run -d \
  --name ov-qa-agent \
  --restart unless-stopped \
  -p 5000:5000 \
  -v qa-agent-data:/data \
  --env-file .env \
  ov-qa-agent:latest

# Verificar
curl http://localhost:5000/health
```

---

## 7. Limitaciones conocidas

| Limitación | Detalle |
|---|---|
| Single-threaded | Flask dev server, una tarea a la vez (threading.Lock). Suficiente para el pipeline actual. |
| Sin WSGI productivo | `python app.py` usa el servidor de desarrollo de Flask. Para mayor carga: agregar gunicorn. |
| Uploads no purgados | Los Excel en `/data/uploads/` no se eliminan automáticamente. Purga manual periódica. |
| Credentials en `.env` | `DB_PASSWORD`, `AUTH_PASSWORD` en texto plano. Aceptable en SERVICIOSIAS; no usar en ambientes con secrets manager. |
