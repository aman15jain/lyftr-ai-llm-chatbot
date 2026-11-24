"""Pydantic request/response models."""
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

SessionId = Annotated[str, StringConstraints(min_length=1, max_length=128)]
Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class ChatRequest(BaseModel):
    session_id: SessionId
    message: Message
    system_prompt: str | None = Field(default=None, max_length=4000)

    @field_validator("system_prompt")
    @classmethod
    def _blank_prompt_is_none(cls, v: str | None) -> str | None:
        return v.strip() or None if v is not None else None


class ChatMetadata(BaseModel):
    resolution_source: Literal["LIVE_INFERENCE", "LLM_CACHE"]
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    key_id: str | None
    fallback_attempts: int


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    metadata: ChatMetadata
