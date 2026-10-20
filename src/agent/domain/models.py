from enum import StrEnum
from typing import Any

Message = dict[str, Any]  # formato OpenAI: {"role": "system" | "user" | "assistant", "content": ...}


class Intent(StrEnum):
    CONSULTA_PRODUCTO = "consulta_producto"  # T2: RAG
    CONSULTA_DATOS = "consulta_datos"  # T3: tool MCP
    ACCION_SENSIBLE = "accion_sensible"  # T3: HITL
    SALUDO = "saludo"
    FUERA_DE_ALCANCE = "fuera_de_alcance"


# TODO S1: AgentReply (pydantic.BaseModel), contrato del structured output.
#   - intent: Intent y answer: str, con Field(description=...): el JSON schema se envía al modelo.
#   - extra="forbid" y answer no vacío. Ojo: el modo strict no admite todo JSON Schema.
# TODO S2: Usage (modelos, llamadas, latencia, tokens; sumable), ModelResult (reply + usage)
#          y AgentTurn (resultado de un turno: reply + usage).
