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
    now = datetime.now()
    month = _MONTHS_ES[now.month]
    year = now.year
    ticket = (task or {}).get("ticket", "N/A")
    module = (task or {}).get("module", "N/A")
    sample = (task or {}).get("sample_size", "")
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
You are a senior QA lead preparing executive summaries for software validation results in an enterprise environment.

Context:
- Ticket ID: {ticket}
- Module: {module}
- Environment: {environment}

Technical Summary:
{technical_summary}

Validation Areas:
{checks}

Sample Size: {sample_size}

Overall Status: {overall_status}

Instructions:
1. Write a concise executive summary (max 5 lines)
2. Use business-oriented language (avoid low-level technical detail)
3. Clearly explain: what was validated, whether the system behaves correctly, confidence level based on validations
4. Highlight if validations cover critical flows (APIs, DB, business logic)
5. Provide a final conclusion:
   - If everything is OK → "Ready for release"
   - If any issue → "Not ready for release"
6. Assign a Risk Level:
   - LOW → all validations passed, no impact
   - MEDIUM → minor issues, low risk
   - HIGH → failures affecting functionality
7. Generate a Jira-ready comment

Output format (use exactly these labels):

Executive Summary:
<text>

Conclusion:
<Ready for release | Not ready for release>

Risk Level:
<LOW | MEDIUM | HIGH>

Jira Comment:
<short comment suitable for Jira update>"""


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
