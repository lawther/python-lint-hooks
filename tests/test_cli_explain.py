from __future__ import annotations

from pathlib import Path

from tests.conftest import LintResult, run_lint


def run_explain(cwd: Path, code: str) -> LintResult:
    return run_lint(cwd, "--explain", code)


def test_explain_valid_code(tmp_path: Path) -> None:
    result = run_explain(tmp_path, "ML100")
    assert result.returncode == 0
    assert "ML100: Function returns a bare `dict`" in result.stdout
    assert "Rationale:" in result.stdout
    assert "Bad Example:" in result.stdout
    assert "Good Example:" in result.stdout


def test_explain_case_insensitive(tmp_path: Path) -> None:
    result = run_explain(tmp_path, "ml100")
    assert result.returncode == 0
    assert "ML100: Function returns a bare `dict`" in result.stdout


def test_explain_invalid_code(tmp_path: Path) -> None:
    result = run_explain(tmp_path, "NONEXISTENT")
    assert result.returncode == 1
    assert "Error: Unknown rule code 'NONEXISTENT'" in result.stderr


def test_explain_tip_is_shown(tmp_path: Path) -> None:
    # Create a file with a violation
    (tmp_path / "test.py").write_text("def f() -> dict: return {}")

    result = run_lint(tmp_path, "test.py")

    assert "💡 Tip: For more information and examples, run 'ml-lints --explain ML100'" in result.stdout
