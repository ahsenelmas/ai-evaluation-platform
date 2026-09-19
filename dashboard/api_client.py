"""Small HTTP client for the evaluation platform API."""

from typing import Any

import httpx


class APIError(Exception):
    """A request to the evaluation API failed."""


class EvaluationAPI:
    def __init__(
        self,
        base_url: str,
        timeout: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = client.request(method, path, params=params, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as error:
            try:
                detail = error.response.json().get("detail", error.response.text)
            except ValueError:
                detail = error.response.text
            raise APIError(
                f"API returned HTTP {error.response.status_code}: {detail}"
            ) from error
        except (httpx.RequestError, ValueError) as error:
            raise APIError(f"Cannot reach the evaluation API: {error}") from error

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/health")

    def langfuse_status(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/integrations/langfuse/status")

    def datasets(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/datasets")

    def dataset(self, dataset_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/datasets/{dataset_id}")

    def experiments(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/experiments")

    def experiment(self, experiment_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/experiments/{experiment_id}")

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/v1/experiments/run", payload=payload)

    def compare(
        self,
        baseline_id: str,
        candidate_id: str,
        *,
        score_tolerance: float = 0.0,
        max_latency_increase_percent: float = 20.0,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/experiments/compare",
            params={
                "baseline_id": baseline_id,
                "candidate_id": candidate_id,
                "score_tolerance": score_tolerance,
                "max_latency_increase_percent": max_latency_increase_percent,
            },
        )
