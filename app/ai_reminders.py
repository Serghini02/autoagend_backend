import os
import json
from typing import Dict, Any, List
from openai import OpenAI

def _get_client() -> OpenAI | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)

def analyze_reminder_intent(texto: str, now_iso: str, timezone: str) -> Dict[str, Any]:
    """
    Analiza si el texto es un recordatorio y extrae información.
    """
    client = _get_client()
    
    if client is None:
        # Fallback si no hay AI key
        return {
            "is_reminder": False,
            "task_type": "task",
            "title": texto[:60],
            "needs_conversation": False
        }

    system_prompt = f"""
Eres Plani, un asistente experto en gestión del tiempo.
Tu tarea es analizar un texto y detectar SI ES UN RECORDATORIO.

Fecha actual: {now_iso}
Zona horaria: {timezone}

Un recordatorio suele implicar una acción futura específica ("recordarme llamar a X", "avisar antes de Y").
Si es una tarea simple ("comprar leche", "limpiar coche") pero con fecha límite, también puede ser recordatorio.
Si es un evento ("reunión lunes 17h"), trátalo como "event".

Devuelve JSON EXACTO:
{{
  "is_reminder": bool,
  "task_type": "reminder" | "task" | "event",
  "title": "título de la acción",
  "description": "descripción completa",
  "deadline": "texto original de la fecha límite" o null,
  "has_deadline": bool,
  "remind_at_text": "texto original de cuándo recordar" o null,
  "needs_conversation": bool (true si falta info crucial sobre CUÁNDO recordar)
}}

Reglas:
1. Si el usuario dice "recordarme X antes del jueves", faltan datos (¿cuánto antes?). needs_conversation=true.
2. Si usuario dice "recuérdame mañana a las 9", está completo. needs_conversation=false (o true si quieres confirmar).
3. Si es "llamar a pepe", asume "task" y needs_conversation=false (se crea tarea normal).
""".strip()

    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": texto},
            ],
        )
        content = resp.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"Error AI analyze: {e}")
        return {
            "is_reminder": False,
            "task_type": "task",
            "title": texto[:60],
            "needs_conversation": False
        }

def generate_reminder_question(
    conversation_history: List[Dict[str, str]],
    current_context: Dict[str, Any],
    now_iso: str, 
    timezone: str
) -> Dict[str, Any]:
    """
    Genera la siguiente pregunta de Plani basada en el historial y contexto.
    """
    client = _get_client()
    if not client:
        return {
            "message": "¿Cuándo quieres el recordatorio?",
            "quick_replies": [],
            "next_step": "complete"
        }

    system_prompt = f"""
Eres Plani, un asistente amigable y eficiente.
Estás en medio de una conversación para configurar un recordatorio.
Contexto actual: {json.dumps(current_context, ensure_ascii=False)}
Fecha actual: {now_iso}

Tu objetivo es obtener la información faltante (cuándo recordar, frecuencia, etc).
Sé breve. Usa emojis.

Devuelve JSON:
{{
  "message": "texto de tu pregunta o confirmación",
  "quick_replies": [
    {{"id": "id_unico", "label": "texto botón", "value": {{ "action": "...", "data": "..." }} }}
  ],
  "next_step": "ask_time" | "ask_date" | "confirm" | "complete",
  "extracted_data_update": {{ ... datos nuevos extraídos del último mensaje usuario ... }}
}}
""".strip()

    try:
        messages = [{"role": "system", "content": system_prompt}]
        # Añadir historial (últimos 6 mensajes para contexto)
        messages.extend(conversation_history[-6:])

        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            response_format={"type": "json_object"},
            messages=messages,
        )
        content = resp.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"Error AI question: {e}")
        return {
            "message": "Ocurrió un error. ¿Cuándo quieres el recordatorio?",
            "quick_replies": [],
            "next_step": "complete"
        }
