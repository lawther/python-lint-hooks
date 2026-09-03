#!/usr/bin/env python3
"""PreToolUse(Bash) guard: keep each bead's `model:` label present, single and honoured.

Every bead in this project carries exactly one `model:sonnet` or `model:opus` label
recording which model the work was scoped for -- `model:sonnet` for mechanical work,
`model:opus` for work that needs design decisions. This hook enforces that rule at the
two points where it can be broken.

CREATE. `bd create` (and its `new` alias, and `bd q`) must produce exactly one model
label. Labels are inherited from `--parent` unless `--no-inherit-labels` is passed, so
the effective set is the explicit `--labels` plus the parent's -- which is why an
explicit label that disagrees with an inherited one yields two, not an override.

CLAIM. `bd update <id> --claim` is the only atomic claim path, so the hook watches for
that flag combination, reads each target's model label via `bd show`, and compares it
to the model that produced the current turn.

Both checks treat two model labels as a failure, not as "either will do". A bead
labelled for both families silently satisfies the claim comparison for every model,
which is strictly worse than an unlabelled bead: unlabelled fails open by design and
visibly, dual-labelled looks guarded while guarding nothing.

No env var or hook input field exposes the active model directly, so it is read from
the transcript instead: `transcript_path` (given in the hook payload) is a JSONL file
where each assistant turn's `message.model` records what actually generated it. That
is the model of record -- more reliable than anything the agent could self-report.

A failure denies the command, which surfaces the reason to the agent so it stops and
asks the user rather than proceeding. Everything else -- no model label on the bead at
claim time, no resolvable transcript, a `bd show` failure, a batch create from a file
or graph whose labels cannot be attributed per issue -- allows the command through:
this is a policy nudge, not a safety boundary, and a false block costs more than an
occasional unlabelled bead slipping past it.

`bd` DETECTION IS COMMAND-POSITION, NOT MEMBERSHIP. `create_commands()` and
`claim_commands()` split the token stream on bare `&&`/`||`/`;`/`|`, treat a segment as
a `bd` invocation only when `bd` is that segment's first token, and check every such
segment in the chain rather than just the first. This closes two concrete bugs a plain
`"bd" in tokens` / `tokens.index("bd")` check has: `rg bd create` was denied (false
positive -- "bd" there is an argument to `rg`, not the command), and `bd show x && bd
create y` was allowed (false negative -- `.index` only ever finds the first "bd", so a
later command in the chain was never examined).

Segmenting on shell operators is still NOT a complete fix, and does not attempt to be:
`FOO=1 bd create`, `sh -c "bd create"`, `time`/`command`/`nohup` prefixes, `(bd
create)` subshells, `if`/loop bodies, and `xargs` all still evade command-position
detection, because none of them put `bd` as the segment's first token even though `bd`
is what ultimately runs. Closing those needs interposing on `bd` itself (a wrapper on
PATH) rather than parsing the shell string -- tracked as a follow-up, deliberately not
attempted here. This hook remains a nudge, not a boundary.

A NEWLINE IS A SEPARATOR TOO, and recovering it is why `tokenise()` works a line at a
time rather than handing shlex the whole command. shlex treats a newline as ordinary
whitespace, so `bd show x` + newline + `bd create y` collapsed into one segment beginning
`bd show` and the unlabelled create on the second line was never examined. Splitting on
lines and splicing a synthetic `;` between them restores the boundary, but only once the
three things that legitimately span lines are stitched back together first:

  * a quoted value -- a line that fails to parse is held and retried joined to the next
    with its newline intact, so a multi-line `--notes` reaches the checks byte-for-byte
    rather than being mangled or split into a bogus second command;
  * a backslash continuation -- distinguished from the above by `ends_mid_escape()`, and
    dropped the way a shell drops it, so a `bd create` whose `-l model:opus` sits on a
    continuation line is no longer read as a create with no label at all and denied;
  * a heredoc body -- its lines are data, not commands, so a document being written with
    `cat <<EOF` that quotes `bd create` in its text is not mistaken for running one.

What newline segmentation still does not see: a heredoc whose delimiter never appears
swallows the rest of the command, and a quoted word that survives quote-stripping looking
exactly like an operator (`echo "<<EOF"`) starts a body that is not there -- both fail
open, consistent with the rest of the hook. A backslash-newline *inside* double quotes
keeps a literal newline where a shell would remove it, which can only ever alter the
inside of a quoted value, never where a command boundary falls.

Standard library only, and no project imports: the hook runs under the system
interpreter before any project environment is guaranteed.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

_MODEL_LABEL_RE = re.compile(r"^model:(?P<family>\w+)$")
_MODEL_FAMILY_RE = re.compile(r"opus|sonnet|haiku|fable", re.IGNORECASE)
_BD_SHOW_TIMEOUT_SECS = 15

# Subcommands of `bd` that mint a new issue. `new` is an alias of `create`; `q` is
# quick capture, which takes --labels too.
_CREATE_SUBCOMMANDS = frozenset({"create", "new", "q"})

# Create forms whose labels cannot be attributed to individual issues: the labels live
# inside the markdown/JSON payload, not in argv. These are allowed through unchecked.
_BATCH_CREATE_FLAGS = frozenset({"-f", "--file", "--graph"})

_LABEL_FLAGS = frozenset({"-l", "--labels"})
_PARENT_FLAGS = frozenset({"--parent"})

# Shell control operators that separate one command from the next. shlex.split
# returns these as their own unquoted tokens, so a segment boundary is just "this
# token, verbatim, outside quotes". A lone "&" backgrounds the command before it and
# is therefore a separator too; "&&", "&>" and "2>&1" tokenise whole, so including it
# does not split them.
_COMMAND_SEPARATORS = frozenset({"&&", "||", ";", "|", "&"})

# The separator spliced in where a newline ended a command, so the segmenter above sees
# a boundary that shlex would otherwise have swallowed as ordinary whitespace.
_SYNTHETIC_SEPARATOR = ";"

# A heredoc redirection: an optional fd, `<<` or `<<-`, and the delimiter word, which may
# instead be the next token. `[^<]` keeps `<<<` (a here-string, which has no body) out.
_HEREDOC_OPERATOR_RE = re.compile(r"^\d*<<(?P<dash>-?)(?P<delimiter>[^<].*)?$")

# Any ordinary character will do: it is only ever appended to a chunk that already failed
# to parse, to tell a dangling backslash apart from an unterminated quote.
_ESCAPE_PROBE_CHAR = "x"

_HOW_TO_LABEL = (
    "Every bead needs exactly one model label: `model:sonnet` for mechanical work, "
    "`model:opus` for work needing design decisions. Add `-l model:<family>`."
)


class Heredoc(NamedTuple):
    delimiter: str
    strips_tabs: bool


class ClaimCommand(NamedTuple):
    issue_ids: list[str]


class CreateCommand(NamedTuple):
    explicit_labels: list[str]
    parent_id: str
    inherits_labels: bool


class Mismatch(NamedTuple):
    issue_id: str
    wanted_families: list[str]


def allow() -> None:
    sys.exit(0)


def deny(reason: str) -> None:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    sys.exit(0)


def heredocs_opened(tokens: list[str]) -> list[Heredoc]:
    """The heredoc bodies `tokens` queues up, in the order the shell will consume them."""
    opened = []
    awaiting_delimiter = False
    awaited_strips_tabs = False
    for token in tokens:
        if awaiting_delimiter:
            opened.append(Heredoc(delimiter=token, strips_tabs=awaited_strips_tabs))
            awaiting_delimiter = False
            continue
        match = _HEREDOC_OPERATOR_RE.match(token)
        if not match:
            continue
        awaited_strips_tabs = bool(match.group("dash"))
        delimiter = match.group("delimiter") or ""
        if delimiter:
            opened.append(Heredoc(delimiter=delimiter, strips_tabs=awaited_strips_tabs))
        else:
            awaiting_delimiter = True
    return opened


def ends_mid_escape(chunk: str) -> bool:
    """True if `chunk` breaks off on a backslash outside any quote -- a line continuation.

    shlex cannot answer this directly: an unterminated quote and a dangling backslash both
    raise ValueError. Appending one ordinary character separates them, because it satisfies
    a dangling escape but leaves an open quote just as open.
    """
    try:
        shlex.split(chunk + _ESCAPE_PROBE_CHAR)
    except ValueError:
        return False
    return True


def tokenise(command: str) -> list[str]:
    """`command` as tokens, with a synthetic `;` marking each newline that ends a command.

    Tokenising the whole string at once loses newlines entirely -- shlex treats one as
    ordinary whitespace, so `bd show x` + newline + `bd create y` reads as a single
    command. Tokenising each physical line instead recovers the boundary, provided three
    things that span lines are stitched back together first: a quoted value, a backslash
    continuation, and a heredoc body (whose lines are data, not commands).
    """
    tokens: list[str] = []
    pending = ""
    holding = False
    unread_heredocs: list[Heredoc] = []

    for line in command.split("\n"):
        if unread_heredocs:
            body_line = line.lstrip("\t") if unread_heredocs[0].strips_tabs else line
            if body_line == unread_heredocs[0].delimiter:
                unread_heredocs.pop(0)
            continue
        chunk = pending + line if holding else line
        try:
            line_tokens = shlex.split(chunk)
        except ValueError:
            # The line stops inside something that continues below: drop a continuation's
            # backslash-newline the way a shell does, and keep a quoted value's newline.
            pending = chunk[:-1] if ends_mid_escape(chunk) else chunk + "\n"
            holding = True
            continue
        pending, holding = "", False
        unread_heredocs = heredocs_opened(line_tokens)
        if not line_tokens:
            continue
        if tokens:
            tokens.append(_SYNTHETIC_SEPARATOR)
        tokens.extend(line_tokens)

    # Anything still held here never balanced, so the quote is genuinely unterminated, and
    # the remainder is deliberately dropped rather than tokenised. Splitting it on whitespace
    # -- the old fallback -- turned prose into tokens: one apostrophe in a commit message
    # left a quote open, shredded the whole command, and let the words "bd create" inside
    # the message read as a real command, denying the commit. Prose containing an apostrophe
    # is ordinary, so that fired constantly. Not checking what cannot be parsed is the
    # fail-open this hook promises everywhere else: better to miss a create than to invent
    # one that was never run.
    return tokens


def command_segments(tokens: list[str]) -> list[list[str]]:
    """`tokens` split into per-command segments at bare `&&`/`||`/`;`/`|` tokens."""
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in _COMMAND_SEPARATORS:
            segments.append([])
        else:
            segments[-1].append(token)
    return [segment for segment in segments if segment]


def bd_segments(tokens: list[str]) -> list[list[str]]:
    """Segments of `tokens` that are a `bd` invocation -- `bd` in command position."""
    return [segment for segment in command_segments(tokens) if segment[0] == "bd"]


def flag_values(tokens: list[str], flags: frozenset[str]) -> list[str]:
    """Values given to any of `flags`, accepting both `--flag value` and `--flag=value`."""
    values = []
    for index, token in enumerate(tokens):
        name, separator, inline_value = token.partition("=")
        if name not in flags:
            continue
        if separator:
            values.append(inline_value)
        elif index + 1 < len(tokens):
            values.append(tokens[index + 1])
    return values


def model_families(labels: list[str]) -> set[str]:
    """The distinct model families named by `labels` (e.g. {'opus'})."""
    return {match.group("family").lower() for label in labels if (match := _MODEL_LABEL_RE.match(label.strip()))}


def create_commands(tokens: list[str]) -> list[CreateCommand]:
    """Every checkable create this (possibly chained) command performs."""
    creates = []
    for call in bd_segments(tokens):
        subcommand = next((token for token in call[1:] if not token.startswith("-")), "")
        if subcommand not in _CREATE_SUBCOMMANDS:
            continue
        # --dry-run and --help/-h create nothing, and batch forms carry their labels in a
        # payload file.
        if (
            "--dry-run" in call
            or "--help" in call
            or "-h" in call
            or any(token.partition("=")[0] in _BATCH_CREATE_FLAGS for token in call)
        ):
            continue
        explicit_labels = [
            label for value in flag_values(call, _LABEL_FLAGS) for label in value.split(",") if label.strip()
        ]
        parent_ids = flag_values(call, _PARENT_FLAGS)
        creates.append(
            CreateCommand(
                explicit_labels=explicit_labels,
                parent_id=parent_ids[0] if parent_ids else "",
                inherits_labels="--no-inherit-labels" not in call,
            )
        )
    return creates


def create_denial(create: CreateCommand) -> str | None:
    """Why this create must be blocked, or None if its model labelling is correct."""
    families = model_families(create.explicit_labels)
    inherited: set[str] = set()
    if create.parent_id and create.inherits_labels:
        parent_families = bead_model_labels([create.parent_id]).get(create.parent_id)
        if parent_families is None:
            # Parent unreadable: cannot compute the effective set, so do not guess.
            return None
        inherited = set(parent_families)
    effective = families | inherited

    if not effective:
        return f"Blocked: this `bd create` would make a bead with no model label. {_HOW_TO_LABEL}"
    if len(effective) == 1:
        return None

    conflict = "/".join(f"model:{family}" for family in sorted(effective))
    if inherited and families - inherited:
        return (
            f"Blocked: this `bd create` would make a bead labelled {conflict} — the explicit label does "
            f"not override the one inherited from {create.parent_id}, it is added to it. Pass "
            "`--no-inherit-labels` and give the full label set explicitly, or drop the explicit model "
            "label to keep the parent's. A bead with two model labels satisfies the claim-time guard "
            "for every model, so it is not guarded at all."
        )
    return (
        f"Blocked: this `bd create` names {conflict}. A bead carries exactly one model label — two "
        "satisfies the claim-time guard for every model, so it is not guarded at all."
    )


def claim_commands(tokens: list[str]) -> list[ClaimCommand]:
    """Every `bd update ... --claim` this (possibly chained) command performs."""
    claims = []
    for call in bd_segments(tokens):
        if "update" not in call or "--claim" not in call:
            continue
        update_idx = call.index("update")
        issue_ids = []
        for token in call[update_idx + 1 :]:
            if token.startswith("-"):
                break
            issue_ids.append(token)
        if issue_ids:
            claims.append(ClaimCommand(issue_ids=issue_ids))
    return claims


def current_model_family(transcript_path: str) -> str | None:
    """Model family (e.g. 'sonnet') of the most recent assistant turn in the transcript."""
    try:
        with Path(transcript_path).open(encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return None
    for raw_line in reversed(lines):
        stripped_line = raw_line.strip()
        if not stripped_line:
            continue
        try:
            # Standard-library-only script (see module docstring); every field access below
            # is via .get() with a None-safe fallback, so a malformed transcript line degrades
            # to "no model found" rather than raising.
            entry = json.loads(stripped_line)  # noqa: ML400
        except json.JSONDecodeError:
            continue
        if entry.get("type") != "assistant":
            continue
        model_id = (entry.get("message") or {}).get("model")
        if not model_id:
            continue
        match = _MODEL_FAMILY_RE.search(model_id)
        if match:
            return match.group(0).lower()
    return None


def bead_model_labels(issue_ids: list[str]) -> dict[str, list[str]]:
    """Map of issue_id -> its model:<family> label values (e.g. ['opus']), missing if unknown."""
    try:
        # issue_ids come from shlex-tokenised argv positions (never a raw shell string), passed
        # as separate argv elements with shell=False; "bd" is resolved via PATH deliberately,
        # matching how the SessionStart hook already invokes it project-wide.
        result = subprocess.run(  # noqa: S603
            ["bd", "show", *issue_ids, "--json"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=_BD_SHOW_TIMEOUT_SECS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    issues = payload if isinstance(payload, list) else [payload]
    labels_by_id = {}
    for issue in issues:
        issue_id = issue.get("id")
        if not issue_id:
            continue
        families = [
            match.group("family").lower()
            for label in issue.get("labels") or []
            if (match := _MODEL_LABEL_RE.match(label))
        ]
        labels_by_id[issue_id] = families
    return labels_by_id


def main() -> None:
    # Standard-library-only script (see module docstring); every field access below is via
    # .get() with a None-safe fallback, and the __main__ guard below fails open on any
    # exception, so malformed hook input degrades to "allow" rather than raising.
    hook_input = json.load(sys.stdin)  # noqa: ML400
    command = (hook_input.get("tool_input") or {}).get("command", "")
    tokens = tokenise(command)

    for create in create_commands(tokens):
        denial = create_denial(create)
        if denial is not None:
            deny(denial)
            return

    issue_ids = [issue_id for claim in claim_commands(tokens) for issue_id in claim.issue_ids]
    if not issue_ids:
        allow()
        return

    labels_by_id = bead_model_labels(issue_ids)
    ambiguous = [
        Mismatch(issue_id, wanted) for issue_id in issue_ids if len(wanted := labels_by_id.get(issue_id) or []) > 1
    ]
    if ambiguous:
        details = "; ".join(f"{m.issue_id} is labelled {'/'.join(sorted(m.wanted_families))}" for m in ambiguous)
        deny(
            f"Blocked: {details}. A bead carries exactly one model label — two matches every model, so "
            f"the tier is unguarded. Fix the bead's labels before claiming it. {_HOW_TO_LABEL}"
        )
        return

    # An unlabelled bead is a deliberate fail-open (see module docstring), as is an
    # unreadable transcript -- neither can be compared against, so neither blocks.
    current_family = current_model_family(hook_input.get("transcript_path", ""))
    if current_family is None:
        allow()
        return

    mismatches = [
        Mismatch(issue_id, wanted_families)
        for issue_id in issue_ids
        if (wanted_families := labels_by_id.get(issue_id)) and current_family not in wanted_families
    ]
    if not mismatches:
        allow()
        return

    details = "; ".join(f"{m.issue_id} wants {'/'.join(m.wanted_families)}" for m in mismatches)
    deny(
        f"Blocked: this session is running on '{current_family}', but {details}. Stop and ask "
        "the user whether to switch model, reassign the bead's model label, or claim it anyway."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - a hook bug must fail open, not block every Bash call
        allow()
