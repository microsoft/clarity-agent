"""Pydantic models for web API request and response validation."""

from __future__ import annotations

from pydantic import BaseModel


class PacketRequest(BaseModel):
    """Request body for POST /api/packet/generate."""

    sections: list[str] | None = None
    format: str = "markdown"
    view: str | None = None


class ModelOverrideRequest(BaseModel):
    """Request body for PUT /api/model-profile/override.

    ``tier`` is a tier name (``"default"``, ``"deep"``, ``"fast"``),
    ``"auto"`` to clear the override and return to profile-driven
    selection, or a direct model string.
    """

    tier: str


class FeedbackRequest(BaseModel):
    """Request body for POST /api/feedback."""

    message: str
    contact_ok: bool = False
    contact_email: str = ""
    include_llm_info: bool = True
    transcript_turns: int = 0
    include_protocol: bool = False
