# Coding Conventions

- I hate using NULL or None as a default value. Avoid this wherever possible. If needed, add a 'default' member of an Enum or similar.
- NEVER rely on manual steps (for example, the developer must remember run a code generator after updating an API). If a step is required, add it to the `justfile`.

# Python Code Style

- All code must be type-hinted.
- All code must pass the project's linting rules.
  - Use `just precommit` to run all lints, type checking and formatting.
  - DO NOT ignore the linting rules. BAD: if e.resp.status == 404:  # noqa: PLR2004. GOOD: if e.resp.status == http.HTTPStatus.NOT_FOUND:
  - You MAY surgically ignore PLR0192 (too many branches) ONLY if there is a match/case statement processing an enum with too many members.
- Any data loaded from a file or external source (e.g. YAML, TOML, JSON, HTTP) must be validated against a Pydantic model. Never trust outside data.
- Data that is wholly internal to the application should be represented using standard Python classes or dataclasses. Pydantic validation is not necessary.
- Use Enums whereever possible. Do not create/pass around 'magic' strings or integers when there is a fixed set of values.
- Functions must never return bare dicts or tuples. Create and use NamedTuples, dataclasses or Python classes whereever possible.
  - NamedTuples are simpler than Dataclasses, which are simpler than Python classes - prefer simpler whereever possible.
  - Strongly prefer to make dataclasses immutable where possible. Use @dataclass(frozen=True)
  - Use 'NewType' to create distinct types for dynamic dict key/values. eg BAD def func() -> dict[str, str] GOOD UserId = NewType('UserId', str); Address = NewType('Address', str); def func() -> dict[UserId, Address]
  - It's OK to use dicts/tuples strictly within the scope of a single function.
- Do not leave comments as questions to yourself in the code. Either figure it out or ask me.
- Do not leave comments in the code that are not necessary for understanding the code.
   - The exception is in test code. Copious comments explaining the 'why' are allowed in test code.
- Do not 'number' steps in the code. It's not necessary.

# Adding a New Lint Rule

To add a new lint rule to this project, follow the guide in [CONTRIBUTING_RULES.md](CONTRIBUTING_RULES.md). Start with:

```sh
just new-rule MLxxx
```

Do not add rule logic directly to any existing file — each rule lives in its own module under `src/python_lint_hooks/rules/`.

# Checks Architecture

The **justfile is the single source of truth** for all check commands. Pre-commit hooks and CI are both thin wrappers that call the same justfile recipes — there is no logic duplicated between them.

- **Local (pre-commit)**: hooks in `.pre-commit-config.yaml` call `just <recipe>` and fire on relevant file changes
- **CI** (`.github/workflows/ci.yml`): calls `just <recipe>` steps directly — no pre-commit involved
- **Manually**: `just lint`, `just test`, or individual recipes like `just lint-api`

**If you need to add, change, or remove a check: edit the justfile recipe.** Then update `.pre-commit-config.yaml` (add/remove a hook entry) and `.github/workflows/ci.yml` (add/remove a `run: just <recipe>` step) to match. Never put command logic in the hook `entry:` or the CI `run:` — only `just <recipe>` calls belong there.

# Committing Code

- You must always use `git add` to stage files before committing. You should never use `git commit -a`.

# Time and Date

- All time and date usage and calculations MUST be timezone aware. Never create datetimes or similar without explicitly specifying a timezone.

# File Manipulation

- Always tell git what you are doing. For example, when moving a file, always use 'git mv', never bare 'mv'. Also 'git rm' etc.

# Conventional Commits

- Commit messages follow the (Conventional Commits)[https://www.conventionalcommits.org/en/v1.0.0/#summary] spec.

# Localisation

- You write in Australian English. All spelling, grammar, idioms and style should reflect this. This applies to documentation, commit messages, code comments, variables, API names etc.
