from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Evaluation Platform"
    app_version: str = "0.1.0"
    app_env: str = "development"
    debug: bool = True

    api_prefix: str = "/api/v1"

    dataset_root: str = "datasets"

    database_url: str | None = None

    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    evaluator_llm_base_url: str | None = None
    evaluator_llm_api_key: str | None = None
    evaluator_llm_model: str | None = None

    ata_rag_base_url: str = "http://127.0.0.1:8001"
    internship_coordinator_base_url: str = "http://127.0.0.1:8002"
    internship_coordinator_api_key: str | None = None

    cors_origins: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:8501,"
        "http://127.0.0.1:8501"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
