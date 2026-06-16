import os

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


_PROMPT = """Eres un agente de QA en una aseguradora. Se ejecutaron validaciones automáticas sobre un despliegue en el ambiente DEV/UAT.
Redacta un resumen ejecutivo en español, en 2-3 párrafos cortos, dirigido al equipo de negocio (no técnico).
Indica claramente si el despliegue fue aprobado o rechazado, menciona los puntos clave y cualquier observación relevante.
No uses listas con viñetas ni formato markdown. Escribe en prosa."""


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


def executive_summary(log_text: str, overall: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return ""

    try:
        client = OpenAI(api_key=api_key)
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _PROMPT},
                {"role": "user", "content": f"Resultado: {overall.upper()}\n\n{log_text}"},
            ],
            max_tokens=400,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        print(f"[SUMMARY] OpenAI error — skipping: {exc}")
        return ""
