import time
from typing import Any

import httpx

from app.adapters.base import ApplicationAdapter
from app.domain.models import (
    ApplicationExecution,
    EvaluationCase,
    TokenUsage,
)


class AtaRagAdapter(ApplicationAdapter):
    system = "ata-rag"

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def execute(
        self,
        case: EvaluationCase,
    ) -> ApplicationExecution:
        self.validate_case(case)

        question = case.input.get("question")

        if not isinstance(question, str) or not question.strip():
            return self._failed_execution(
                case=case,
                error=("ATA RAG evaluation case requires a non-empty 'question'."),
            )

        payload: dict[str, Any] = {
            "question": question.strip(),
            "retrieval_limit": case.input.get(
                "retrieval_limit",
                5,
            ),
        }

        language = case.input.get("language")

        if language is not None:
            payload["language"] = language

        started_at = time.perf_counter()

        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    "/api/chat",
                    json=payload,
                )

                response.raise_for_status()
                data = response.json()

            latency_ms = int((time.perf_counter() - started_at) * 1000)

            if not isinstance(data, dict):
                raise ValueError("ATA RAG returned a non-object response.")

            answer = data.get("answer")

            if not isinstance(answer, str):
                raise ValueError("ATA RAG response does not contain a valid 'answer'.")

            raw_sources = data.get("sources", [])

            sources = raw_sources if isinstance(raw_sources, list) else []

            token_usage = self._parse_token_usage(data.get("token_usage"))

            return ApplicationExecution(
                case_id=case.id,
                system=self.system,
                output={
                    "answer": answer,
                    "language": data.get("language"),
                    "grounded": data.get("grounded"),
                    "sources": sources,
                    "message_id": data.get("message_id"),
                    "session_id": data.get("session_id"),
                },
                retrieved_context=[
                    source for source in sources if isinstance(source, dict)
                ],
                success=True,
                latency_ms=latency_ms,
                token_usage=token_usage,
                estimated_cost=float(
                    data.get(
                        "estimated_cost",
                        0.0,
                    )
                ),
                model=data.get("model"),
                prompt_version=data.get("prompt_version"),
                application_version=data.get("application_version"),
                metadata={
                    "adapter": "AtaRagAdapter",
                    "endpoint": "/api/chat",
                },
            )

        except httpx.HTTPStatusError as error:
            latency_ms = int((time.perf_counter() - started_at) * 1000)

            return self._failed_execution(
                case=case,
                error=(f"ATA RAG returned HTTP {error.response.status_code}."),
                latency_ms=latency_ms,
            )

        except (
            httpx.HTTPError,
            ValueError,
            TypeError,
        ) as error:
            latency_ms = int((time.perf_counter() - started_at) * 1000)

            return self._failed_execution(
                case=case,
                error=str(error),
                latency_ms=latency_ms,
            )

    def _failed_execution(
        self,
        case: EvaluationCase,
        error: str,
        latency_ms: int = 0,
    ) -> ApplicationExecution:
        return ApplicationExecution(
            case_id=case.id,
            system=self.system,
            output={},
            success=False,
            error=error,
            latency_ms=latency_ms,
            metadata={
                "adapter": "AtaRagAdapter",
                "endpoint": "/api/chat",
            },
        )

    @staticmethod
    def _parse_token_usage(
        raw_usage: Any,
    ) -> TokenUsage:
        if not isinstance(raw_usage, dict):
            return TokenUsage()

        input_tokens = int(raw_usage.get("input_tokens", 0))

        output_tokens = int(raw_usage.get("output_tokens", 0))

        total_tokens = int(
            raw_usage.get(
                "total_tokens",
                input_tokens + output_tokens,
            )
        )

        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
