import pytest
from fastapi.testclient import TestClient

from app.api.routes.experiments import (
    get_langfuse_publisher,
)
from app.main import app


class ConnectedPublisher:
    enabled = True

    def check_connection(self) -> bool:
        return True


class DisabledPublisher:
    enabled = False

    def check_connection(self) -> bool:
        return False


client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


def test_langfuse_status_returns_connected():
    app.dependency_overrides[get_langfuse_publisher] = lambda: ConnectedPublisher()

    response = client.get("/api/v1/integrations/langfuse/status")

    assert response.status_code == 200

    assert response.json() == {
        "configured": True,
        "connected": True,
        "host": "https://cloud.langfuse.com",
        "message": ("Langfuse is configured and connected."),
    }


def test_langfuse_status_returns_not_configured():
    app.dependency_overrides[get_langfuse_publisher] = lambda: DisabledPublisher()

    response = client.get("/api/v1/integrations/langfuse/status")

    assert response.status_code == 200

    body = response.json()

    assert body["configured"] is False
    assert body["connected"] is False
    assert body["message"] == ("Langfuse credentials are not configured.")
