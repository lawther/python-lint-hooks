"""CLI entry point for ml-lint."""

from __future__ import annotations

import argparse
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pathspec
from pydantic import BaseModel, Field

from python_lint_hooks.rules import all_rules
from python_lint_hooks.runner import check_file
from python_lint_hooks.violation import Violation

if TYPE_CHECKING:
    pass


# Ruff's default exclusion list
RUFF_DEFAULT_EXCLUDE = [
    ".bzr",
    ".direnv",
    ".eggs",
    ".git",
    ".git-rewrite",
    ".hg",
    ".mypy_cache",
    ".nox",
    ".pants.d",
    ".pytype",
    ".ruff_cache",
    ".svn",
    ".tox",
    ".venv",
    "__pypackages__",
    "_build",
    "buck-out",
    "build",
    "dist",
    "node_modules",
    "venv",
]


class _HooksConfig(BaseModel):
    exclude: list[str] = Field(default_factory=lambda: RUFF_DEFAULT_EXCLUDE)
    extend_exclude: list[str] = Field(default_factory=list, alias="extend-exclude")
    respect_gitignore: bool = Field(default=True, alias="respect-gitignore")
    force_exclude: bool = Field(default=False, alias="force-exclude")
    select: list[str] = Field(default_factory=list)
    extend_select: list[str] = Field(default_factory=list, alias="extend-select")
    ignore: list[str] = Field(default_factory=list)
    extend_ignore: list[str] = Field(default_factory=list, alias="extend-ignore")

    class Config:
        populate_by_name = True


@dataclass(frozen=True)
class _RunConfig:
    paths: list[Path]
    exclude: list[str]
    extend_exclude: list[str]
    respect_gitignore: bool
    force_exclude: bool
    select: list[str]
    ignore: list[str]

    @classmethod
    def from_args(cls, args: argparse.Namespace, hooks_config: _HooksConfig) -> _RunConfig:
        # Exclusion logic (matches Ruff's override/additive behavior)
        exclude = getattr(args, "exclude", None)
        if exclude is None:
            exclude = hooks_config.exclude

        extend_exclude = hooks_config.extend_exclude
        cli_extend_exclude = getattr(args, "extend_exclude", None)
        if cli_extend_exclude:
            extend_exclude = extend_exclude + cli_extend_exclude

        # Boolean flags
        respect_gitignore = getattr(args, "respect_gitignore", None)
        if respect_gitignore is None:
            respect_gitignore = hooks_config.respect_gitignore

        force_exclude = getattr(args, "force_exclude", None)
        if force_exclude is None:
            force_exclude = hooks_config.force_exclude

        # Selection logic: CLI --select overrides Config select.
        select = getattr(args, "select", None)
        if select is None:
            select = hooks_config.select

        # Selection logic: extend-select is additive across CLI and Config.
        extend_select = hooks_config.extend_select
        cli_extend_select = getattr(args, "extend_select", None)
        if cli_extend_select:
            extend_select = extend_select + cli_extend_select

        final_select = select + extend_select
        if not final_select:
            # If nothing is selected, default to all ML rules (Ruff selects some by default)
            final_select = ["ML"]

        # Ignore logic: CLI --ignore overrides Config ignore.
        ignore = getattr(args, "ignore", None)
        if ignore is None:
            ignore = hooks_config.ignore

        # Ignore logic: extend-ignore is additive across CLI and Config.
        extend_ignore = hooks_config.extend_ignore
        cli_extend_ignore = getattr(args, "extend_ignore", None)
        if cli_extend_ignore:
            extend_ignore = extend_ignore + cli_extend_ignore

        final_ignore = ignore + extend_ignore

        return cls(
            paths=[Path(p) for p in args.paths],
            exclude=exclude,
            extend_exclude=extend_exclude,
            respect_gitignore=respect_gitignore,
            force_exclude=force_exclude,
            select=final_select,
            ignore=final_ignore,
        )


def _load_hooks_config(config_path: Path) -> _HooksConfig:
    if not config_path.exists():
        return _HooksConfig()
    with config_path.open("rb") as f:
        data = tomllib.load(f)  # noqa: ML400
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return _HooksConfig()
    hooks_raw = tool.get("python-lint-hooks")
    if not isinstance(hooks_raw, dict):
        return _HooksConfig()
    return _HooksConfig.model_validate(hooks_raw)


def _load_gitignore(root: Path) -> pathspec.PathSpec:
    gitignore_path = root / ".gitignore"
    if gitignore_path.exists():
        with gitignore_path.open("r", encoding="utf-8") as f:
            return pathspec.PathSpec.from_lines("gitwildmatch", f)
    return pathspec.PathSpec.from_lines("gitwildmatch", [])


def _is_excluded(path: Path, spec: pathspec.PathSpec, gitignore_spec: pathspec.PathSpec | None, root: Path) -> bool:
    try:
        # Resolve to absolute then to relative to root to ensure we have a clean relative path
        rel_path = path.resolve().relative_to(root.resolve())
    except ValueError:
        return False

    # pathspec expects posix-style paths
    path_str = rel_path.as_posix()
    if path.is_dir():
        path_str += "/"

    # Check explicit excludes
    if spec.match_file(path_str):
        return True

    # Check gitignore if enabled
    return bool(gitignore_spec and gitignore_spec.match_file(path_str))


def _collect_files(config: _RunConfig, root: Path) -> list[Path]:
    files: list[Path] = []
    # Ensure patterns are treated as gitwildmatch
    spec = pathspec.PathSpec.from_lines("gitwildmatch", config.exclude + config.extend_exclude)

    # Load gitignore from the root (CWD)
    gitignore_spec = _load_gitignore(root) if config.respect_gitignore else None

    for p in config.paths:
        path = (root / p).resolve()

        if path.is_file() and path.suffix == ".py":
            # If it's an explicit file path, we only exclude it if force_exclude is True
            if not config.force_exclude or not _is_excluded(path, spec, gitignore_spec, root):
                files.append(path)
        elif path.is_dir():
            for py_file in sorted(path.rglob("*.py")):
                is_parent_excluded = False
                try:
                    rel_to_root = py_file.resolve().relative_to(root.resolve())
                    # Check each parent directory for exclusion
                    for parent in list(rel_to_root.parents)[:-1]:  # exclude '.'
                        if _is_excluded(root / parent, spec, gitignore_spec, root):
                            is_parent_excluded = True
                            break
                except ValueError:
                    pass

                if not is_parent_excluded and not _is_excluded(py_file, spec, gitignore_spec, root):
                    files.append(py_file)

    # De-duplicate files while preserving order
    return list(dict.fromkeys(files))


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
    parser.add_argument(
        "--exclude",
        nargs="+",
        help="List of paths, used to omit files and/or directories from analysis",
    )
    parser.add_argument(
        "--extend-exclude",
        nargs="+",
        dest="extend_exclude",
        help="Like --exclude, but adds additional files and directories on top of those already excluded",
    )
    parser.add_argument(
        "--respect-gitignore",
        action=argparse.BooleanOptionalAction,
        dest="respect_gitignore",
        help="Respect file exclusions via `.gitignore` and other standard ignore files",
    )
    parser.add_argument(
        "--force-exclude",
        action=argparse.BooleanOptionalAction,
        dest="force_exclude",
        help="Enforce exclusions, even for paths passed to Ruff directly on the command-line",
    )
    parser.add_argument(
        "--select",
        nargs="+",
        help="List of rule codes to enable (e.g., ML001)",
    )
    parser.add_argument(
        "--extend-select",
        nargs="+",
        dest="extend_select",
        help="Like --select, but adds additional rule codes on top of those already selected",
    )
    parser.add_argument(
        "--ignore",
        nargs="+",
        help="List of rule codes to ignore (e.g., ML200)",
    )
    parser.add_argument(
        "--extend-ignore",
        nargs="+",
        dest="extend_ignore",
        help="Like --ignore, but adds additional rule codes on top of those already ignored",
    )
    args = parser.parse_args()

    hooks_config = _load_hooks_config(Path(args.config))
    run_config = _RunConfig.from_args(args, hooks_config)
    root = Path.cwd().resolve()

    files = _collect_files(run_config, root)

    enabled_codes = frozenset(
        cls.code
        for cls in all_rules()
        if any(cls.code.startswith(s) for s in run_config.select)
        and not any(cls.code.startswith(i) for i in run_config.ignore)
    )

    all_violations: list[Violation] = []
    for file in files:
        all_violations.extend(check_file(file, enabled_codes))

    for violation in sorted(all_violations, key=lambda v: (str(v.path), v.line, v.col)):
        print(violation.format())

    sys.exit(1 if all_violations else 0)
