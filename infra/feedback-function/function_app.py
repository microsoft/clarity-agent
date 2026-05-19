"""Azure Function: feedback submission endpoint.

Receives user feedback via HTTP POST, validates it, and writes it
to Azure Blob Storage using a managed identity.  The identity has
a custom write-only RBAC role — it cannot read, list, or delete
existing blobs.

Required application settings:
    FEEDBACK_STORAGE_ACCOUNT    Storage account name (e.g. "clarityfeedback").
    FEEDBACK_CONTAINER          Blob container name (default: "feedback").

Optional application settings:
    FEEDBACK_MAX_SIZE           Max body size in bytes (default: 4MB).
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime

import azure.functions as func  # type: ignore[import-not-found]
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient  # type: ignore[import-not-found]

app = func.FunctionApp()

_MAX_SIZE: int = int(os.environ.get("FEEDBACK_MAX_SIZE", 4 << 20))
_CONTAINER: str = os.environ.get("FEEDBACK_CONTAINER", "feedback")

logger = logging.getLogger("feedback")


@app.function_name("submit_feedback")
@app.route(route="feedback", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def submit_feedback(req: func.HttpRequest) -> func.HttpResponse:
    """Accept a feedback markdown document and store it."""
    body: bytes = req.get_body()

    # --- Validate size ---
    if len(body) > _MAX_SIZE:
        return func.HttpResponse(
            f"Feedback too large ({len(body)} bytes, max {_MAX_SIZE})",
            status_code=413,
        )

    # --- Validate content ---
    try:
        text: str = body.decode("utf-8")
    except UnicodeDecodeError:
        return func.HttpResponse(
            "Invalid encoding (expected UTF-8)", status_code=400,
        )

    if not text.strip():
        return func.HttpResponse("Empty feedback", status_code=400)

    # --- Write to blob storage via managed identity ---
    account: str | None = os.environ.get("FEEDBACK_STORAGE_ACCOUNT")
    if not account:
        logger.error("FEEDBACK_STORAGE_ACCOUNT not configured")
        return func.HttpResponse("Server misconfigured", status_code=500)

    timestamp: str = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    short_id: str = uuid.uuid4().hex[:8]
    blob_name: str = f"feedback-{timestamp}-{short_id}.md"

    try:
        account_url = f"https://{account}.blob.core.windows.net"
        credential = DefaultAzureCredential()
        service = BlobServiceClient(account_url, credential=credential)
        client = service.get_blob_client(_CONTAINER, blob_name)
        client.upload_blob(text.encode("utf-8"), overwrite=False)
    except Exception:
        logger.exception("Failed to write feedback blob")
        return func.HttpResponse("Storage error", status_code=502)

    logger.info("Feedback saved: %s (%d bytes)", blob_name, len(body))
    return func.HttpResponse(status_code=201)
