from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from openai import OpenAI
from sqlalchemy.engine import Engine

from src.config import OPENAI_API_KEY, OPENAI_MODEL, MAX_TOOL_ROUNDS
from src.risk_engine import list_projects, get_risk_summary, get_project_overview

SYSTEM_PROMPT = """Eres un asistente de gestión de proyectos. Responde en español, de forma clara y ejecutiva.
Usa las herramientas para verificar datos antes de afirmar el estado de un proyecto.
Distingue hechos observados de hipótesis. No inventes fechas, porcentajes ni responsables.
Al analizar riesgos, explica: hallazgo, evidencia, impacto probable y siguiente acción sugerida.
No declares causalidad si los datos solo muestran correlación. Si faltan datos, dilo explícitamente.
Solo puedes consultar información usando las herramientas disponibles. No pidas ni reveles credenciales.
Las herramientas son de solo lectura; nunca afirmes haber modificado la base de datos."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "listar_proyectos",
            "description": "Obtiene el listado resumido de proyectos desde PostgreSQL.",
            "parameters": {
                "type": "object",
                "properties": {"limite": {"type": "integer", "minimum": 1, "maximum": 100}},
                "required": [],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "resumen_riesgos",
            "description": "Calcula indicadores globales y devuelve tareas atrasadas o sin actualización reciente.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "resumen_avance",
            "description": "Obtiene el avance, estado y riesgo calculado para cada proyecto.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False}
        }
    },
]

def _json_default(value: Any):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "item"):
        return value.item()
    return str(value)

class ProjectAgent:
    def __init__(self, engine: Engine):
        if not OPENAI_API_KEY:
            raise RuntimeError("Falta configurar OPENAI_API_KEY en .env.")
        self.engine = engine
        self.client = OpenAI(api_key=OPENAI_API_KEY, timeout=45.0, max_retries=2)

    def _dispatch(self, name: str, arguments: dict) -> dict:
        if name == "listar_proyectos":
            limit = arguments.get("limite", 50)
            if not isinstance(limit, int) or not 1 <= limit <= 100:
                raise ValueError("El límite debe estar entre 1 y 100.")
            return {"proyectos": list_projects(self.engine, limit=limit)}
        if name == "resumen_riesgos":
            return get_risk_summary(self.engine)
        if name == "resumen_avance":
            df = get_project_overview(self.engine)
            return {"proyectos": df.where(df.notna(), None).to_dict(orient="records")}
        raise ValueError("Herramienta no autorizada.")

    def ask(self, messages: list[dict[str, str]]) -> str:
        # Solo se reenvía un historial acotado de mensajes de usuario/asistente.
        clean_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in messages[-10:]:
            if msg.get("role") in {"user", "assistant"} and isinstance(msg.get("content"), str):
                clean_messages.append({"role": msg["role"], "content": msg["content"][:6000]})

        for _ in range(MAX_TOOL_ROUNDS):
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=clean_messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.2,
            )
            message = response.choices[0].message
            if not message.tool_calls:
                return message.content or "No se generó una respuesta. Intenta reformular la pregunta."

            clean_messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                    } for tc in message.tool_calls
                ]
            })
            for tool_call in message.tool_calls:
                try:
                    args = json.loads(tool_call.function.arguments or "{}")
                    result = self._dispatch(tool_call.function.name, args)
                    payload = json.dumps(result, ensure_ascii=False, default=_json_default)
                except Exception:
                    payload = json.dumps({"error": "No se pudo ejecutar la herramienta solicitada."}, ensure_ascii=False)
                clean_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": payload[:30000]
                })
        return "El análisis alcanzó el límite de pasos. Prueba una pregunta más específica."
