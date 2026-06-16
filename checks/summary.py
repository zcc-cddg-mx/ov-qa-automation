import os
from datetime import datetime

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import anthropic as _anthropic_lib
except ImportError:
    _anthropic_lib = None

_MONTHS_ES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _fallback_summary(task: dict, check_results: list, overall: str) -> str:
    t = task or {}
    raw_month = t.get("month")
    raw_year = t.get("year")
    month = _MONTHS_ES[int(raw_month)] if raw_month and 1 <= int(raw_month) <= 12 else _MONTHS_ES[datetime.now().month]
    year = int(raw_year) if raw_year else datetime.now().year
    ticket = t.get("ticket", "N/A")
    module = t.get("module", "N/A")
    sample = t.get("sample_size", "")
    sample_text = f" Se validaron {sample} pólizas de la muestra aleatoria." if sample else ""
    env = os.environ.get("QA_ENVIRONMENT", "UAT")
    return (
        f"El despliegue del batch de renovaciones para {month} {year} fue aprobado exitosamente. "
        f"Ticket {ticket} — módulo {module}.{sample_text} "
        f"Los checks de migración, salud del servicio, conteo de registros y flujo de cotización "
        f"pasaron sin inconvenientes. "
        f"El ambiente {env} se encuentra en condiciones óptimas para continuar con el proceso de despliegue."
    )


_PROMPT = """\
Eres un líder de QA senior preparando resúmenes ejecutivos de resultados de validación de software en un entorno empresarial.

Contexto:
- ID de Ticket: {ticket}
- Módulo: {module}
- Ambiente: {environment}

Resumen Técnico:
{technical_summary}

Áreas de Validación:
{checks}

Tamaño de Muestra: {sample_size}

Estado General: {overall_status}

Instrucciones:
1. Escribe un resumen ejecutivo conciso (máximo 5 líneas)
2. Usa lenguaje orientado al negocio (evita detalles técnicos de bajo nivel)
3. Explica claramente: qué se validó, si el sistema funciona correctamente, nivel de confianza basado en las validaciones
4. Destaca si las validaciones cubren flujos críticos (APIs, BD, lógica de negocio)
5. Proporciona una conclusión final:
   - Si todo está OK → "Listo para liberación"
   - Si hay algún problema → "No listo para liberación"
6. Asigna un Nivel de Riesgo:
   - BAJO → todas las validaciones pasaron, sin impacto
   - MEDIO → problemas menores, riesgo bajo
   - ALTO → fallas que afectan la funcionalidad
7. Genera un comentario listo para Jira

Formato de salida (usa exactamente estas etiquetas):

Resumen Ejecutivo:
<texto>

Conclusión:
<Listo para liberación | No listo para liberación>

Nivel de Riesgo:
<BAJO | MEDIO | ALTO>

Comentario Jira:
<comentario corto adecuado para actualización en Jira>"""


_CATEGORY_MAP = {
    "flyway_history":   "database",
    "endpoint_health":  "api",
    "row_count":        "data",
    "no_renovar_count": "data",
    "entity_rows":      "data",
    "quote_flow":       "business_rules",
}


def _group_checks(check_results: list) -> list:
    seen = {}
    for c in check_results:
        base = c["name"].split(":")[0]
        cat = _CATEGORY_MAP.get(base, "other")
        if cat not in seen or c["status"] == "failed":
            seen[cat] = c["status"]
    return [{"category": k, "status": v} for k, v in seen.items()]


def _build_prompt(task: dict, check_results: list, overall: str) -> str:
    grouped = _group_checks(check_results or [])
    checks_text = "\n".join(f"  - {c['category']}: {c['status']}" for c in grouped)
    return _PROMPT.format(
        ticket=(task or {}).get("ticket", "N/A"),
        module=(task or {}).get("module", "N/A"),
        environment=os.environ.get("QA_ENVIRONMENT", "UAT"),
        technical_summary=(task or {}).get("summary", overall),
        checks=checks_text,
        sample_size=(task or {}).get("sample_size", "N/A"),
        overall_status=overall.upper(),
    )


def _call_anthropic(prompt: str) -> str:
    timeout = float(os.environ.get("AI_SUMMARY_TIMEOUT", "20"))
    client = _anthropic_lib.Anthropic(
        api_key=os.environ["ANTHROPIC_AUTH_TOKEN"],
        base_url=os.environ.get("ANTHROPIC_BASE_URL"),
        timeout=timeout,
    )
    model = os.environ.get("ANTHROPIC_MODEL", "eu.anthropic.claude-sonnet-4-6")
    msg = client.messages.create(
        model=model,
        max_tokens=int(os.environ.get("OPENAI_MAX_TOKENS", "500")),
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def _call_openai(prompt: str) -> str:
    timeout = float(os.environ.get("AI_SUMMARY_TIMEOUT", "20"))
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=timeout)
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=int(os.environ.get("OPENAI_MAX_TOKENS", "500")),
        temperature=float(os.environ.get("OPENAI_TEMPERATURE", "0.2")),
    )
    return resp.choices[0].message.content.strip()


def format_log(task: dict, check_results: list, overall: str, summary: str) -> str:
    lines = []
    lines.append(f"ticket={task['ticket']} task_id={task['task_id']} result={overall}")
    lines.append(f"command={task['command']} module={task.get('module','')}")
    lines.append("")
    for c in check_results:
        lines.append(f"[CHECK]  {c['name']} — {c['status']} ({c.get('detail', '')})")
    lines.append("")
    lines.append(f"[DONE]   {summary}")
    return "\n".join(lines)


def executive_summary(log_text: str, overall: str, task: dict = None,
                      check_results: list = None) -> str:
    prompt = _build_prompt(task, check_results or [], overall)

    # Anthropic (proxy corporativo Zurich) tiene prioridad
    if _anthropic_lib and os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        try:
            result = _call_anthropic(prompt)
            print(f"[SUMMARY] Anthropic ejecutivo generado ({len(result)} chars)")
            return result
        except Exception as exc:
            print(f"[SUMMARY] Anthropic error — {exc}")

    # Fallback: OpenAI
    if OpenAI and os.environ.get("OPENAI_API_KEY"):
        try:
            result = _call_openai(prompt)
            print(f"[SUMMARY] OpenAI ejecutivo generado ({len(result)} chars)")
            return result
        except Exception as exc:
            print(f"[SUMMARY] OpenAI error — {exc}")

    # Fallback estático: solo para resultados aprobados
    if overall == "approved":
        result = _fallback_summary(task, check_results or [], overall)
        print(f"[SUMMARY] fallback estático ({len(result)} chars)")
        return result

    return ""
