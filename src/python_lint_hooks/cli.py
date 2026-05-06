"""CLI entry point for ml-lint."""

from __future__ import annotations

import argparse
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from python_lint_hooks.checker import Violation, check_file


class _HooksConfig(BaseModel):
    exclude: list[str] = []


@dataclass(frozen=True)
class _RunConfig:
    paths: list[Path]
    exclude: list[str]

    @classmethod
    def from_args(cls, args: argparse.Namespace, hooks_config: _HooksConfig) -> _RunConfig:
        return cls(
            paths=[Path(p) for p in args.paths],
            exclude=hooks_config.exclude,
        )


def _load_hooks_config(config_path: Path) -> _HooksConfig:
    if not config_path.exists():
        return _HooksConfig()
    with config_path.open("rb") as f:
        data = tomllib.load(f)
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return _HooksConfig()
    hooks_raw = tool.get("python-lint-hooks")
    if not isinstance(hooks_raw, dict):
        return _HooksConfig()
    return _HooksConfig.model_validate(hooks_raw)


def _is_excluded(path: Path, excludes: list[str], root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    for exclude in excludes:
        exclude_path = Path(exclude.rstrip("/"))
        try:
            rel.relative_to(exclude_path)
            return True
        except ValueError:
            pass
    return False


def _collect_files(paths: list[Path], excludes: list[str], root: Path) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix == ".py":
            if not _is_excluded(path, excludes, root):
                files.append(path)
        elif path.is_dir():
            for py_file in sorted(path.rglob("*.py")):
                if not _is_excluded(py_file, excludes, root):
                    files.append(py_file)
    return files


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ml-lint",
        description="Check Python files for bare dict/tuple returns and classes defined inside functions.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Files or directories to check (default: current directory)",
    )
    parser.add_argument(
        "--config",
        default="pyproject.toml",
        help="Path to config file (default: pyproject.toml)",
    )
    args = parser.parse_args()

    hooks_config = _load_hooks_config(Path(args.config))
    run_config = _RunConfig.from_args(args, hooks_config)
    root = Path.cwd()

    files = _collect_files(run_config.paths, run_config.exclude, root)

    all_violations: list[Violation] = []
    for file in files:
        all_violations.extend(check_file(file))

    for violation in sorted(all_violations, key=lambda v: (str(v.path), v.line, v.col)):
        print(violation.format())

    sys.exit(1 if all_violations else 0)
