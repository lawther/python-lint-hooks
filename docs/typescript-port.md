# TypeScript port: two-language monorepo

This document is the **specification** for adding a TypeScript implementation of `ml-lints`.
Each task below carries a stable ref (`F1`, `T7`, `RV2`, …) which is also its bead title prefix.
Adversarial reviews bind against it: `/adversarial-review T7 from docs/typescript-port.md`.

## Context

`ml-lints` ships 19 Python rules aimed at optimising AI-agent development — forcing self-documenting code so agents burn fewer tokens re-deriving "wtf is this tuple?". Several rules are not Python-specific: the 500-class (Australian English, hacky pluralisation) are natural-language rules over identifiers, comments and strings, and ML400 has a *higher-value* TypeScript analogue, because `JSON.parse` returns `any` and `any` poisons everything downstream silently.

The goal is a TypeScript implementation that does not fork the project's real asset: the **self-describing contract**. A rule declares `code`/`category`/`summary`/`suggestion`/`bad_example`/`good_examples` plus a docstring rationale, and that metadata is *enforced* — `tests/test_rule_examples.py` asserts every `bad_example` fires its own code and every `good_example` fires zero violations of any rule and passes ruff. It then feeds `--explain`, `docs/rules/*.md` and the README table. That contract must survive into a second language and be cheap to extend to a third.

**Outcome:** one repo, two published artefacts, one shared code space, one doc set, and a machine-checkable guarantee that both implementations agree on what each `ML###` code means.

## Decisions

| | |
|---|---|
| **Topology** | Monorepo, native tooling per language: `packages/py` (PyPI `ml-lints`) + `packages/ts` (npm `@ml-lints/eslint-plugin`, on typescript-eslint). The justfile stays the single source of truth. |
| **Codes** | Shared concept codes. `ML###` names a *concept*; each language implements a subset. No breaking rename. |
| **Contract** | Code is truth. Each package exports a committed `rule-manifest.json`; a conformance test diffs them. |
| **First TS release** | ML500 + ML501 only. |
| **Delivery** | Tracer bullet: naive ML500 driven through *every* layer including a real npm publish, then thickened. |
| **Foundation** | Only the two ML500 blockers precede the tracer. `packages/ts` is built **alongside** `src/ml_lints`; the `packages/py` move comes later. Path rework accepted. |

## There is no shared engine

ESLint already supplies traversal, file discovery, config, suppression, severity and JSON output. So `runner.py`, `noqa.py`, `violation.py` and `cli.py`'s pathspec machinery are **not** shared — TypeScript gets equivalents free. Building a shared engine would mean duplicating ESLint or shipping a standalone CLI, forfeiting the type checker and every editor integration.

| Shared | Not shared (deliberately) |
|---|---|
| `shared/spelling_map.json` | Rule engine / traversal |
| The metadata contract (fields, not implementation) | Suppression syntax (`# noqa:` vs `eslint-disable`) |
| `rule-manifest.json` schema + both manifests | Exemption sets — TypeScript's genuinely differ |
| Conformance test | Examples (per-language by definition) |
| Doc + README generation | Config format (pyproject vs flat config) |
| `ML###` code space, `RuleCategory` vocabulary | |

Two divergences are **declared rather than discovered**: suppression syntax is not unifiable, and the `💡 Tip:` line at `cli.py:478` cannot be reproduced from inside an ESLint plugin, because ESLint owns stdout.

## Delivery shape

Slice 1 goes end to end through every layer with the thinnest possible rule and **ends at a real npm publish**. That puts the nastiest external unknown (npm scope plus OIDC trusted publishing, which unlike PyPI has no "pending publisher" — the trusted publisher must be configured against an *existing* package) at the point where a rollback costs nothing. Everything after lands on a live spine.

```
E0 design gate ──► E1 foundation ──► E2 TRACER (naive ML500 → npm 0.0.1) ──┬──► E3 thicken
                                                                             ├──► E4 monorepo ──► E5 release
                                                                             └──► E6 authoring
```

## Adversarial review gates

Gates were selected on one criterion: **the work can pass CI while proving nothing.**

| Gate | Reviews | Instrument | Then unblocks |
|---|---|---|---|
| RV0 | This document | `/adversarial-design-review` | F1, F2, T1, T4 |
| RV1 | T1 manifest schema | `/adversarial-design-review` | T3, T6 |
| RV2 | T7 example harness | `/adversarial-review` | T10, K1, K2 |
| RV3 | T8 conformance gate | `/adversarial-review` | A1 |
| RV4 | K1 exemption set | `/adversarial-review` | K3 |
| RV5 | M2 monorepo move | `/adversarial-review` | M3, R1, A1 |

RV0 and RV1 use the **design** instrument because neither artefact has a spec above it — a plan and a JSON schema *are* specs, and their decomposition is the deliverable. Dependents are rewired off the original and onto its gate, so nothing downstream starts until the gate clears.

Reviews are **handoff points**: the commands are user-invoked. On REJECT the commands are review-only, so the fix plan becomes new beads that **block the review bead**, which stays open until re-run and accepted.

---

# Tasks

## E0 · Design gate

### RV0 · Adversarial design review of this document
Run `/adversarial-design-review docs/typescript-port.md`.
**Acceptance:** verdict recorded. Framework-level findings resolved or explicitly accepted before F1/F2/T1/T4 begin.

## E1 · Foundation

### F1 · Lowercase the dead capitalised spelling-map keys
Six of 1763 keys are capitalised (`Africanization`, `Africanize`, `Americanization`, `Americanize`, `Arabize`, `Finlandization`) but `_check_text` and `_check_name` look up `.lower()` — unreachable dead data today. Fix now, or Python and TypeScript each guess a normalisation and diverge for reasons the conformance test cannot see, since it diffs metadata rather than data.
**Acceptance:** all keys lowercase; a test asserts no key differs from its own `.lower()`; ML500 now flags `Americanize`.

### F2 · ML500 raises on a missing or empty spelling map
`ml500_australian_english.py:56-60` assigns `{}` when the map is absent, so a packaging regression yields zero violations and every negative test still passes. This is exactly the failure mode T2's vendoring introduces.
**Acceptance:** a missing map raises; a test asserts `len(spelling_map) > 1000`; deleting the map makes the suite fail loudly.

## E2 · Tracer bullet

Naive ML500 means spelling-map lookup over identifiers and comments, with **no exemption logic**. The slice ends publishable.

### T1 · Manifest JSON schema, Pydantic model and categories.json
`shared/schema/rule-manifest.schema.json` plus `scripts/manifest_model.py` (GEMINI.md mandates Pydantic for file-loaded data) plus `shared/categories.json`.

Per rule: `code`, `category`, `summary`, `suggestion`, `rationale`, `exemptions?`, `badExample`, `goodExamples`, `docUrl`. Envelope: `manifestVersion`, `language` (closed enum), `package`, `version`.

Deliberately out of v1: message templates, severity, fixability. `manifestVersion` exists so they can be added later.

**Acceptance:** rules sorted by code; serialised with `indent=2, sort_keys=True` and a trailing newline, because byte-stability is what makes `--check` work. Schema validates a hand-written ML500 example. Must survive the question *"what breaks when Rust is added"*.

### RV1 · Design review: manifest schema
Run `/adversarial-design-review` on T1's schema.
**Acceptance:** verdict recorded before T3 and T6 encode the schema.

### T2 · shared/ directory, sync script and justfile wiring
A wheel and an npm tarball must each *contain* the spelling map; neither can reach `../../shared/` after install. Symlinks are unreliable on Windows and in `npm pack`. Hatchling `force-include` of `../../` breaks `uv build --sdist` and editable installs.

So `shared/spelling_map.json` is truth, vendored copies are **committed** into each package, and `scripts/sync_shared.py` copies with a `--check` mode. `precommit` syncs and auto-stages, reusing the existing `README.md`/`docs` pattern; `just ci` runs `--check`.

**Acceptance:** hand-editing a vendored copy fails `just ci`. A fresh `git clone` runs the suite with no build step.

### T3 · Python manifest export
`ml-lints --list-rules --format json [--out PATH] [--check PATH]`, mirroring `generate_rule_docs.py`'s `--check` semantics. Extend the CLI rather than adding a script: the installed artefact should be interrogable (`uvx ml-lints --list-rules --format json`), which is the same self-describing thesis as `--explain`.
**Acceptance:** `packages/py/rule-manifest.json` committed and byte-stable across runs; `--check` fails on drift.

### T4 · packages/ts skeleton
`package.json`, `tsconfig.json`, `createRule` helper, flat-config `recommended` preset, `index.ts` with the two scaffolding sentinels.

Rule ID is the bare code (`@ml-lints/ML500`) so `RuleCreator`'s `urlCreator` generates the doc URL mechanically. `summary` maps to the **standard** `meta.docs.description` field, so `eslint-plugin/require-meta-docs-description` enforces its presence for free.

**Acceptance:** `npx eslint` loads the plugin. Confirm whether `eslint-plugin-eslint-plugin` objects to non-kebab rule names, and record the answer.

### T5 · TypeScript ML500, naive
Spelling-map lookup over identifiers and comments via `sourceCode.getAllComments()`. **No exemption logic** — that is K1.
**Acceptance:** flags `const color = 1`; reports through `meta.messages`, not a hardcoded string.

### T6 · TypeScript manifest emitter and explain bin
`ml-lints-ts rules [--format json] [--out F] [--check F]` and `ml-lints-ts explain ML500`, the latter printing the same layout as `cli.py:_explain_rule` so agent muscle memory transfers.
**Acceptance:** `packages/ts/rule-manifest.json` committed; `npx @ml-lints/eslint-plugin explain ML500` works with no install.

### T7 · TypeScript example-verification test
The port of the enforced self-describing contract.

Bad examples use `new Linter().verify()` asserting `>= 1`, **not `RuleTester`**, which demands exact error counts — Python asserts `>= 1`, and ML500's bad example fires three times. Reserve `RuleTester` for hand-written per-rule tests where exact counts are the point.

Good examples: run all plugin rules in-process asserting zero, then `eslint:recommended` plus `@typescript-eslint/recommended` as the honest analogue of Python's `ruff check` subprocess.

**Acceptance:** must demonstrably **fail** when the plugin rule set is emptied, and when a `badExample` is edited to lint clean. A harness that cannot fail is the defect this task exists to prevent.

### RV2 · Review: example harness
Run `/adversarial-review T7 from docs/typescript-port.md`.
**Acceptance:** reviewer confirms both falsification cases above actually fail.

### T8 · Conformance test
Lives at `shared/conformance/`, reads **only the two committed JSON files**, so it needs neither toolchain.

Drift-checked: `category`, `summary`, `suggestion`. Not drift-checked: `exemptions` (TypeScript's differ by design), examples, `docUrl`, `rationale` — the last required non-empty on both, but Python's ML500 rationale discusses import machinery with no TypeScript analogue.

Also checked: every category ∈ `categories.json`; no duplicate codes; every code matches `^ML\d{3}$`; every code has a `docs/rules/<CODE>.md`; `docUrl` matches the canonical template exactly, or ESLint's `meta.docs.url` 404s silently.

Do **not** assert TypeScript ⊆ Python — that would block a future TypeScript-only rule.

**Acceptance:** must demonstrably **fail** when a shared code's summary is altered in one manifest, and when a category is misspelt `localization`. Failure messages quote both sides verbatim.

### RV3 · Review: conformance gate
Run `/adversarial-review T8 from docs/typescript-port.md`.
**Acceptance:** reviewer confirms the gate bites on deliberately injected drift.

### T9 · Dual-language doc and README generation
Both generators stop importing `ml_lints` and read the two committed manifests. The generator stays Python: a TypeScript generator would make `just docs-rules` require node, blocking a Python-only contributor.
**Acceptance:** when only one language implements a code, omit the language headings and render exactly today's layout — **17 of 19 doc files must come out byte-identical**. That is the correctness proof for the rewrite.

### T10 · Node in CI and a non-mutating ci gate
Today `just lint` runs mutating `ruff format` and `ruff check --fix` before `just test`, and `precommit` regenerates docs then `git add`s them, so CI cannot fail on formatting or doc drift and `check-rules-docs` is dead code.
**Acceptance:** `just ci` fails on unformatted code, stale docs, drifted vendored data and manifest drift. Verified precondition: docs are currently in sync and `ruff format --check` is clean, so enabling this causes no fallout today.

### T11 · npm publish 0.0.1 and trusted publishing
Confirm the `@ml-lints` scope is available **first**. Set `"publishConfig": {"access": "public", "provenance": true}`. Publish 0.0.1 with a short-lived granular token, configure OIDC trusted publishing against the now-existing package, then delete the token.
**Acceptance:** `npm i @ml-lints/eslint-plugin` in a scratch project lints a `.ts` file and reports `@ml-lints/ML500` with a resolving doc URL. The tarball contains the vendored spelling map.

## E3 · Thicken

### K1 · TypeScript ML500 exemption set
TypeScript must **not** attempt Python's `_BASE_METHODS_CACHE`; importing third-party modules at lint time has no safe TypeScript analogue. Instead: imported identifiers, member expressions, object-literal keys, JSX attribute names, non-JSDoc string literals. These differ from Python's by design, which is why `exemptions` is not drift-checked. Later, `parserServices` gives *better* override detection than Python's runtime-import hack.
**Acceptance:** each exemption has a paired positive test proving the rule still fires on the un-exempt form. An over-broad exemption silently guts ML500 without failing anything, so the paired test is mandatory, not optional.

### RV4 · Review: exemption set
Run `/adversarial-review K1 from docs/typescript-port.md`.
**Acceptance:** reviewer confirms every exemption has a paired positive test and none is broader than specified.

### K2 · TypeScript ML501
Hacky pluralisation. "Skip docstrings" becomes "skip JSDoc".
**Acceptance:** catches `version(s)`; ignores JSDoc.

### K3 · Publish 0.1.0
Complete ML500 plus ML501.
**Acceptance:** published; docs show both languages for ML500 and ML501.

> **Note:** ML500 and ML501 are lexical, so nothing up to K3 exercises the type checker. Type-aware linting needs `parserOptions.projectService`, which is awkward for in-memory snippets. Configure non-type-aware and defer that plumbing to the first rule that needs it (the ML100 family). The topology decision's "we get the real type checker" claim is therefore **unverified** until then.

## E4 · Monorepo symmetry

Deliberately scheduled *after* the spine flies, which accepts the path rework this ordering creates.

### M1 · Coverage floor and cache-reset fixture
The safety net for M2, so it lands first. There is no coverage floor today, so if the move breaks module resolution coverage silently drops to 0% and CI stays green. `pytest-randomly` plus ML500's class-level mutable caches (`_SPELLING_MAP`, `_BASE_METHODS_CACHE`) is the highest-probability silent failure in this plan.
**Acceptance:** `--cov-fail-under` set at the current measured value minus two points; autouse fixture resets both caches; suite green across at least three random seeds.

### M2 · Move the Python package into packages/py
`git mv src/ tests/` into `packages/py/`, plus `scripts/branch_summary.py` and `pyproject.toml`. Root becomes a uv virtual workspace with **ruff config at root only**, since a `[tool.ruff]` in the package would shadow it. Per-file-ignores need `**/` prefixes to survive this and any future move. Use just's `[working-directory]` attribute (just 1.58.0 installed; needs 1.38+) rather than `cd`, which sidesteps the `_lint-justfile` ban on `&&` chains.
**Acceptance:** `git diff -M --stat` is substantially renames. Must prove a deliberate `S101` in `src/` still fails ruff, and that coverage still measures `ml_lints` rather than silently reporting nothing — over-matching globs silently *disable* checks. `ty check` resolving `ml_lints` from the workspace root is the least certain item; verify empirically, with a `[working-directory]`-scoped recipe as fallback.

### RV5 · Review: monorepo move
Run `/adversarial-review M2 from docs/typescript-port.md`.
**Acceptance:** reviewer independently confirms the `S101` and coverage checks above, rather than accepting the suite being green.

### M3 · scripts/ path audit
`scripts/` **stays at root**: `generate_rule_docs.py:110` and `generate_rules_table.py:44` resolve `Path(__file__).parent.parent / "docs"` and `/ "README.md"`. Moving them would silently write to `packages/py/docs/` instead of failing. Drop both `sys.path.insert` hacks, which the workspace makes unnecessary.
**Acceptance:** generators run from the repo root and write to the root `docs/` and `README.md`.

## E5 · Release automation

### R1 · release-please multi-package config
Independent versions: Python continues from 0.13.0, TypeScript from wherever E3 leaves it. `separate-pull-requests: true`, components `ml-lints` and `eslint-plugin`.
**Acceptance:** a throwaway `feat:` PR produces a correct proposed release PR, inspected before merging.

### R2 · Lockfile matrix and publish gating
`update-lockfile` silently stops working: it hardcodes `ref: release-please--branches--main`, which becomes `…--components--ml-lints`. Gate publish jobs on `paths_released`, not the singular `tag_name`/`pr` outputs. The uv workspace pays off here — one root `uv.lock`, so `uv lock` stays a single unconditional command.
**Acceptance:** both packages' release PRs get their lockfiles updated; publishing a Python release does not publish npm.

### R3 · Announce the tag-scheme change
**Most user-visible break in this plan:** tags become `ml-lints-v0.14.0` instead of `v0.13.0`, breaking the README's "pin to a specific tag" guidance and any downstream `git+https://…@v0.13.0` pin.
**Acceptance:** README updated; the change called out in release notes.

## E6 · Authoring ergonomics

### A1 · Language-aware rule scaffolding
`just new-rule ML150 [py|ts]`, defaulting to `py` so existing muscle memory and GEMINI.md's documented invocation keep working. Move logic out of the inline `python3 -c` at `justfile:101` into a testable `scripts/scaffold_rule.py`; TypeScript needs two sentinels, which would double an already-maxed-out one-liner.

**Used-code set is the union of the committed manifests** — no separate registry file. **Next-free must be per-block, not per-category:** the 1xx block hosts three categories (`return-types` ML100-107, `type-hygiene` ML108-109, `parameter-types` ML110), so a global next-free would hand out ML111 for a testing rule.

**Acceptance:** scaffolding a code that exists in the *other* language prints its category, summary and suggestion so the author copies them verbatim, which turns T8 from a nag into a rarely-firing backstop.

### A2 · Documentation
`CONTRIBUTING_RULES.md`, `GEMINI.md`, `README.md`. Includes fixing `GEMINI.md:40,44`, which references a `.pre-commit-config.yaml` that does not exist — the real hook is `.githooks/pre-commit` calling `just precommit`.
**Acceptance:** a fresh clone runs `just setup-dev && just ci` green with no manual steps, per GEMINI.md's requirement that no step relies on the developer remembering it.

---

## Accepted rework

Building `packages/ts` alongside `src/ml_lints` means E4 rewrites justfile paths, ruff globs and CI wiring that E2 will have just written. That is the deliberate cost of flying the spine first.
