from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from tests.conftest import run_lint


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    (tmp_path / "main.py").write_text(
        textwrap.dedent("""\
        from dataclasses import dataclass
        
        @dataclass
        class Point:
            x: int
            
        def get_data() -> dict[str, str]:
            return {"x": "1"}
    """)
    )
    return tmp_path


def test_no_filter(temp_project: Path) -> None:
    result = run_lint(temp_project, ".")
    assert "ML200" in result.stdout
    assert "ML102" in result.stdout


def test_prefix_matching(temp_project: Path) -> None:
    # 'ML' prefix should select everything starting with ML
    result = run_lint(temp_project, ".", "--select", "ML")
    assert "ML200" in result.stdout
    assert "ML102" in result.stdout


def test_select_specific(temp_project: Path) -> None:
    result = run_lint(temp_project, ".", "--select", "ML200")
    assert "ML200" in result.stdout
    assert "ML102" not in result.stdout


def test_ignore_wins_over_select(temp_project: Path) -> None:
    # Even if ML is selected, ignoring ML200 should hide it
    result = run_lint(temp_project, ".", "--select", "ML", "--ignore", "ML200")
    assert "ML200" not in result.stdout
    assert "ML102" in result.stdout


def test_extend_select(temp_project: Path) -> None:
    # Select something non-existent, then extend-select ML200
    result = run_lint(temp_project, ".", "--select", "NONE", "--extend-select", "ML200")
    assert "ML200" in result.stdout
    assert "ML102" not in result.stdout


def test_extend_ignore(temp_project: Path) -> None:
    # Select all, ignore ML102 via --ignore, and ML200 via --extend-ignore
    result = run_lint(temp_project, ".", "--select", "ML", "--ignore", "ML102", "--extend-ignore", "ML200")
    assert "ML102" not in result.stdout
    assert "ML200" not in result.stdout


def test_config_override(temp_project: Path) -> None:
    # Create a config with select=['ML102']
    (temp_project / "pyproject.toml").write_text(
        textwrap.dedent("""\
        [tool.python-lint-hooks]
        select = ["ML102"]
    """)
    )

    # Running without flags should only show ML102
    result = run_lint(temp_project, ".")
    assert "ML102" in result.stdout
    assert "ML200" not in result.stdout

    # CLI --select should OVERRIDE config select
    result_cli = run_lint(temp_project, ".", "--select", "ML200")
    assert "ML200" in result_cli.stdout
    assert "ML102" not in result_cli.stdout


def test_select_comma_separated(temp_project: Path) -> None:
    result = run_lint(temp_project, ".", "--select", "ML200,ML102")
    assert "ML200" in result.stdout
    assert "ML102" in result.stdout


def test_select_repeated_flag(temp_project: Path) -> None:
    result = run_lint(temp_project, ".", "--select", "ML200", "--select", "ML102")
    assert "ML200" in result.stdout
    assert "ML102" in result.stdout


def test_path_after_select_flag_is_not_swallowed(tmp_path: Path) -> None:
    # Regression test: --select used nargs="+" for its values, which greedily consumed
    # a following positional path argument, silently falling back to scanning "." (i.e.
    # every subdirectory) instead of just the one explicitly named. "a" and "b" each
    # contain a distinct violation; passing only "b" after --select must exclude "a"'s.
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "mod.py").write_text("def f():\n    class FromA: pass\n")
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "mod.py").write_text("def f():\n    class FromB: pass\n")

    result = run_lint(tmp_path, "--select", "ML300", "b")
    assert "FromB" in result.stdout
    assert "FromA" not in result.stdout


def test_config_extend_select(temp_project: Path) -> None:
    (temp_project / "pyproject.toml").write_text(
        textwrap.dedent("""\
        [tool.python-lint-hooks]
        select = ["ML102"]
        extend-select = ["ML200"]
    """)
    )

    # Should show both
    result = run_lint(temp_project, ".")
    assert "ML102" in result.stdout
    assert "ML200" in result.stdout

    # CLI --select should override config select, but config extend-select still applies
    result_cli = run_lint(temp_project, ".", "--select", "NONE")
    assert "ML102" not in result_cli.stdout
    assert "ML200" in result_cli.stdout


def test_lint_outside_cwd_uses_target_repo_pyproject_config(tmp_path: Path) -> None:
    # Issue #32 regression test:
    # When ml-lints is run against a path outside CWD (e.g. ../sibling_repo),
    # configuration in pyproject.toml should be loaded from the target repository's pyproject.toml
    # unless --config is explicitly overridden on CLI.
    invoking_dir = tmp_path / "invoking_repo"
    invoking_dir.mkdir()
    (invoking_dir / "pyproject.toml").write_text(
        textwrap.dedent("""\
        [tool.python-lint-hooks]
        select = ["ML100"]
    """)
    )

    sibling_dir = tmp_path / "sibling_repo"
    sibling_dir.mkdir()
    (sibling_dir / "pyproject.toml").write_text(
        textwrap.dedent("""\
        [tool.python-lint-hooks]
        select = ["ML300"]
    """)
    )
    (sibling_dir / "main.py").write_text("def f():\n    class TargetViolation: pass\n")

    # Without explicit --config, target repo's pyproject.toml (selecting ML300) should be loaded
    result = run_lint(invoking_dir, "../sibling_repo")
    assert "TargetViolation" in result.stdout

    # With explicit --config pointing to invoking repo's config, invoking repo's config (selecting ML100) is used
    result_explicit = run_lint(
        invoking_dir,
        "--config",
        str(invoking_dir / "pyproject.toml"),
        "../sibling_repo",
    )
    assert "TargetViolation" not in result_explicit.stdout
