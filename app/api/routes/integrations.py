from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.routes.experiments import (
    get_langfuse_publisher,
)
from app.api.schemas.integrations import (
    LangfuseStatusResponse,
)
from app.core.config import get_settings
from app.integrations.langfuse_client import (
    LangfuseExperimentPublisher,
)

router = APIRouter(
    prefix="/integrations",
    tags=["integrations"],
)


@router.get(
    "/langfuse/status",
    response_model=LangfuseStatusResponse,
)
def get_langfuse_status(
    publisher: Annotated[
        LangfuseExperimentPublisher,
        Depends(get_langfuse_publisher),
    ],
) -> LangfuseStatusResponse:
    settings = get_settings()

    configured = publisher.enabled
    connected = publisher.check_connection()

    if connected:
        message = "Langfuse is configured and connected."

    elif configured:
        message = "Langfuse is configured but the connection check failed."

    else:
        message = "Langfuse credentials are not configured."

    return LangfuseStatusResponse(
        configured=configured,
        connected=connected,
        host=settings.langfuse_host,
        message=message,
    )
