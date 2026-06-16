#!/usr/bin/env bash
# 3-test-agent.sh — prueba el QA Agent end-to-end
#
# Uso:
#   ./3-test-agent.sh [--url http://host:5000] [--callback-port 9099] [--excel /ruta/archivo.xlsx]
#
# Casos:
#   1. Health check
#   2. Campos faltantes → 400
#   3. ren-data sin archivo → 400
#   4. rules sin entity → 400
#   5. ren-data completo → 202 + polling hasta done/error
#   6. Concurrencia — segunda tarea rechazada mientras la primera corre
#   7. Historial GET /tasks
#   8. Callback n8n — captura multipart y muestra campos + checks_log

set -euo pipefail

BASE_URL="http://localhost:5000"
CALLBACK_PORT="9099"
EXCEL=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --url)           BASE_URL="$2";      shift 2 ;;
    --callback-port) CALLBACK_PORT="$2"; shift 2 ;;
    --excel)         EXCEL="$2";         shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── helpers ──────────────────────────────────────────────────────────────────

ok()   { echo "  ✓ $*"; }
fail() { echo "  ✗ $*"; }

poll() {
  local task_id="$1" max_iter="$2" interval="$3"
  for i in $(seq 1 "${max_iter}"); do
    SRES=$(curl -sf "${BASE_URL}/status/${task_id}")
    STATUS=$(echo "${SRES}" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
    if [[ "${STATUS}" != "queued" && "${STATUS}" != "running" ]]; then
      echo "${SRES}" | python3 -m json.tool
      return
    fi
    printf "  [%ds] status=%s\n" "$((i * interval))" "${STATUS}"
    sleep "${interval}"
  done
  echo "TIMEOUT — last status: ${STATUS}"
}

# ─── 1. Health ────────────────────────────────────────────────────────────────

echo ""
echo "=== 1. Health ==="
HRES=$(curl -sf "${BASE_URL}/health")
echo "${HRES}" | python3 -m json.tool
STATUS=$(echo "${HRES}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))")
[[ "${STATUS}" == "ok" ]] && ok "health ok" || fail "health returned: ${STATUS}"

# ─── 2. Campos faltantes → 400 ────────────────────────────────────────────────

echo ""
echo "=== 2. Validación — falta command (debe retornar 400) ==="
HTTP=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${BASE_URL}/validate" \
  -F "ticket=INC0001")
[[ "${HTTP}" == "400" ]] && ok "400 recibido" || fail "esperado 400, recibido ${HTTP}"
curl -s -X POST "${BASE_URL}/validate" -F "ticket=INC0001" | python3 -m json.tool

# ─── 3. ren-data sin archivo → 400 ───────────────────────────────────────────

echo ""
echo "=== 3. ren-data sin archivo Excel (debe retornar 400) ==="
HTTP=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${BASE_URL}/validate" \
  -F "ticket=INC0001" -F "command=ren-data" -F "year=2026" -F "month=7")
[[ "${HTTP}" == "400" ]] && ok "400 recibido" || fail "esperado 400, recibido ${HTTP}"
curl -s -X POST "${BASE_URL}/validate" \
  -F "ticket=INC0001" -F "command=ren-data" -F "year=2026" -F "month=7" | python3 -m json.tool

# ─── 4. rules sin entity → 400 ───────────────────────────────────────────────

echo ""
echo "=== 4. rules sin entity (debe retornar 400) ==="
HTTP=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${BASE_URL}/validate" \
  -F "ticket=INC0001" -F "command=rules" \
  -F "module=ams-rule" -F "migration_name=V2026_test")
[[ "${HTTP}" == "400" ]] && ok "400 recibido" || fail "esperado 400, recibido ${HTTP}"
curl -s -X POST "${BASE_URL}/validate" \
  -F "ticket=INC0001" -F "command=rules" \
  -F "module=ams-rule" -F "migration_name=V2026_test" | python3 -m json.tool

# ─── 5. ren-data completo ─────────────────────────────────────────────────────

echo ""
echo "=== 5. POST /validate (ren-data completo) ==="

if [ -z "${EXCEL}" ]; then
  echo "  SKIP — provee --excel /ruta/archivo.xlsx para ejecutar este caso"
else
  RESP=$(curl -sf -X POST "${BASE_URL}/validate" \
    -F "ticket=INC_TEST_001" \
    -F "command=ren-data" \
    -F "year=2026" \
    -F "month=7" \
    -F "file=@${EXCEL}")
  echo "${RESP}" | python3 -m json.tool
  TASK_ID=$(echo "${RESP}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('task_id',''))")

  if [ -n "${TASK_ID}" ]; then
    echo "Polling /status/${TASK_ID} (max 10 min)..."
    poll "${TASK_ID}" 120 5
  fi
fi

# ─── 6. Concurrencia ──────────────────────────────────────────────────────────

echo ""
echo "=== 6. Concurrencia — segunda tarea debe ser rechazada ==="

if [ -z "${EXCEL}" ]; then
  echo "  SKIP — provee --excel para ejecutar este caso"
else
  curl -sf -X POST "${BASE_URL}/validate" \
    -F "ticket=INC_CONC_1" -F "command=ren-data" \
    -F "year=2026" -F "month=7" -F "file=@${EXCEL}" > /tmp/qa_task1.json &
  sleep 0.3
  curl -sf -X POST "${BASE_URL}/validate" \
    -F "ticket=INC_CONC_2" -F "command=ren-data" \
    -F "year=2026" -F "month=7" -F "file=@${EXCEL}" > /tmp/qa_task2.json
  wait

  echo "Tarea 1:"
  python3 -m json.tool < /tmp/qa_task1.json
  echo "Tarea 2 (debe ser rejected o queued):"
  python3 -m json.tool < /tmp/qa_task2.json

  T2_STATUS=$(python3 -c "import json; print(json.load(open('/tmp/qa_task2.json')).get('status',''))")
  [[ "${T2_STATUS}" == "rejected" ]] && ok "concurrencia correcta — segunda tarea rechazada" \
    || echo "  INFO: tarea 2 status=${T2_STATUS}"
fi

# ─── 7. Historial ─────────────────────────────────────────────────────────────

echo ""
echo "=== 7. GET /tasks (últimas 10) ==="
curl -sf "${BASE_URL}/tasks?limit=10" | python3 -m json.tool

# ─── 8. Callback n8n — sin OpenAI ────────────────────────────────────────────

echo ""
echo "=== 8. Callback n8n — multipart sin OpenAI (desde tests/tasks/1f87e04f.json) ==="

CALLBACK_FILE=$(mktemp /tmp/qa_callback_XXXX.bin)

# servidor HTTP mínimo: acepta un POST, escribe body a archivo, responde 200
cat > /tmp/_qa_callback_server.py << 'PYEOF'
import sys, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

port = int(sys.argv[1])
out  = sys.argv[2]

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        ct = self.headers.get("Content-Type", "")
        open(out, "wb").write(body)
        open(out + ".ct", "w").write(ct)
        self.send_response(200); self.end_headers(); self.wfile.write(b'ok')
        threading.Thread(target=self.server.shutdown).start()

HTTPServer(("0.0.0.0", port), H).serve_forever()
PYEOF

python3 /tmp/_qa_callback_server.py "${CALLBACK_PORT}" "${CALLBACK_FILE}" &
CB_PID=$!
sleep 0.5
echo "  callback listener PID=${CB_PID} en localhost:${CALLBACK_PORT}"

python3 - << PYEOF
import json, sys, os
sys.path.insert(0, '${SCRIPT_DIR}')

# cargar .env si existe
env_file = '${SCRIPT_DIR}/.env'
if os.path.exists(env_file):
    for line in open(env_file):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

import callback

TASK_FILE = '${SCRIPT_DIR}/tests/tasks/1f87e04f.json'
if not os.path.exists(TASK_FILE):
    print("  SKIP — tests/tasks/1f87e04f.json no encontrado")
    sys.exit(0)

with open(TASK_FILE) as f:
    task = json.load(f)

t = {
    'task_id': task['task_id'], 'ticket': task['ticket'],
    'command': task['command'], 'module': task['module'],
    'migration_name': task.get('migration_name', ''),
    'branch': '', 'aux_branch': '', 'commit_id': '',
    'callback_url': 'http://localhost:${CALLBACK_PORT}/webhook/test',
}
callback.send(t, task['checks'], task['result'], task['summary'], task['updated_at'])
PYEOF

for i in $(seq 1 20); do sleep 0.5; [ -s "${CALLBACK_FILE}" ] && break; done
wait "${CB_PID}" 2>/dev/null || true

CT=$(cat "${CALLBACK_FILE}.ct" 2>/dev/null || echo "")
echo ""
echo "  Content-Type: ${CT}"
echo ""

python3 - "${CALLBACK_FILE}" "${CT}" << 'PYEOF'
import sys

body = open(sys.argv[1], 'rb').read()
ct = sys.argv[2] if len(sys.argv) > 2 else ""

boundary = None
for part in ct.split(";"):
    part = part.strip()
    if part.startswith("boundary="):
        boundary = part[len("boundary="):].strip('"').encode()
        break

if not boundary:
    print("  ERROR: no se recibió callback multipart"); sys.exit(1)

parts = body.split(b"--" + boundary)
print("  Campos recibidos:")
for part in parts[1:-1]:
    header, _, content = part.partition(b"\r\n\r\n")
    content = content.rstrip(b"\r\n")
    hdr = header.decode("utf-8", errors="replace")
    if "filename" in hdr:
        print(f"\n  --- checks_log.txt ---")
        print(content.decode("utf-8", errors="replace"))
        print("  ---")
    else:
        name = hdr.split('name="')[1].split('"')[0]
        val = content.decode("utf-8", errors="replace")
        print(f"  {name}: {val[:120]}")
PYEOF

rm -f "${CALLBACK_FILE}" "${CALLBACK_FILE}.ct"

# ─── 9. Callback n8n — con OpenAI mock ───────────────────────────────────────

echo ""
echo "=== 9. Callback n8n — multipart con OpenAI mock (executive_summary) ==="

CALLBACK_FILE2=$(mktemp /tmp/qa_callback_XXXX.bin)

python3 /tmp/_qa_callback_server.py "${CALLBACK_PORT}" "${CALLBACK_FILE2}" &
CB_PID2=$!
sleep 0.5
echo "  callback listener PID=${CB_PID2} en localhost:${CALLBACK_PORT}"

python3 - << PYEOF
import json, sys, os
from unittest.mock import patch, MagicMock
sys.path.insert(0, '${SCRIPT_DIR}')

# cargar .env (sin OPENAI_API_KEY para que el mock tome control)
env_file = '${SCRIPT_DIR}/.env'
if os.path.exists(env_file):
    for line in open(env_file):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

os.environ['OPENAI_API_KEY'] = 'sk-mock-test'

MOCK_SUMMARY = (
    "El despliegue del batch de renovaciones para julio 2026 fue aprobado exitosamente. "
    "Se validaron 10 pólizas de la muestra aleatoria, confirmando que el cálculo de prima "
    "anual es consistente con los factores registrados en la base de datos. "
    "Los checks de migración, salud del servicio y conteo de registros también pasaron sin inconvenientes. "
    "El ambiente DEV/UAT se encuentra en condiciones óptimas para continuar con el proceso de despliegue."
)

mock_choice = MagicMock()
mock_choice.message.content = MOCK_SUMMARY
mock_resp = MagicMock()
mock_resp.choices = [mock_choice]
mock_client = MagicMock()
mock_client.chat.completions.create.return_value = mock_resp

import callback

with open('${SCRIPT_DIR}/tests/tasks/1f87e04f.json') as f:
    task = json.load(f)

t = {
    'task_id': task['task_id'], 'ticket': task['ticket'],
    'command': task['command'], 'module': task['module'],
    'migration_name': task.get('migration_name', ''),
    'branch': '', 'aux_branch': '', 'commit_id': '',
    'callback_url': 'http://localhost:${CALLBACK_PORT}/webhook/test',
}

with patch('checks.summary.OpenAI', return_value=mock_client):
    callback.send(t, task['checks'], task['result'], task['summary'], task['updated_at'])
PYEOF

for i in $(seq 1 20); do sleep 0.5; [ -s "${CALLBACK_FILE2}" ] && break; done
wait "${CB_PID2}" 2>/dev/null || true

CT2=$(cat "${CALLBACK_FILE2}.ct" 2>/dev/null || echo "")
echo ""
echo "  Content-Type: ${CT2}"
echo ""

python3 - "${CALLBACK_FILE2}" "${CT2}" << 'PYEOF'
import sys

body = open(sys.argv[1], 'rb').read()
ct = sys.argv[2] if len(sys.argv) > 2 else ""

boundary = None
for part in ct.split(";"):
    part = part.strip()
    if part.startswith("boundary="):
        boundary = part[len("boundary="):].strip('"').encode()
        break

if not boundary:
    print("  ERROR: no se recibió callback multipart"); sys.exit(1)

parts = body.split(b"--" + boundary)
print("  Campos recibidos:")
for part in parts[1:-1]:
    header, _, content = part.partition(b"\r\n\r\n")
    content = content.rstrip(b"\r\n")
    hdr = header.decode("utf-8", errors="replace")
    if "filename" in hdr:
        print(f"\n  --- checks_log.txt ---")
        print(content.decode("utf-8", errors="replace"))
        print("  ---")
    else:
        name = hdr.split('name="')[1].split('"')[0]
        val = content.decode("utf-8", errors="replace")
        if name == "executive_summary":
            print(f"\n  executive_summary:\n  {val}\n")
        else:
            print(f"  {name}: {val[:120]}")
PYEOF

rm -f "${CALLBACK_FILE2}" "${CALLBACK_FILE2}.ct" /tmp/_qa_callback_server.py

echo ""
echo "=== FIN ==="
