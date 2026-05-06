from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest


def run_lint(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["uv", "run", "ml-lint", *args],  # noqa: S607
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    (tmp_path / "main.py").write_text(
        textwrap.dedent("""\
        from dataclasses import dataclass
        
        @dataclass
        class Point:
            x: int
            
        def get_data() -> dict:
            return {"x": 1}
    """)
    )
    return tmp_path


def test_no_filter(temp_project: Path) -> None:
    result = run_lint(temp_project, ".")
    assert "ML005" in result.stdout
    assert "ML001" in result.stdout


def test_prefix_matching(temp_project: Path) -> None:
    # 'ML' prefix should select everything starting with ML
    result = run_lint(temp_project, ".", "--select", "ML")
    assert "ML005" in result.stdout
    assert "ML001" in result.stdout


def test_select_specific(temp_project: Path) -> None:
    result = run_lint(temp_project, ".", "--select", "ML005")
    assert "ML005" in result.stdout
    assert "ML001" not in result.stdout


def test_ignore_wins_over_select(temp_project: Path) -> None:
    # Even if ML is selected, ignoring ML005 should hide it
    result = run_lint(temp_project, ".", "--select", "ML", "--ignore", "ML005")
    assert "ML005" not in result.stdout
    assert "ML001" in result.stdout


def test_extend_select(temp_project: Path) -> None:
    # Select something non-existent, then extend-select ML005
    result = run_lint(temp_project, ".", "--select", "NONE", "--extend-select", "ML005")
    assert "ML005" in result.stdout
    assert "ML001" not in result.stdout


def test_extend_ignore(temp_project: Path) -> None:
    # Select all, ignore ML001 via --ignore, and ML005 via --extend-ignore
    result = run_lint(temp_project, ".", "--select", "ML", "--ignore", "ML001", "--extend-ignore", "ML005")
    assert "ML001" not in result.stdout
    assert "ML005" not in result.stdout


def test_config_override(temp_project: Path) -> None:
    # Create a config with select=['ML001']
    (temp_project / "pyproject.toml").write_text(
        textwrap.dedent("""\
        [tool.python-lint-hooks]
        select = ["ML001"]
    """)
    )

    # Running without flags should only show ML001
    result = run_lint(temp_project, ".")
    assert "ML001" in result.stdout
    assert "ML005" not in result.stdout

    # CLI --select should OVERRIDE config select
    result_cli = run_lint(temp_project, ".", "--select", "ML005")
    assert "ML005" in result_cli.stdout
    assert "ML001" not in result_cli.stdout


def test_config_extend_select(temp_project: Path) -> None:
    (temp_project / "pyproject.toml").write_text(
        textwrap.dedent("""\
        [tool.python-lint-hooks]
        select = ["ML001"]
        extend-select = ["ML005"]
    """)
    )

    # Should show both
    result = run_lint(temp_project, ".")
    assert "ML001" in result.stdout
    assert "ML005" in result.stdout

    # CLI --select should override config select, but config extend-select still applies
    result_cli = run_lint(temp_project, ".", "--select", "NONE")
    assert "ML001" not in result_cli.stdout
    assert "ML005" in result_cli.stdout
