#!/usr/bin/env python3
"""Sweep ml-lints rules across a corpus of external checkouts.

Measuring a rule's false-positive rate against a large volume of real code is the
evidence step before shipping or changing a rule. This script is that step, and
the justfile recipes `corpus-lint` and `corpus-diff` are its only entry points.

The ml-lints CLI cannot do this job. It excludes `.venv` by default, which is where
most of the corpus lives, and it aborts on the first file that is not valid UTF-8.
This script drives `ml_lints.runner.check_file` directly instead, swallowing the
per-file failures that a sweep of 60,000 unvetted files inevitably hits.

It is a developer tool, not a gate: it depends on checkouts outside this repo, so
nothing in `just precommit` or CI calls it.
"""

from __future__ import annotations

import argparse
import ast
import os
import subprocess
import sys
import tempfile
import tomllib
import warnings
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, NewType

from pydantic import BaseModel, ConfigDict, Field

from ml_lints.analyzers.newtype_index import NewTypeIndex
from ml_lints.runner import check_file
from ml_lints.violation import RuleCode, Violation

if TYPE_CHECKING:
    from collections.abc import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / ".corpus.toml"
EXAMPLE_CONFIG_PATH = REPO_ROOT / ".corpus.toml.example"
OUTPUT_DIR = REPO_ROOT / ".corpus-out"

_SAMPLES_PER_RULE = 5
_FINDINGS_PER_RATE_UNIT = 1000
"""Hit rates are quoted per this many files: raw counts are incomparable between
rules until divided by the corpus size, and per-file rates are all leading zeroes."""

_VENV_DIR_NAMES = frozenset({".venv", "venv", ".tox", ".nox"})
_NOISE_DIR_NAMES = frozenset({".git", "node_modules", "__pycache__", ".mypy_cache", ".ruff_cache"})

RuleCodeStr = NewType("RuleCodeStr", str)
"""A rule code as plain text. Deliberately not `RuleCode`: the diff's baseline half
runs against HEAD's copy of ml_lints, whose enum may not contain a code that the
working tree has just added."""


class ExitCode(Enum):
    """Process exit statuses. A sweep never fails on findings — findings are the point."""

    OK = 0
    MISCONFIGURED = 2
    CORPUS_MISSING = 3


class SkipReason(Enum):
    """Why a file in the corpus could not be checked."""

    UNREADABLE = "unreadable"
    NOT_UTF8 = "not valid UTF-8"
    SYNTAX_ERROR = "syntax error"
    TOO_DEEPLY_NESTED = "too deeply nested to parse"


class _CorpusConfig(BaseModel):
    """Validated contents of .corpus.toml."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    roots: list[str] = Field(min_length=1)
    include_venvs: bool = Field(default=True, alias="include-venvs")


@dataclass(frozen=True)
class CorpusRoot:
    """One project in the corpus, indexed independently of the others."""

    name: str
    path: Path


class Finding(NamedTuple):
    """One rule hit, in a form that survives a round trip through JSON.

    The sweep's two halves run in separate processes against different copies of
    ml_lints, so findings are compared as plain data rather than as `Violation`s.
    """

    code: RuleCodeStr
    path: str
    line: int
    col: int
    message: str

    def site(self) -> str:
        """Where the finding is, ignoring what it says.

        Two sweeps are matched on site rather than on the whole finding so that
        rewording a message does not read as every finding being removed and an
        equal number of new ones appearing at the same lines.
        """
        return f"{self.code}\t{self.path}\t{self.line}\t{self.col}"


@dataclass(frozen=True)
class SweepResult:
    """Everything one pass over the corpus produced."""

    findings: tuple[Finding, ...]
    files_checked: int
    files_skipped: tuple[SkipReason, ...]
    roots_swept: tuple[str, ...]
    roots_missing: tuple[str, ...]
    codes_requested: tuple[RuleCodeStr, ...]
    codes_unknown: tuple[RuleCodeStr, ...]


class RuleTally(NamedTuple):
    """Per-rule totals for the summary table."""

    code: RuleCodeStr
    hits: int
    files_hit: int
    rate_per_thousand: float


# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------


def load_config() -> _CorpusConfig:
    """Read and validate .corpus.toml, or explain how to create it and exit."""
    if not CONFIG_PATH.exists():
        print(f"error: no corpus configuration at {CONFIG_PATH}", file=sys.stderr)
        print(
            f"\nThe corpus lives in checkouts outside this repo, so its location is per-machine\n"
            f"and deliberately not committed. Create it with:\n\n"
            f"    cp {EXAMPLE_CONFIG_PATH.name} {CONFIG_PATH.name}\n\n"
            f"then edit the roots to match your machine.",
            file=sys.stderr,
        )
        sys.exit(ExitCode.MISCONFIGURED.value)

    with CONFIG_PATH.open("rb") as handle:
        raw = tomllib.load(handle)
    return _CorpusConfig.model_validate(raw)


def resolve_roots(config: _CorpusConfig) -> tuple[list[CorpusRoot], list[str]]:
    """Split the configured roots into those that exist and those that do not.

    A missing root is reported rather than fatal, so one config file can serve
    several machines that do not all have every checkout.
    """
    present: list[CorpusRoot] = []
    missing: list[str] = []
    for entry in config.roots:
        path = (REPO_ROOT / entry).resolve() if not Path(entry).is_absolute() else Path(entry).resolve()
        if path.is_dir():
            present.append(CorpusRoot(name=entry, path=path))
        else:
            missing.append(entry)
    return present, missing


# ----------------------------------------------------------------------------
# File collection
# ----------------------------------------------------------------------------


def collect_files(root: CorpusRoot, *, include_venvs: bool, already_seen: set[Path]) -> list[Path]:
    """Return the Python files under root, in a stable order, each resolved once.

    Resolving and deduping globally is not tidiness: a project root contains its own
    virtualenv, and site-packages routinely symlinks or vendors code that another
    root also holds. Without this, the same file is counted — and reported — twice.
    """
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root.path):
        dirnames[:] = sorted(
            name for name in dirnames if name not in _NOISE_DIR_NAMES and (include_venvs or name not in _VENV_DIR_NAMES)
        )
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            resolved = Path(dirpath, filename).resolve()
            if resolved in already_seen:
                continue
            already_seen.add(resolved)
            files.append(resolved)
    return files


# ----------------------------------------------------------------------------
# The sweep
# ----------------------------------------------------------------------------


def _silence_parse_warnings() -> None:
    """Stop third-party source from narrating its own defects through our output.

    Unvetted corpus code raises SyntaxWarning at parse time for things like invalid
    escape sequences. Those warnings are about the file being read, not about this
    sweep, and at corpus scale they bury the report they are printed alongside.
    """
    warnings.simplefilter("ignore", SyntaxWarning)
    warnings.simplefilter("ignore", DeprecationWarning)


def _skip_reason(error: Exception) -> SkipReason:
    if isinstance(error, UnicodeDecodeError):
        return SkipReason.NOT_UTF8
    if isinstance(error, SyntaxError):
        return SkipReason.SYNTAX_ERROR
    if isinstance(error, RecursionError):
        return SkipReason.TOO_DEEPLY_NESTED
    return SkipReason.UNREADABLE


def _build_index(files: Iterable[Path]) -> NewTypeIndex:
    """Build a NewType index over one root's files.

    One index per root, never one over the whole corpus. The index resolves an import
    by matching its dotted name against every module path it holds, and gives up when
    more than one matches. Pooled across unrelated checkouts almost every name is
    ambiguous, so ML108/ML109 fall silent anyway — and the rare name that does match
    exactly once can resolve into a different project entirely, inventing findings
    that no real run would ever produce.
    """
    index = NewTypeIndex()
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError, ValueError, RecursionError):
            continue
        index.ingest(str(path), tree)
    index.finalise()
    return index


def _known_codes() -> dict[RuleCodeStr, RuleCode]:
    return {RuleCodeStr(code.value): code for code in RuleCode}


def _to_finding(violation: Violation) -> Finding:
    return Finding(
        code=RuleCodeStr(str(violation.code)),
        path=str(violation.path),
        line=violation.line,
        col=violation.col,
        message=violation.message,
    )


def sweep(
    roots: Iterable[CorpusRoot],
    missing: Iterable[str],
    requested: Iterable[RuleCodeStr],
    *,
    include_venvs: bool,
    quiet: bool,
) -> SweepResult:
    """Run the selected rules over every root and collect the findings."""
    _silence_parse_warnings()

    known = _known_codes()
    requested_codes = tuple(requested)
    unknown = tuple(code for code in requested_codes if code not in known)
    selected = [known[code] for code in requested_codes if code in known]

    # An empty request means every rule; a request naming only codes this copy of
    # ml_lints has never heard of means none, and must not silently widen to all.
    enabled = frozenset(selected) if requested_codes else None
    nothing_to_run = bool(requested_codes) and not selected

    findings: list[Finding] = []
    skipped: list[SkipReason] = []
    checked = 0
    seen: set[Path] = set()
    swept: list[str] = []

    for root in roots:
        files = collect_files(root, include_venvs=include_venvs, already_seen=seen)
        swept.append(root.name)
        if nothing_to_run:
            checked += len(files)
            continue
        if not quiet:
            print(f"  {root.name}: {len(files)} files", file=sys.stderr, flush=True)
        index = _build_index(files)
        for path in files:
            checked += 1
            try:
                violations = check_file(path, enabled, project_index=index)
            except (OSError, SyntaxError, UnicodeDecodeError, ValueError, RecursionError) as error:
                skipped.append(_skip_reason(error))
                continue
            findings.extend(_to_finding(violation) for violation in violations)

    return SweepResult(
        findings=tuple(findings),
        files_checked=checked,
        files_skipped=tuple(skipped),
        roots_swept=tuple(swept),
        roots_missing=tuple(missing),
        codes_requested=requested_codes,
        codes_unknown=unknown,
    )


# ----------------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------------


def tally(result: SweepResult) -> list[RuleTally]:
    """Per-rule hit counts, worst offender first."""
    hits: dict[RuleCodeStr, int] = {}
    files: dict[RuleCodeStr, set[str]] = {}
    for finding in result.findings:
        hits[finding.code] = hits.get(finding.code, 0) + 1
        files.setdefault(finding.code, set()).add(finding.path)

    scale = _FINDINGS_PER_RATE_UNIT / result.files_checked if result.files_checked else 0.0
    tallies = [
        RuleTally(code=code, hits=count, files_hit=len(files[code]), rate_per_thousand=count * scale)
        for code, count in hits.items()
    ]
    return sorted(tallies, key=lambda entry: (-entry.hits, entry.code))


def _source_line(finding: Finding) -> str:
    """The offending line itself — a finding cannot be judged from its coordinates."""
    try:
        lines = Path(finding.path).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return "<source unavailable>"
    if not 1 <= finding.line <= len(lines):
        return "<line out of range>"
    return lines[finding.line - 1].strip()


def _samples(findings: Iterable[Finding], count: int) -> list[Finding]:
    """Spread the samples across the findings rather than taking the first few.

    Findings arrive grouped by root, so the leading ones all come from whichever
    project sorted first — exactly the sample least likely to expose a rule's range.
    """
    ordered = list(findings)
    if len(ordered) <= count:
        return ordered
    stride = len(ordered) / count
    return [ordered[int(index * stride)] for index in range(count)]


def _relative(path: str) -> str:
    """Shorten a corpus path against the repo's parent, which every root shares."""
    try:
        return str(Path(path).relative_to(REPO_ROOT.parent))
    except ValueError:
        return path


def _print_preamble(result: SweepResult) -> None:
    for root in result.roots_missing:
        print(f"note: corpus root not found, skipped: {root}", file=sys.stderr)
    if result.codes_unknown:
        print(f"note: unknown rule code(s) ignored: {', '.join(result.codes_unknown)}", file=sys.stderr)


def _print_skips(result: SweepResult) -> None:
    if not result.files_skipped:
        return
    counts: dict[SkipReason, int] = {}
    for reason in result.files_skipped:
        counts[reason] = counts.get(reason, 0) + 1
    breakdown = ", ".join(
        f"{count} {reason.value}" for reason, count in sorted(counts.items(), key=lambda p: p[0].name)
    )
    print(f"Skipped {len(result.files_skipped)} unparseable files ({breakdown}).")


def _print_silent_rules(result: SweepResult, tallies: list[RuleTally]) -> None:
    """Name the rules that fired nowhere, so zero is not mistaken for untested."""
    known = set(_known_codes())
    ran = set(result.codes_requested) & known if result.codes_requested else known
    silent = sorted(ran - {entry.code for entry in tallies})
    if silent:
        print(f"\nNo hits anywhere in the corpus: {', '.join(silent)}")


def report_scan(result: SweepResult) -> None:
    """Print the summary table and a spread of samples for each rule that fired."""
    _print_preamble(result)
    tallies = tally(result)

    print(f"\nSwept {result.files_checked} files across {len(result.roots_swept)} roots.")
    _print_skips(result)

    if not result.findings:
        print("\nNo findings.")
        _print_silent_rules(result, tallies)
        return

    print(f"\n{'RULE':<8} {'HITS':>7} {'FILES':>7} {'PER 1K':>8}")
    for entry in tallies:
        print(f"{entry.code:<8} {entry.hits:>7} {entry.files_hit:>7} {entry.rate_per_thousand:>8.2f}")

    by_code: dict[RuleCodeStr, list[Finding]] = {}
    for finding in result.findings:
        by_code.setdefault(finding.code, []).append(finding)

    for entry in tallies:
        print(f"\n{entry.code} — {entry.hits} hits, sampling {min(_SAMPLES_PER_RULE, entry.hits)}:")
        for finding in _samples(by_code[entry.code], _SAMPLES_PER_RULE):
            print(f"  {_relative(finding.path)}:{finding.line}:{finding.col}")
            print(f"      {_source_line(finding)}")
            print(f"      → {finding.message}")

    _print_silent_rules(result, tallies)


def write_full_output(result: SweepResult, name: str) -> Path:
    """Write every finding to a gitignored file, for grepping at full detail."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    destination = OUTPUT_DIR / name
    ordered = sorted(result.findings, key=lambda f: (f.code, f.path, f.line, f.col))
    destination.write_text(
        "".join(f"{f.path}:{f.line}:{f.col}: {f.code} {f.message}\n" for f in ordered),
        encoding="utf-8",
    )
    return destination


# ----------------------------------------------------------------------------
# Diff mode
# ----------------------------------------------------------------------------


class DiffSide(Enum):
    """How a finding differs between the two sweeps."""

    APPEARED = "Appeared (findings your working tree adds)"
    DISAPPEARED = "Disappeared (findings your working tree removes)"
    REWORDED = "Reworded (same site, different message)"


def _run_baseline_sweep(args: argparse.Namespace) -> SweepResult:
    """Sweep the corpus using HEAD's copy of ml_lints, leaving the working tree alone.

    A temporary detached worktree, not `git stash`. Stashing to get the 'before' means
    the developer's uncommitted work lives in a stash for the minutes the sweep takes,
    and a crash midway leaves it there. A worktree is read-only with respect to the
    files being edited.

    The baseline runs in a subprocess because ml_lints is already imported in this
    process. The child runs *this* script — not HEAD's copy of it — with HEAD's `src`
    on PYTHONPATH, so both halves of the diff use identical sweep logic over identical
    files and differ only in the rule code under test. Running HEAD's script instead
    would break the first time the script itself changed.

    PYTHONPATH rather than sys.path manipulation in the child: the editable install
    reaches the interpreter through a .pth file, and .pth entries are appended during
    site initialisation, after PYTHONPATH. Setting it in the environment therefore wins,
    and it keeps every ml_lints import at the top of this module where it belongs.
    """
    with tempfile.TemporaryDirectory(prefix="corpus-lint-head-") as tmp:
        worktree = Path(tmp) / "head"
        subprocess.run(
            ["git", "worktree", "add", "--detach", "--quiet", str(worktree), "HEAD"],
            cwd=REPO_ROOT,
            check=True,
        )
        try:
            payload = Path(tmp) / "baseline.json"
            subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--emit-json",
                    str(payload),
                    "--quiet",
                    *args.codes,
                ],
                cwd=REPO_ROOT,
                env={**os.environ, "PYTHONPATH": str(worktree / "src")},
                check=True,
            )
            return _BaselinePayload.model_validate_json(payload.read_text(encoding="utf-8")).to_result()
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                cwd=REPO_ROOT,
                check=False,
            )


class _BaselinePayload(BaseModel):
    """The baseline sweep as it crosses the process boundary.

    Validated rather than trusted: it arrives as JSON from a subprocess running a
    different checkout of ml_lints, which makes it outside data by the same argument
    that applies to any config file.
    """

    model_config = ConfigDict(extra="forbid")

    findings: list[Finding]
    files_checked: int
    files_skipped: list[SkipReason]
    roots_swept: list[str]
    roots_missing: list[str]
    codes_requested: list[str]
    codes_unknown: list[str]

    @classmethod
    def of(cls, result: SweepResult) -> _BaselinePayload:
        return cls(
            findings=list(result.findings),
            files_checked=result.files_checked,
            files_skipped=list(result.files_skipped),
            roots_swept=list(result.roots_swept),
            roots_missing=list(result.roots_missing),
            codes_requested=list(result.codes_requested),
            codes_unknown=list(result.codes_unknown),
        )

    def to_result(self) -> SweepResult:
        return SweepResult(
            findings=tuple(self.findings),
            files_checked=self.files_checked,
            files_skipped=tuple(self.files_skipped),
            roots_swept=tuple(self.roots_swept),
            roots_missing=tuple(self.roots_missing),
            codes_requested=tuple(RuleCodeStr(code) for code in self.codes_requested),
            codes_unknown=tuple(RuleCodeStr(code) for code in self.codes_unknown),
        )


def _print_side(side: DiffSide, findings: list[Finding]) -> None:
    print(f"\n{side.value}: {len(findings)}")
    if not findings:
        return
    by_code: dict[RuleCodeStr, list[Finding]] = {}
    for finding in findings:
        by_code.setdefault(finding.code, []).append(finding)
    for code in sorted(by_code):
        group = by_code[code]
        print(f"\n  {code} — {len(group)}:")
        for finding in group:
            print(f"    {_relative(finding.path)}:{finding.line}:{finding.col}")
            print(f"        {_source_line(finding)}")
            print(f"        → {finding.message}")


def report_diff(before: SweepResult, after: SweepResult) -> None:
    """Show only what changed between HEAD and the working tree."""
    _print_preamble(after)
    before_by_site = {finding.site(): finding for finding in before.findings}
    after_by_site = {finding.site(): finding for finding in after.findings}

    appeared = [f for site, f in after_by_site.items() if site not in before_by_site]
    disappeared = [f for site, f in before_by_site.items() if site not in after_by_site]
    reworded = [
        f for site, f in after_by_site.items() if site in before_by_site and before_by_site[site].message != f.message
    ]

    print(
        f"\nSwept {after.files_checked} files twice: HEAD ({len(before.findings)} findings) "
        f"vs working tree ({len(after.findings)} findings)."
    )
    if not appeared and not disappeared and not reworded:
        print("\nNo change. Your working tree finds exactly what HEAD finds.")
        return

    _print_side(DiffSide.APPEARED, appeared)
    _print_side(DiffSide.DISAPPEARED, disappeared)
    if reworded:
        _print_side(DiffSide.REWORDED, reworded)


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="corpus-lint",
        description="Sweep ml-lints rules across external checkouts to measure false positives.",
    )
    parser.add_argument(
        "codes",
        nargs="*",
        metavar="CODE",
        help="Rule codes to sweep (e.g. ML701). Omit to sweep every rule.",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Sweep twice — HEAD and the working tree — and report only what changed.",
    )
    parser.add_argument(
        "--emit-json",
        metavar="PATH",
        help=argparse.SUPPRESS,  # internal: how the baseline subprocess returns its sweep
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-root progress on stderr.",
    )
    return parser.parse_args(argv)


def _sweep_from_config(args: argparse.Namespace) -> SweepResult:
    config = load_config()
    roots, missing = resolve_roots(config)
    if not roots:
        print(
            f"error: none of the {len(missing)} configured corpus roots exist. Check the roots in {CONFIG_PATH.name}.",
            file=sys.stderr,
        )
        sys.exit(ExitCode.CORPUS_MISSING.value)
    codes = tuple(RuleCodeStr(code.upper()) for code in args.codes)
    return sweep(roots, missing, codes, include_venvs=config.include_venvs, quiet=args.quiet)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    if args.diff:
        before = _run_baseline_sweep(args)
        after = _sweep_from_config(args)
        report_diff(before, after)
        write_full_output(after, "latest.txt")
        sys.exit(ExitCode.OK.value)

    result = _sweep_from_config(args)

    if args.emit_json:
        Path(args.emit_json).write_text(_BaselinePayload.of(result).model_dump_json(), encoding="utf-8")
        sys.exit(ExitCode.OK.value)

    report_scan(result)
    destination = write_full_output(result, "latest.txt")
    print(f"\nFull findings: {destination.relative_to(REPO_ROOT)}")
    sys.exit(ExitCode.OK.value)


if __name__ == "__main__":
    main()
