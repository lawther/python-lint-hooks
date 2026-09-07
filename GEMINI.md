<!-- BEGIN GLOBAL RULES sha256:c9c4c18fdb8efe1b -->
<!-- Generated from agent_rules/global.md. Do not edit inside this block:
     edit global.md, then run `just sync-rules` in agent_rules. -->

# Automation

- NEVER rely on manual steps (for example, the developer must remember to run a code generator after updating an API). If a step is required, add it to the `justfile`.

# Python Code Style

- All code must be type-hinted.
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
- Do not use magic numbers. Instead, go back to first principles for maximum explainability of values. Example:
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

The **justfile is the single source of truth** for all check commands. Pre-commit hooks and CI are both thin wrappers that call the same justfile recipes — there is no logic duplicated between them.

- **Local (pre-commit)**: hooks in `.pre-commit-config.yaml` call `just <recipe>` and fire on relevant file changes
- **CI** (`.github/workflows/ci.yml`): calls `just <recipe>` steps directly — no pre-commit involved
- **Manually**: `just lint`, `just test`, or an individual recipe

**If you need to add, change, or remove a check: edit the justfile recipe.** Then update `.pre-commit-config.yaml` (add/remove a hook entry) and `.github/workflows/ci.yml` (add/remove a `run: just <recipe>` step) to match. Never put command logic in the hook `entry:` or the CI `run:` — only `just <recipe>` calls belong there.

# Task Tracking

- Use `bd` (beads) for ALL task tracking. Never use TodoWrite, TaskCreate, or a markdown
  TODO list. Create the issue before writing the code, and claim it with
  `bd update <id> --claim` when you start.
- Run `bd prime` when you need the command reference or the session-close protocol. It is
  not injected at session start: the SessionStart hook runs `bd prime --memories-only`,
  which carries this repo's `bd remember` memories and nothing else. That is deliberate --
  bd's full output asserts a "Conservative" git policy that contradicts the Committing Code
  section below, and pinning the hook is the only place it can be corrected. See
  agent_rules/hooks.toml, `[commands.bd-prime]`.
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

- **`bd ... --force`** — a blocked `bd` operation means the dependency graph says the work is not finishable yet. The error text says "use --force to override"; that describes a mechanism, it does not grant permission. Ask me whether the dependency is wrong.
- **`git push --force` / `-f` / `--force-with-lease`** — rewriting published history is my call, never yours.
- **`--no-verify`** — a failing precommit gate is a finding to report to me, not something to route around.

The same rule applies to anything else that exists to bypass a check, whether or not it is listed here. If you believe the refusal is genuinely wrong, say so and wait — do not act first and explain afterwards. Explaining after the fact is not asking.

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
