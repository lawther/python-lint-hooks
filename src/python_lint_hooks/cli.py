"""CLI entry point for ml-lint."""

from __future__ import annotations

import argparse
import inspect
import sys
import textwrap
import tomllib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import pathspec
from pydantic import BaseModel, ConfigDict, Field

from python_lint_hooks.rules import all_rules
from python_lint_hooks.runner import check_paths
from python_lint_hooks.violation import RuleCode, Violation


def _split_comma_list(value: str) -> list[str]:
    """Parse one `--flag value` occurrence into a list of trimmed, non-empty items.

    Used as the `type=` for --select/--ignore/--exclude and their extend- variants,
    each combined with `action="append"`. A single token per occurrence (rather than
    `nargs="+"`) avoids an argparse ambiguity where a multi-token option greedily
    swallows a following `nargs="*"` positional (e.g. the `paths` argument) when the
    flag is given before it on the command line.
    """
    return [item.strip() for item in value.split(",") if item.strip()]


def _flatten_groups(groups: list[list[str]] | None) -> list[str] | None:
    if groups is None:
        return None
    return [item for group in groups for item in group]


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
    model_config = ConfigDict(populate_by_name=True)

    exclude: list[str] = Field(default_factory=lambda: RUFF_DEFAULT_EXCLUDE)
    extend_exclude: list[str] = Field(default_factory=list, alias="extend-exclude")
    respect_gitignore: bool = Field(default=True, alias="respect-gitignore")
    force_exclude: bool = Field(default=False, alias="force-exclude")
    select: list[str] = Field(default_factory=list)
    extend_select: list[str] = Field(default_factory=list, alias="extend-select")
    ignore: list[str] = Field(default_factory=list)
    extend_ignore: list[str] = Field(default_factory=list, alias="extend-ignore")


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
        exclude = _flatten_groups(getattr(args, "exclude", None))
        if exclude is None:
            exclude = hooks_config.exclude

        extend_exclude = hooks_config.extend_exclude
        cli_extend_exclude = _flatten_groups(getattr(args, "extend_exclude", None))
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
        select = _flatten_groups(getattr(args, "select", None))
        if select is None:
            select = hooks_config.select

        # Selection logic: extend-select is additive across CLI and Config.
        extend_select = hooks_config.extend_select
        cli_extend_select = _flatten_groups(getattr(args, "extend_select", None))
        if cli_extend_select:
            extend_select = extend_select + cli_extend_select

        final_select = select + extend_select
        if not final_select:
            # If nothing is selected, default to all ML rules (Ruff selects some by default)
            final_select = ["ML"]

        # Ignore logic: CLI --ignore overrides Config ignore.
        ignore = _flatten_groups(getattr(args, "ignore", None))
        if ignore is None:
            ignore = hooks_config.ignore

        # Ignore logic: extend-ignore is additive across CLI and Config.
        extend_ignore = hooks_config.extend_ignore
        cli_extend_ignore = _flatten_groups(getattr(args, "extend_ignore", None))
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


def _find_project_root(path: Path) -> Path:
    abs_path = path.resolve()
    start_dir = abs_path if abs_path.is_dir() else abs_path.parent
    for d in (start_dir, *start_dir.parents):
        if (d / ".git").exists() or (d / ".gitignore").exists() or (d / "pyproject.toml").exists():
            return d
    return start_dir


def _load_gitignore_lines(root: Path) -> list[str]:
    gitignore_path = root / ".gitignore"
    if gitignore_path.exists():
        with gitignore_path.open("r", encoding="utf-8") as f:
            return f.readlines()
    return []


def _is_excluded(path: Path, spec: pathspec.PathSpec, gitignore_spec: pathspec.PathSpec, root: Path) -> bool:
    try:
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
    return gitignore_spec.match_file(path_str)


class _EffectiveSpecs(NamedTuple):
    spec: pathspec.PathSpec
    gitignore_spec: pathspec.PathSpec


def _collect_out_of_root_files(path: Path) -> list[Path]:
    if path.is_file() and path.suffix == ".py":
        return [path]
    if path.is_dir():
        return sorted(path.rglob("*.py"))
    return []


def _compute_effective_specs(
    config: _RunConfig,
    path_str: str,
    full_spec: pathspec.PathSpec,
    full_gitignore_spec: pathspec.PathSpec,
    gitignore_lines: list[str],
) -> _EffectiveSpecs:
    if config.force_exclude:
        return _EffectiveSpecs(spec=full_spec, gitignore_spec=full_gitignore_spec)

    # Ruff behaviour: if not force_exclude, we ignore exclusions matching the search path itself.
    # This allows explicitly passed files/dirs to be linted even if globally excluded.
    all_exclude_patterns = config.exclude + config.extend_exclude
    active_exclude = [
        pat
        for pat in all_exclude_patterns
        if not pathspec.PathSpec.from_lines("gitwildmatch", [pat]).match_file(path_str)
    ]
    active_gitignore = [
        line
        for line in gitignore_lines
        if not pathspec.PathSpec.from_lines("gitwildmatch", [line]).match_file(path_str)
    ]
    return _EffectiveSpecs(
        spec=pathspec.PathSpec.from_lines("gitwildmatch", active_exclude),
        gitignore_spec=pathspec.PathSpec.from_lines("gitwildmatch", active_gitignore),
    )


def _collect_matching_files(
    path: Path,
    specs: _EffectiveSpecs,
    root: Path,
) -> list[Path]:
    if path.is_file() and path.suffix == ".py":
        return [path]
    if path.is_dir():
        files: list[Path] = []
        for py_file in sorted(path.rglob("*.py")):
            py_file_abs = py_file.resolve()
            if not _is_excluded(py_file_abs, specs.spec, specs.gitignore_spec, root):
                files.append(py_file_abs)
        return files
    return []


def _collect_files_for_path(
    p: Path,
    config: _RunConfig,
    full_spec: pathspec.PathSpec,
) -> list[Path]:
    path = (Path.cwd() / p).resolve()
    root = _find_project_root(path)

    gitignore_lines = _load_gitignore_lines(root) if config.respect_gitignore else []
    full_gitignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", gitignore_lines)

    try:
        rel_path = path.relative_to(root)
        path_str = rel_path.as_posix()
        if path.is_dir() and path_str != ".":
            path_str += "/"
    except ValueError:
        return _collect_out_of_root_files(path)

    if config.force_exclude and _is_excluded(path, full_spec, full_gitignore_spec, root):
        return []

    specs = _compute_effective_specs(
        config,
        path_str,
        full_spec,
        full_gitignore_spec,
        gitignore_lines,
    )
    return _collect_matching_files(path, specs, root)


def _deduplicate_paths(paths: list[Path]) -> list[Path]:
    unique_files: list[Path] = []
    seen: set[str] = set()
    for f in paths:
        f_str = str(f)
        if f_str not in seen:
            unique_files.append(f)
            seen.add(f_str)
    return unique_files


def _collect_files(config: _RunConfig) -> list[Path]:
    files: list[Path] = []
    all_exclude_patterns = config.exclude + config.extend_exclude
    full_spec = pathspec.PathSpec.from_lines("gitwildmatch", all_exclude_patterns)

    for p in config.paths:
        files.extend(_collect_files_for_path(p, config, full_spec))

    return _deduplicate_paths(files)


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
        type=_split_comma_list,
        action="append",
        metavar="PATH[,PATH...]",
        help=(
            "Comma-separated list of paths to omit from analysis (repeatable). "
            "WARNING: This completely overrides default exclusions (like .venv, .git, etc.). "
            "Use --extend-exclude to preserve defaults and add new ones."
        ),
    )
    parser.add_argument(
        "--extend-exclude",
        type=_split_comma_list,
        action="append",
        metavar="PATH[,PATH...]",
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
        type=_split_comma_list,
        action="append",
        metavar="CODE[,CODE...]",
        help=(
            "Comma-separated list of rule codes to enable (repeatable), e.g. ML001. "
            "WARNING: This overrides the default selected rules. "
            "Use --extend-select to preserve defaults and add new ones."
        ),
    )
    parser.add_argument(
        "--extend-select",
        type=_split_comma_list,
        action="append",
        metavar="CODE[,CODE...]",
        dest="extend_select",
        help="Like --select, but adds additional rule codes on top of those already selected",
    )
    parser.add_argument(
        "--ignore",
        type=_split_comma_list,
        action="append",
        metavar="CODE[,CODE...]",
        help=(
            "Comma-separated list of rule codes to ignore (repeatable), e.g. ML200. "
            "WARNING: This overrides the default ignored rules. "
            "Use --extend-ignore to preserve defaults and add new ones."
        ),
    )
    parser.add_argument(
        "--extend-ignore",
        type=_split_comma_list,
        action="append",
        metavar="CODE[,CODE...]",
        dest="extend_ignore",
        help="Like --ignore, but adds additional rule codes on top of those already ignored",
    )
    parser.add_argument(
        "--explain",
        help="Print rationale and examples for a specific rule code (e.g., ML102)",
    )
    args = parser.parse_args()

    if args.explain:
        _explain_rule(args.explain)
        return

    hooks_config = _load_hooks_config(Path(args.config))
    run_config = _RunConfig.from_args(args, hooks_config)

    files = _collect_files(run_config)

    enabled_codes = frozenset(
        cls.code
        for cls in all_rules()
        if any(cls.code.startswith(s) for s in run_config.select)
        and not any(cls.code.startswith(i) for i in run_config.ignore)
    )

    all_violations: list[Violation] = check_paths(files, enabled_codes)

    for violation in sorted(all_violations, key=lambda v: (str(v.path), v.line, v.col)):
        print(violation.format())

    if all_violations:
        counts = Counter(v.code for v in all_violations)
        most_common, _ = counts.most_common(1)[0]
        print(f"\n💡 Tip: For more information and examples, run 'ml-lint --explain {most_common}'")

    sys.exit(1 if all_violations else 0)


def _explain_rule(code: str) -> None:
    """Print rationale and examples for a specific rule code."""
    code = code.upper()
    rules = {cls.code: cls for cls in all_rules()}
    if code not in rules:
        print(f"Error: Unknown rule code '{code}'", file=sys.stderr)
        sys.exit(1)

    cls = rules[RuleCode(code)]
    docstring = inspect.getdoc(cls) or "No rationale provided."

    print(f"{cls.code}: {cls.summary}")
    print("=" * (len(cls.code) + len(cls.summary) + 2))
    print(f"\nSuggestion: {cls.suggestion}")
    print(f"Rationale:\n{docstring}")

    try:
        if cls.bad_example:
            print("\nBad Example:")
            print("-" * 12)
            print(textwrap.dedent(cls.bad_example).strip())
    except AttributeError:
        print(f"\nError: Rule {cls.code} is missing mandatory 'bad_example' field.", file=sys.stderr)

    try:
        if cls.good_examples:
            header = "Good Example" if len(cls.good_examples) == 1 else "Good Examples"
            print(f"\n{header}:")
            print("-" * (len(header) + 1))
            for ex in cls.good_examples:
                print(textwrap.dedent(ex).strip())
                print()
    except AttributeError:
        print(f"Error: Rule {cls.code} is missing mandatory 'good_examples' field.", file=sys.stderr)


if __name__ == "__main__":
    main()
