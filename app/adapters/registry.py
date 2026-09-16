from app.adapters.ata_rag import AtaRagAdapter
from app.adapters.base import ApplicationAdapter
from app.adapters.internship_coordinator import (
    InternshipCoordinatorAdapter,
)
from app.core.config import Settings, get_settings


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[
            str,
            ApplicationAdapter,
        ] = {}

    def register(
        self,
        adapter: ApplicationAdapter,
    ) -> None:
        system = adapter.system.strip().lower()

        if not system:
            raise ValueError("Adapter system cannot be empty.")

        if system in self._adapters:
            raise ValueError(f"Adapter for system '{system}' is already registered.")

        self._adapters[system] = adapter

    def get(
        self,
        system: str,
    ) -> ApplicationAdapter:
        normalized_system = system.strip().lower()

        adapter = self._adapters.get(normalized_system)

        if adapter is None:
            available = ", ".join(self.available())

            raise ValueError(
                f"Unknown AI system '{system}'. Available systems: {available}"
            )

        return adapter

    def available(self) -> list[str]:
        return sorted(self._adapters)


def build_default_adapter_registry(
    settings: Settings | None = None,
) -> AdapterRegistry:
    resolved_settings = settings or get_settings()

    registry = AdapterRegistry()

    registry.register(
        AtaRagAdapter(
            base_url=(resolved_settings.ata_rag_base_url),
        )
    )

    registry.register(
        InternshipCoordinatorAdapter(
            base_url=(resolved_settings.internship_coordinator_base_url),
            api_key=(resolved_settings.internship_coordinator_api_key),
        )
    )

    return registry
