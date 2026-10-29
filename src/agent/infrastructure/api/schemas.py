"""Contrato HTTP del agente. Solo crece con campos opcionales."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, StringConstraints

from agent.domain.models import Intent

UserMessage = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class ChatRequest(BaseModel):
    session_id: UUID | None = None
    message: UserMessage


class ChatResponse(BaseModel):
    session_id: UUID
    intent: Intent
    answer: str
