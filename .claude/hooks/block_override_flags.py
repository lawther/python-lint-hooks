#!/usr/bin/env python3
"""Decide whether a shell command exists only to override a refusal.

A tool refusing is information. ``bd --force``, ``git push --force`` and ``--no-verify`` all
exist to silence a refusal, and silencing one is the user's decision, not the agent's. This
script is the decision half of the ``PreToolUse`` guard: the wrapper hands it one command
string as ``argv[1]``, and it prints the deny payload, or nothing at all.

Matching is on shell **tokens**, via :mod:`shlex`, not on the raw command string. A flag
inside a quoted argument — a commit message, a ``bd --append-notes`` body, this file's own
prose — is data, not a flag, and must not trip the guard.

Standard library only, and no project imports: the hook runs under the system interpreter
before any project environment is guaranteed.
"""

from __future__ import annotations

import json
import shlex
import sys
from typing import NamedTuple

_FORCE_FLAG = "--force"
_SHORT_FORCE_FLAG = "-f"
_LEASE_FLAG_PREFIX = "--force-with-lease"
_NO_VERIFY_FLAG = "--no-verify"


class Rule(NamedTuple):
    """One refusal-override pattern: a short name, and why the command is denied."""

    name: str
    reason: str


BD_FORCE = Rule(
    name="bd --force",
    reason=(
        "Blocked: 'bd --force' overrides a dependency the tracker is enforcing. A blocked bd "
        "operation is the graph telling you the work is not finishable yet — the error text "
        "'use --force to override' describes a mechanism, it does not grant permission. Stop "
        "and ask the user whether the dependency is wrong."
    ),
)

FORCE_PUSH = Rule(
    name="force push",
    reason=("Blocked: force push. Rewriting published history is the user's call, never the agent's. Stop and ask."),
)

SKIPPED_VERIFICATION = Rule(
    name="--no-verify",
    reason=(
        "Blocked: '--no-verify' skips the precommit gate. A failing gate is a finding to "
        "report to the user, not an obstacle to route around. Stop and ask."
    ),
)


def tokenise(command: str) -> list[str]:
    """Shell tokens of ``command``, falling back to a whitespace split on unparseable input.

    The fallback errs towards blocking: it can only ever expose *more* bare tokens than
    :func:`shlex.split` would, so a command this script cannot parse is more likely to be
    denied than waved through.
    """
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def violated_rule(tokens: list[str]) -> Rule | None:
    """The rule ``tokens`` breaks, or ``None`` when the command is not an override."""
    present = set(tokens)
    forced = (
        _FORCE_FLAG in present
        or _SHORT_FORCE_FLAG in present
        or any(token.startswith(_LEASE_FLAG_PREFIX) for token in tokens)
    )

    if "bd" in present and _FORCE_FLAG in present:
        return BD_FORCE
    # Deliberately loose: any command naming both 'git' and 'push' alongside a force flag.
    # Over-blocking costs one question; under-blocking costs rewritten remote history.
    if "git" in present and "push" in present and forced:
        return FORCE_PUSH
    if _NO_VERIFY_FLAG in present:
        return SKIPPED_VERIFICATION
    return None


def main(argv: list[str]) -> None:
    """Print the PreToolUse deny payload when ``argv[1]`` overrides a refusal."""
    if len(argv) < 2:  # noqa: PLR2004 - argv[0] is the script; argv[1] is the command under test
        return
    rule = violated_rule(tokenise(argv[1]))
    if rule is None:
        return
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": rule.reason,
            }
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main(sys.argv)
