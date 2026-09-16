from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.datasets import router as datasets_router
from app.api.routes.evaluations import router as evaluations_router
from app.api.routes.experiments import (
    router as experiments_router,
)
from app.api.routes.health import router as health_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Reusable evaluation, observability and regression-testing "
        "platform for AI-powered applications."
    ),
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type"],
)

app.include_router(
    health_router,
    prefix=settings.api_prefix,
)

app.include_router(
    evaluations_router,
    prefix=settings.api_prefix,
)

app.include_router(
    datasets_router,
    prefix=settings.api_prefix,
)

app.include_router(
    experiments_router,
    prefix=settings.api_prefix,
)


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "message": "AI Evaluation Platform API is running.",
        "documentation": "/docs",
    }
