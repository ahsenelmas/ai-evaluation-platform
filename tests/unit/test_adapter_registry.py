import pytest

from app.adapters.ata_rag import AtaRagAdapter
from app.adapters.registry import AdapterRegistry


def test_registry_returns_registered_adapter() -> None:
    registry = AdapterRegistry()

    adapter = AtaRagAdapter(
        base_url="http://ata-rag.test"
    )

    registry.register(adapter)

    assert registry.get("ata-rag") is adapter
    assert registry.available() == ["ata-rag"]


def test_registry_rejects_duplicate_system() -> None:
    registry = AdapterRegistry()

    registry.register(
        AtaRagAdapter(
            base_url="http://ata-rag.test"
        )
    )

    with pytest.raises(
        ValueError,
        match="already registered",
    ):
        registry.register(
            AtaRagAdapter(
                base_url="http://another.test"
            )
        )


def test_registry_rejects_unknown_system() -> None:
    registry = AdapterRegistry()

    registry.register(
        AtaRagAdapter(
            base_url="http://ata-rag.test"
        )
    )

    with pytest.raises(
        ValueError,
        match="Unknown AI system",
    ):
        registry.get("unknown-system")
