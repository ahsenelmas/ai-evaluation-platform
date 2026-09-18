import time
from pathlib import Path
from typing import Any

import httpx

from app.adapters.base import ApplicationAdapter
from app.domain.models import (
    ApplicationExecution,
    EvaluationCase,
)


class InternshipCoordinatorAdapter(ApplicationAdapter):
    system = "internship-coordinator"

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 60.0,
        api_key: str | None = None,
        attachment_root: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key
        self.transport = transport

        self.attachment_root = (
            Path(attachment_root).expanduser().resolve()
            if attachment_root
            else None
        )

    async def execute(
        self,
        case: EvaluationCase,
    ) -> ApplicationExecution:
        self.validate_case(case)

        validation_error = self._validate_input(case.input)

        if validation_error:
            return self._failed_execution(
                case=case,
                error=validation_error,
            )

        try:
            attachment_paths = (
                self._resolve_attachment_paths(
                    case.input.get(
                        "attachment_paths",
                        [],
                    )
                )
            )
        except ValueError as error:
            return self._failed_execution(
                case=case,
                error=str(error),
            )

        payload = {
            "email_sender": case.input["email_sender"],
            "email_subject": case.input["email_subject"],
            "email_body": case.input["email_body"],
            "attachment_paths": attachment_paths,
        }

        headers: dict[str, str] = {}

        if self.api_key:
            headers["x-api-key"] = self.api_key

        started_at = time.perf_counter()

        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    "/cases/intake",
                    json=payload,
                    headers=headers,
                )

                response.raise_for_status()
                data = response.json()

            latency_ms = int(
                (time.perf_counter() - started_at) * 1000
            )

            if not isinstance(data, dict):
                raise ValueError(
                    "Internship Coordinator returned "
                    "a non-object response."
                )

            extracted_fields = {
                "student_name": data.get("student_name"),
                "student_id": data.get("student_id"),
                "student_email": data.get("student_email"),
                "company_name": data.get("company_name"),
                "supervisor_name": data.get(
                    "supervisor_name"
                ),
                "supervisor_email": data.get(
                    "supervisor_email"
                ),
                "internship_start_date": data.get(
                    "internship_start_date"
                ),
                "internship_end_date": data.get(
                    "internship_end_date"
                ),
            }

            return ApplicationExecution(
                case_id=case.id,
                system=self.system,
                output={
                    "case_id": data.get("case_id"),
                    "status": data.get("status"),
                    "extracted_fields": extracted_fields,
                    "missing_fields": data.get(
                        "missing_fields",
                        [],
                    ),
                    "rule_violations": data.get(
                        "rule_violations",
                        [],
                    ),
                    "security_flag": data.get(
                        "security_flag"
                    ),
                    "clarification_needed": data.get(
                        "clarification_needed"
                    ),
                    "recommendation": data.get(
                        "recommendation"
                    ),
                    "recommendation_reason": data.get(
                        "recommendation_reason"
                    ),
                    "next_action": data.get("next_action"),
                    "audit_log": data.get(
                        "audit_log",
                        [],
                    ),
                },
                success=True,
                latency_ms=latency_ms,
                model=data.get("model"),
                prompt_version=data.get("prompt_version"),
                application_version=data.get(
                    "application_version"
                ),
                metadata={
                    "adapter": (
                        "InternshipCoordinatorAdapter"
                    ),
                    "endpoint": "/cases/intake",
                },
            )

        except httpx.HTTPStatusError as error:
            latency_ms = int(
                (time.perf_counter() - started_at) * 1000
            )

            return self._failed_execution(
                case=case,
                error=(
                    "Internship Coordinator returned "
                    f"HTTP {error.response.status_code}."
                ),
                latency_ms=latency_ms,
            )

        except (
            httpx.HTTPError,
            ValueError,
            TypeError,
        ) as error:
            latency_ms = int(
                (time.perf_counter() - started_at) * 1000
            )

            return self._failed_execution(
                case=case,
                error=str(error),
                latency_ms=latency_ms,
            )

    def _resolve_attachment_paths(
        self,
        attachment_paths: list[str],
    ) -> list[str]:
        if self.attachment_root is None:
            return attachment_paths

        resolved_paths: list[str] = []

        for raw_path in attachment_paths:
            path = Path(raw_path)

            candidate = (
                path
                if path.is_absolute()
                else self.attachment_root / path
            )

            resolved_path = candidate.resolve()

            try:
                resolved_path.relative_to(
                    self.attachment_root
                )
            except ValueError as error:
                raise ValueError(
                    "Attachment path must stay within "
                    "INTERNSHIP_COORDINATOR_ATTACHMENT_ROOT."
                ) from error

            resolved_paths.append(str(resolved_path))

        return resolved_paths

    @staticmethod
    def _validate_input(
        case_input: dict[str, Any],
    ) -> str | None:
        required_string_fields = [
            "email_sender",
            "email_subject",
            "email_body",
        ]

        invalid_fields = [
            field
            for field in required_string_fields
            if not isinstance(
                case_input.get(field),
                str,
            )
        ]

        if invalid_fields:
            return (
                "Internship evaluation case requires "
                "string fields: "
                + ", ".join(invalid_fields)
            )

        attachment_paths = case_input.get(
            "attachment_paths",
            [],
        )

        if not isinstance(attachment_paths, list):
            return "'attachment_paths' must be a list."

        if not all(
            isinstance(path, str)
            for path in attachment_paths
        ):
            return (
                "Every attachment path must be a string."
            )

        return None

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
                "adapter": (
                    "InternshipCoordinatorAdapter"
                ),
                "endpoint": "/cases/intake",
            },
        )
