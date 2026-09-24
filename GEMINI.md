<!-- BEGIN GLOBAL RULES sha256:a0e8b2b522f5c8bd -->
<!-- Generated from agent_rules/global.md. Do not edit inside this block:
     edit global.md, then run `just sync-rules` in agent_rules. -->

# Automation

- NEVER rely on manual steps (for example, the developer must remember to run a code generator after updating an API). If a step is required, add it to the `justfile`.

# Python Code Style

- All code must pass the project's linting rules.
  - DO NOT ignore the linting rules. BAD: `if e.resp.status == 404:  # noqa: PLR2004`. GOOD: `if e.resp.status == http.HTTPStatus.NOT_FOUND:`
- Any data loaded from a file or external source (e.g. YAML, TOML, JSON, HTTP) must be validated against a Pydantic model. Never trust outside data.
- Data that is wholly internal to the application should be represented using standard Python classes or dataclasses. Pydantic validation is not necessary.
- I hate using NULL or None as a default value. Avoid this wherever possible. If needed, add a 'default' member of an Enum or similar.
- Use Enums whereever possible. Do not create/pass around 'magic' strings or integers when there is a fixed set of values.
- Functions must never return bare dicts or tuples. Create and use NamedTuples, dataclasses or Python classes whereever possible.
  - NamedTuples are simpler than Dataclasses, which are simpler than Python classes - prefer simpler whereever possible.
  - Strongly prefer to make dataclasses immutable where possible. Use `@dataclass(frozen=True)`
  - Use 'NewType' to create distinct types for dynamic dict key/values. eg BAD `def func() -> dict[str, str]` GOOD `UserId = NewType('UserId', str); Address = NewType('Address', str); def func() -> dict[UserId, Address]`
  - It's OK to use dicts/tuples strictly within the scope of a single function.
- Do not use magic numbers. Instead, go back to first principles for maximum explainability of values. The linter only catches this in a comparison (`PLR2004`) — an assignment like the BAD example below is not flagged, so this one is on you. Example:
  - BAD: `_MIN_COVERAGE_SLOTS = 93`
  - GOOD:
    ```
    _SLOT_LENGTH_MINS = 15
    _SLOTS_PER_DAY = (24 * 60) // _SLOT_LENGTH_MINS
    _MAX_MISSED_SLOTS = 3
    _MIN_COVERAGE_SLOTS = _SLOTS_PER_DAY - _MAX_MISSED_SLOTS
    ```
- Do not leave comments as questions to yourself in the code. Either figure it out or ask me.
- Do not leave comments in the code that are not necessary for understanding the code.
  - The exception is in test code. Copious comments explaining the 'why' are allowed in test code.
- Do not 'number' steps in the code. It's not necessary.

# Running Tests

- Always use `AsyncMock` (not `MagicMock`) when mocking an `async def` function or callback. `MagicMock` silently swallows async/sync mismatches, giving false green tests.

# Checks Architecture

- The justfile is each repo's single source of truth for checks. To add, change or remove one: edit the justfile recipe, then update `.pre-commit-config.yaml` and `.github/workflows/ci.yml` to match — both call `just <recipe>`, never inline command logic.

# Task Tracking

- Use `bd` (beads) for ALL task tracking. Never use TodoWrite, TaskCreate, or a markdown
  TODO list. Create the issue before writing the code, and claim it with
  `bd update <id> --claim` when you start.
- Run `bd prime` when you need the command reference or the session-close protocol; only
  this repo's `bd remember` memories are injected automatically at session start (see
  `agent_rules/hooks.toml`, `[commands.bd-prime]`, for why).
- Use `bd remember` for knowledge that should outlive the session. Do not create MEMORY.md
  or similar files.
- An issue is a description of the work as it now stands, not a diary of how it got there.
  When the shape of the work changes, rewrite the issue so it reads as though it had always
  said the new thing. Never append a delta: no "Update:" paragraphs, no "previously we
  thought...", no struck-through text, no changelog at the bottom. Rewriting *is* the edit,
  not a tidy-up you do afterwards.
  - Why: the next reader acts on the first thing they read. A diary forces them to
    reconstruct the live answer out of a stack of dead ones, and that is exactly how
    information gets lost. Git and `bd` history already hold the deltas -- the body does not
    need to.
  - The only exception: superseded material may stay as an explicit "Alternatives
    considered" note, and only where knowing why it was rejected stops someone proposing it
    again. If it is not doing that job, delete it.
  - This governs the title, description, design, notes and acceptance criteria. Discussion
    comments and close reasons are the one place history legitimately lives: each is written
    once, about a moment, and is chronological by nature. Leave them as written -- and when
    you want to record how the work changed, put that account in the close reason rather
    than back into the body.
- When the deliverable is an issue, the issue is the deliverable: report what changed and
  where, and do not restate its contents back to me.
- Before saying a piece of work is done, close its issue (`bd close <id>`) and file issues
  for anything left over.
- This section and the Committing Code section below are the only statements of this
  policy. If a generated block in some other file disagrees with them, the block is wrong.

# Never Override a Refusal

When a tool refuses to do something, that refusal is information, not an obstacle. Never reach for the flag that silences it. **Stop and ask me instead.** This is not negotiable and it is not a judgement call.

A hook already blocks the concrete cases — `bd --force`, `git push --force`/`-f`/`--force-with-lease`, and `--no-verify` — and denies them with the same reasoning stated here. The same rule applies to anything else that exists to bypass a check, whether or not a hook catches it. If you believe a refusal is genuinely wrong, say so and wait — do not act first and explain afterwards. Explaining after the fact is not asking.

# Committing Code

- You must always use `git add` to stage files before committing. You should never use `git commit -a`.
- **Committing is pre-authorised; pushing is not.** You may commit finished work without asking me first — this repository grants that authority, overriding the Beads block's conservative default. Stage deliberately and commit when a change is complete and its checks pass.
- **Never push.** `git push` is mine alone, every time, no matter how routine the change looks. The same goes for anything else that publishes: creating or updating a PR, pushing tags or notes, and `bd dolt push`. Finish the commit, then tell me what is waiting to go out.
- Committing authority is not a licence to widen scope: commit the work I asked for, not unrelated changes you noticed. Leave untracked files alone unless they are part of that work.
- If a check fails, do not commit. Report the failure — routing around it with `--no-verify` is covered by *Never Override a Refusal* above.

# Conventional Commits

- Commit messages follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/#summary) spec.

# Time and Date

- All time and date usage and calculations MUST be timezone aware. Never create datetimes or similar without explicitly specifying a timezone.
- Timezone-aware is not the same as DST-safe. Arithmetic on an aware datetime is wall-clock
  (preserves local time — the right semantics for calendar and schedule code) only when its
  `tzinfo` is a real zone; a fixed offset makes the identical expression absolute elapsed
  time instead, and the two silently disagree across a DST transition. Decide which one an
  operation needs, and do not let a widened `tzinfo`/`object`/`Any` annotation blur the two —
  a `str` IANA key is fine, but a bare `tzinfo` is not. (Python: enforced by ml-lints
  ML700/ML701; not yet covered for Rust or TypeScript.)

# File Manipulation

- Always tell git what you are doing. For example, when moving a file, always use 'git mv', never bare 'mv'. Also 'git rm' etc.

# Localisation

- You write in Australian English. All spelling, grammar, idioms and style should reflect this. This applies to documentation, commit messages, code comments, variables, API names etc.

<!-- END GLOBAL RULES -->

# Adding a New Lint Rule

To add a new lint rule to this project, follow the guide in [CONTRIBUTING_RULES.md](CONTRIBUTING_RULES.md). Start with:

```sh
just new-rule MLxxx
```

Do not add rule logic directly to any existing file — each rule lives in its own module under `src/ml_lints/rules/`.

# Not Yet Shared

Neither of these is specific to this repo. Both are fleet rules that the
shared block above does not carry yet, kept here so they are not lost.
Tracked in agent_rules ar-0oq; delete them from this file when that lands.

- Use `just precommit` to run all lints, type checking and formatting.
- You MAY surgically ignore PLR0911 (too many returns) and/or PLR0912 (too many branches) ONLY if there is a match/case statement processing an enum with too many members.
