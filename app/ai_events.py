import os
import json
from typing import Dict, Any
from openai import OpenAI


def _get_client() -> OpenAI | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def parse_text_to_event(texto: str, now_iso: str, timezone: str) -> Dict[str, Any]:
    client = _get_client()

    if client is None:
        return {
            "title": texto[:60].strip(),
            "description": texto.strip(),
            "date_text": None,
            "start_time": None,
            "end_time": None,
            "duration_minutes": 30,
            "rrule": None,
            "timezone": timezone,
        }

    system_prompt = f"""
Eres un asistente que extrae UN evento de agenda a partir de texto.

Fecha/hora actual (ancla): {now_iso}
Zona horaria: {timezone}

Devuelve SIEMPRE JSON con este formato EXACTO:

{{
  "title": "título breve",
  "description": "descripción completa",
  "date_text": "expresión de fecha: 'hoy', 'mañana', 'el lunes', 'el 20 de enero', 'este martes'..." o null,
  "start_time": "HH:MM" o null,
  "end_time": "HH:MM" o null,
  "duration_minutes": número entero (si no hay end_time, usa 30),
  "rrule": "cadena RRULE iCal (sin DTSTART) o null",
  "timezone": "{timezone}"
}}

REGLAS:
1) Si el texto indica rango horario:
   - "de 16 a 17" => start_time="16:00", end_time="17:00"
2) Si indica una sola hora:
   - "a las 19" => start_time="19:00", end_time=null, duration_minutes=30
3) Recurrencias:
   - "cada lunes" => rrule="FREQ=WEEKLY;BYDAY=MO"
   - "todos los días" => rrule="FREQ=DAILY"
   - "cada mes el día 1" => rrule="FREQ=MONTHLY;BYMONTHDAY=1"
4) MUY IMPORTANTE:
   - Si rrule != null y no hay una fecha concreta, rellena date_text para anclar la primera ocurrencia:
     * semanal BYDAY=MO => date_text="el lunes" (o el día correspondiente)
     * daily => date_text="hoy"
     * monthly (BYMONTHDAY=...) => date_text="hoy"
5) NO inventes fechas ISO ni años.
""".strip()

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f'Texto: """{texto}"""'},
        ],
    )

    content = resp.choices[0].message.content
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {
            "title": texto[:60].strip(),
            "description": texto.strip(),
            "date_text": None,
            "start_time": None,
            "end_time": None,
            "duration_minutes": 30,
            "rrule": None,
            "timezone": timezone,
        }

    return {
        "title": (data.get("title") or texto[:60]).strip(),
        "description": (data.get("description") or texto).strip(),
        "date_text": data.get("date_text") or None,
        "start_time": data.get("start_time") or None,
        "end_time": data.get("end_time") or None,
        "duration_minutes": int(data.get("duration_minutes") or 30),
        "rrule": data.get("rrule") or None,
        "timezone": data.get("timezone") or timezone,
    }
