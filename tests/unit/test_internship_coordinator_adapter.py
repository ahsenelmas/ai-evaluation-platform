import httpx
import pytest

from app.adapters.internship_coordinator import (
    InternshipCoordinatorAdapter,
)
from app.domain.models import EvaluationCase


def create_case() -> EvaluationCase:
    return EvaluationCase(
        id="internship-001",
        system="internship-coordinator",
        input={
            "email_sender": ("student@example.test"),
            "email_subject": ("Internship Application"),
            "email_body": ("Please review my internship application."),
            "attachment_paths": [],
        },
        expected_output={"recommendation": "APPROVE"},
    )


@pytest.mark.asyncio
async def test_internship_adapter_returns_execution() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.url.path == "/cases/intake"

        return httpx.Response(
            status_code=200,
            json={
                "case_id": "CASE-001",
                "status": "RECOMMENDATION_READY",
                "student_name": "Test Student",
                "student_id": "ATA12345",
                "student_email": ("student@example.test"),
                "company_name": "Test Company",
                "supervisor_name": "Test Supervisor",
                "supervisor_email": ("supervisor@test-company.test"),
                "internship_start_date": ("2026-07-01"),
                "internship_end_date": ("2026-08-15"),
                "missing_fields": [],
                "rule_violations": [],
                "recommendation": "APPROVE",
                "recommendation_reason": ("Application is complete."),
                "next_action": ("COORDINATOR_APPROVAL"),
                "audit_log": ["Application processed"],
                "application_version": "1.0.0",
            },
        )

    adapter = InternshipCoordinatorAdapter(
        base_url="http://internship.test",
        transport=httpx.MockTransport(handler),
    )

    execution = await adapter.execute(create_case())

    assert execution.success is True
    assert execution.output["recommendation"] == "APPROVE"
    assert execution.output["extracted_fields"]["student_name"] == "Test Student"
    assert execution.application_version == "1.0.0"


@pytest.mark.asyncio
async def test_internship_adapter_handles_http_error() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=500,
            json={"detail": "Internal server error"},
        )

    adapter = InternshipCoordinatorAdapter(
        base_url="http://internship.test",
        transport=httpx.MockTransport(handler),
    )

    execution = await adapter.execute(create_case())

    assert execution.success is False
    assert execution.error is not None
    assert "500" in execution.error


@pytest.mark.asyncio
async def test_internship_adapter_validates_input() -> None:
    case = EvaluationCase(
        id="internship-002",
        system="internship-coordinator",
        input={"email_sender": ("student@example.test")},
        expected_output={},
    )

    adapter = InternshipCoordinatorAdapter(
        base_url="http://internship.test",
    )

    execution = await adapter.execute(case)

    assert execution.success is False
    assert execution.error is not None
    assert "email_subject" in execution.error
    assert "email_body" in execution.error


@pytest.mark.asyncio
async def test_internship_adapter_rejects_wrong_system() -> None:
    case = EvaluationCase(
        id="wrong-001",
        system="ata-rag",
        input={},
        expected_output={},
    )

    adapter = InternshipCoordinatorAdapter(
        base_url="http://internship.test",
    )

    with pytest.raises(
        ValueError,
        match="cannot execute",
    ):
        await adapter.execute(case)
