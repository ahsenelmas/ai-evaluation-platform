from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_datasets() -> None:
    response = client.get("/api/v1/datasets")

    assert response.status_code == 200

    datasets = response.json()

    assert isinstance(datasets, list)
    assert len(datasets) >= 1

    dataset_ids = [dataset["id"] for dataset in datasets]

    assert "ata-rag-golden-v1" in dataset_ids


def test_get_dataset() -> None:
    response = client.get("/api/v1/datasets/ata-rag-golden-v1")

    assert response.status_code == 200

    dataset = response.json()

    assert dataset["metadata"]["id"] == "ata-rag-golden-v1"

    assert dataset["metadata"]["system"] == "ata-rag"

    assert len(dataset["cases"]) == 3
    assert dataset["cases"][0]["id"] == "ata-rag-001"


def test_get_unknown_dataset_returns_404() -> None:
    response = client.get("/api/v1/datasets/missing-dataset")

    assert response.status_code == 404
    assert "was not found" in (response.json()["detail"])
