from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(
    prefix="/health",
    tags=["health"],
)


@router.get("")
async def health_check() -> dict[str, str]:
    settings = get_settings()

    return {
        "status": "healthy",
        "service": settings.app_name,
        "environment": settings.app_env,
        "version": settings.app_version,
    }
