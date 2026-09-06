"""Pydantic models for web API request and response validation."""

from __future__ import annotations

from pydantic import BaseModel


class PacketRequest(BaseModel):
    """Request body for POST /api/packet/generate."""

    sections: list[str] | None = None
    format: str = "markdown"
    view: str | None = None


class SetModelRequest(BaseModel):
    """Request body for PUT /api/model.

    ``model`` is a provider model identifier, as listed by
    ``GET /api/models``.  Free-form providers (Azure) accept any
    deployment name.
    """

    model: str


class FeedbackRequest(BaseModel):
    """Request body for POST /api/feedback."""

    message: str
    contact_ok: bool = False
    contact_email: str = ""
    include_llm_info: bool = True
    transcript_turns: int = 0
    include_protocol: bool = False
