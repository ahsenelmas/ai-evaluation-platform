import pytest

from app.domain.models import ApplicationExecution, EvaluationCase
from app.evaluators.registry import build_default_registry


def make_case(expected: dict) -> EvaluationCase:
    return EvaluationCase(
        id="internship-app-001",
        system="internship-coordinator",
        expected_output=expected,
    )


def make_execution(actual: dict) -> ApplicationExecution:
    return ApplicationExecution(
        case_id="internship-app-001",
        system="internship-coordinator",
        output=actual,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("expected", "actual", "passed"),
    [
        (True, True, True),
        (False, False, True),
        (True, False, False),
        (False, None, False),
        (False, "false", False),
    ],
)
async def test_security_flag_requires_equal_booleans(expected, actual, passed):
    evaluator = build_default_registry().create("security_flag_match", {})
    result = await evaluator.evaluate(
        make_case({"security_flag": expected}),
        make_execution({"security_flag": actual}),
    )
    assert result.passed is passed
    assert result.score == float(passed)


@pytest.mark.asyncio
async def test_security_flag_missing_label_fails():
    evaluator = build_default_registry().create("security_flag_match", {})
    result = await evaluator.evaluate(
        make_case({}), make_execution({"security_flag": False})
    )
    assert result.passed is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("expected", "actual", "passed"),
    [
        ([], [], True),
        (["student_id", "company_name"], ["company_name", "student_id"], True),
        (["student_id"], [], False),
        ([], ["student_id"], False),
        (["student_id"], None, False),
        (None, [], False),
        ([], [None], False),
        (["student_id", "student_id"], ["student_id"], False),
    ],
)
async def test_missing_fields_match_checks_labels_without_order(
    expected, actual, passed
):
    evaluator = build_default_registry().create("missing_fields_match", {})
    result = await evaluator.evaluate(
        make_case({"missing_fields": expected}),
        make_execution({"missing_fields": actual}),
    )
    assert result.passed is passed
    assert result.score == float(passed)


def test_internship_evaluators_reject_unrecognized_settings():
    registry = build_default_registry()
    for name in ("security_flag_match", "missing_fields_match"):
        with pytest.raises(ValueError, match="does not accept settings"):
            registry.create(name, {"ignored": True})
