import os
import json
from typing import List, Dict, Any
from openai import OpenAI


def _get_client() -> OpenAI | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def parse_note_to_tasks(texto: str, now_iso: str, timezone: str) -> List[Dict[str, Any]]:
    client = _get_client()

    if client is None:
        return [{
            "title": texto[:60].strip(),
            "description": texto.strip(),
            "date_text": None,
            "time_text": None,
            "day_part": None,
            "channel": None,
        }]

    system_prompt = f"""
Eres un asistente que convierte notas en tareas.

Fecha/hora actual (ancla): {now_iso}
Zona horaria: {timezone}

Devuelve SIEMPRE JSON:
{{
  "tasks": [
    {{
      "title": "título breve",
      "description": "descripción completa",
      "date_text": "ej: 'hoy', 'mañana', 'el lunes', 'el 20 de enero'" o null,
      "time_text": "HH:MM" o null,
      "day_part": "morning" | "noon" | "afternoon" | "night" | null,
      "channel": "call" | "email" | "whatsapp" | "otro" | null
    }}
  ]
}}

REGLAS:
- 'a las 17' -> time_text="17:00"
- '17h' -> "17:00"
- '14.30' -> "14:30"
- No devuelvas fechas ISO, ni inventes años.
""".strip()

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f'Nota: """{texto}"""'},
        ],
    )

    content = resp.choices[0].message.content
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return [{
            "title": texto[:60].strip(),
            "description": texto.strip(),
            "date_text": None,
            "time_text": None,
            "day_part": None,
            "channel": None,
        }]

    tasks = data.get("tasks", [])
    out: List[Dict[str, Any]] = []
    for t in tasks:
        out.append({
            "title": (t.get("title") or texto[:60]).strip(),
            "description": (t.get("description") or texto).strip(),
            "date_text": t.get("date_text") or None,
            "time_text": t.get("time_text") or None,
            "day_part": t.get("day_part") or None,
            "channel": t.get("channel") or None,
        })

    if not out:
        out.append({
            "title": texto[:60].strip(),
            "description": texto.strip(),
            "date_text": None,
            "time_text": None,
            "day_part": None,
            "channel": None,
        })

    return out
