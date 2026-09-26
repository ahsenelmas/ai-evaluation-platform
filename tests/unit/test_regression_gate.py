from pathlib import Path

from scripts.check_regression import run_gate

FIXTURES = Path(__file__).parents[1] / "fixtures" / "regression"


def test_regression_gate_accepts_healthy_candidate(capsys):
    exit_code = run_gate(
        FIXTURES / "baseline.json",
        FIXTURES / "candidate.json",
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "RESULT: PASS" in output
    assert "ci-candidate-v2" in output


def test_regression_gate_rejects_regressed_candidate(capsys):
    exit_code = run_gate(
        FIXTURES / "baseline.json",
        FIXTURES / "regressed_candidate.json",
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "RESULT: FAIL" in output
    assert "Regression reasons:" in output
    assert "Candidate pass rate decreased" in output
    assert "Average latency increased" in output


def test_regression_gate_reports_invalid_input(tmp_path, capsys):
    invalid_report = tmp_path / "invalid.json"
    invalid_report.write_text("{}", encoding="utf-8")

    exit_code = run_gate(
        FIXTURES / "baseline.json",
        invalid_report,
    )

    output = capsys.readouterr().out
    assert exit_code == 2
    assert "REGRESSION GATE ERROR:" in output
