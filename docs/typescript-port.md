# TypeScript port: two-language monorepo

This document is the **specification** for adding a TypeScript implementation of `ml-lints`.
Each task below carries a stable ref (`F1`, `T7`, `RV2`, …) which is also its bead title prefix.
Adversarial reviews bind against it: `/adversarial-review T7 from docs/typescript-port.md`.

## Context

`ml-lints` ships 19 Python rules aimed at optimising AI-agent development — forcing self-documenting code so agents burn fewer tokens re-deriving "wtf is this tuple?". Several rules are not Python-specific: the 500-class (Australian English, hacky pluralisation) are natural-language rules over identifiers, comments and strings, and ML400 has a *higher-value* TypeScript analogue, because `JSON.parse` returns `any` and `any` poisons everything downstream silently.

The goal is a TypeScript implementation that does not fork the project's real asset: the **self-describing contract**. A rule declares `code`/`category`/`summary`/`suggestion`/`bad_example`/`good_examples` plus a docstring rationale, and that metadata is *enforced* — `tests/test_rule_examples.py` asserts every `bad_example` fires its own code and every `good_example` fires zero violations of any rule and passes ruff. It then feeds `--explain`, `docs/rules/*.md` and the README table. That contract must survive into a second language and be cheap to extend to a third.

**Outcome:** one repo, two published artefacts, one shared code space, one doc set, and a machine-checkable guarantee that both implementations agree on what each `ML###` code means — in metadata *and* in behaviour. Those are separate gates, because agreeing on the words is not agreeing on the answers.

## Decisions

| | |
|---|---|
| **Topology** | Monorepo, native tooling per language: `packages/py` (PyPI `ml-lints`) + `packages/ts` (npm `@ml-lints/eslint-plugin`, on typescript-eslint). The justfile stays the single source of truth. |
| **Codes** | Shared concept codes. `ML###` names a *concept*; each language implements a subset. No breaking rename. The concept is a literal manifest field (T1) and is the thing the conformance gate diffs; `summary`/`suggestion` are per-language phrasing and are deliberately not diffed. |
| **Contract** | Code is truth. Each package exports a committed `rule-manifest.json`; a metadata gate diffs them, and a fixture corpus pins behaviour. Metadata agreement is not behavioural agreement — see *Behavioural conformance*. |
| **First TS release** | ML500 + ML501 only. |
| **Delivery** | Tracer bullet: naive ML500 driven through *every* layer including a real npm publish, then thickened. |
| **Foundation** | Foundation stays thin: the two ML500 blockers plus the F4 `id` rename that T3 depends on. `packages/ts` is built **alongside** `src/ml_lints`; the `packages/py` move comes later. Path rework accepted. |

## There is no shared engine

ESLint already supplies traversal, file discovery, config, suppression, severity and JSON output. So `runner.py`, `noqa.py`, `violation.py` and `cli.py`'s pathspec machinery are **not** shared — TypeScript gets equivalents free. Building a shared engine would mean duplicating ESLint or shipping a standalone CLI, forfeiting the type checker and every editor integration.

| Shared | Not shared (deliberately) |
|---|---|
| `shared/spelling_map.json` | Rule engine / traversal |
| The metadata contract (fields, not implementation) | Suppression syntax (`# noqa:` vs `eslint-disable`) |
| `rule-manifest.json` schema + both manifests | Exemption sets — TypeScript's genuinely differ |
| Metadata conformance gate | Examples (per-language by definition) |
| Behavioural conformance: the scenario catalogue and the answer keys | Fixture realisations — per-language source by definition |
| Doc + README generation | Config format (pyproject vs flat config) |
| `ML###` code space, `RuleCategory` vocabulary | `summary`/`suggestion` phrasing — most rules name one language's constructs |
| The `concept` text behind each `ML###`, and each rule's `messageIds` | Message wording — only the ids and any declared neutral data are shared |

Four divergences are **declared rather than discovered**: suppression syntax is not unifiable; the `💡 Tip:` line at `cli.py:478` cannot be reproduced from inside an ESLint plugin, because ESLint owns stdout; `summary`/`suggestion` wording, which names the constructs of the language it is advising about (see T1); and the rendered text of a violation message, of which only the `messageId` and any declared neutral data are shared (see *Behavioural conformance*).

## Behavioural conformance

Agreeing on the manifest is not agreeing on the answers. Both manifests can carry a byte-identical `concept` for ML500 while the two implementations split identifiers differently, restore case differently, scan different spans and report different things — and a gate that reads only the manifests calls that conformance. ML500's meaning mostly does not live in the manifest or in `spelling_map.json`; it lives in `WORDS_RE` (`ml500_australian_english.py:46`), `_match_case` (`:70-81`), the URL-span skip (`:85`), the dotted-name skip (`:89`), and the docstring-versus-string-literal split.

Behaviour is therefore pinned by fixtures, in two tiers. **Tier 1 applies to every rule.** **Tier 2 is opt-in**, and qualifies only where a rule's meaning is a transformation of a text span so that both languages can consume the same input — true of ML500 and ML501, false of ML400.

Both tiers drive the **real linter end to end**, never a rule-internal helper. A helper-level corpus would pin a private API in both languages, and for a structural rule there is no helper to call.

### Tier 1 · Scenario catalogue

The shared artefact is the *situation*, not the source. `shared/conformance/scenarios.json` names each situation, its polarity, and the languages that claim it:

```json
{ "code": "ML400",
  "scenario": "external-data-used-unvalidated",
  "polarity": "must-fire",
  "languages": ["python", "typescript"],
  "describes": "A value read from an external source reaches a use without passing through a declared schema." }
```

Each claiming language commits its own realisation at `packages/<lang>/conformance/<ID>.json`: source in that language plus the exact findings expected from it — `line`, `col`, `id`, `messageId`, `data` — sorted by position. ML400's two realisations share no bytes (`json.load` and Pydantic on one side, `JSON.parse` and Zod on the other) yet answer the same question, which is the thing that cannot otherwise be checked. **This is why the shared unit is the scenario and not the source**: a format built around shared input would cover the 500-class and nothing else, which is the failure mode `summary` had.

The gate fails when a claimed scenario has no realisation, when a realisation names a scenario absent from the catalogue, when the findings do not match exactly, and when a code implemented by both languages lacks a must-fire *and* a must-not-fire scenario claimed by both. That last check is what stops a language claiming a code on the strength of one positive case.

### Tier 2 · Answer key

Tier 1 compares polarity only, because the two languages run different source. For ML500 that is not enough: `my_favorite_color → my_favourite_colour` and `myFavoriteColor → myFavoriteColour` both count as "fires", and the two splitters disagree unnoticed.

Where the input can be a shared string, the rule adds an answer key at `shared/conformance/answers/<ID>.json` — one input, one expected result, both implementations graded against it rather than against each other's yes/no:

```json
{ "case": "camel-case-two-words",
  "kind": "identifier",
  "input": "myFavoriteColor",
  "expected": [{ "offset": 0,
                 "messageId": "useAustralianEnglish",
                 "data": { "found": "myFavoriteColor", "suggestion": "myFavouriteColour" } }] }
```

`kind` is one of `identifier`, `comment`, `doc`, `plainString`. Each language ships a small adapter that wraps `input` into a real construct of that kind, runs the linter over it, and maps each reported position back to an offset within `input`. The adapter is the only per-language code in this tier, and it is itself pinned: at least one case must expect a non-zero offset, so an adapter that returns a constant fails.

Offsets are 0-based within `input`. Tier 1's `line`/`col` are 1-based in the source, matching what both linters already emit. An input must be valid in every language the answer key claims.

### Message identity

`messageIds` is a manifest field (T1): the sorted, non-empty set of message identifiers a rule can emit, diffed byte-identically by the metadata gate for any code both languages implement. Message *templates* stay out of v1 as T1 says — sharing the identifiers alone is what stops a language quietly reporting a code under a different message identity.

A rule may additionally declare `neutralData`, the data keys whose values are language-neutral. ML500 declares `["found", "suggestion"]`. ML400 declares none, because its payload names Pydantic on one side and Zod on the other. Declared keys are compared inside the answer key, where a shared input makes the comparison meaningful; tier 1 asserts `data` against each language's own realisation and never across languages.

The rendered sentence is never compared, in either tier. Python has no message-id concept today, so **F5** adds one.

### Scope for v1

Pinned for naive ML500, in one tier or both:

- which spans are scanned — identifiers (bindings, references, parameters, function and class names), comments and doc comments; plain string literals are **not**
- identifier word-splitting, including camelCase, snake_case and kebab-case boundaries and digit runs
- case restoration per replaced part: ALL CAPS → ALL CAPS, Title → Title, otherwise lower
- one finding per identifier, carrying the whole reconstructed name as its suggestion
- one finding per offending word in free text, each at its own position, including across newlines
- URL spans and dotted names skipped in free text
- the rule `id`, the `messageId`, and the `found` / `suggestion` data values

**Accepted divergences**, stated so they are not mistaken for oversights:

- **exemption sets** — K1's differ by design; the corpus is naive ML500 and exercises none
- **suppression syntax** — no fixture carries `# noqa:` or `eslint-disable`
- **the rendered message sentence** — only the id and the declared neutral data are compared
- **severity and fixability** — already deferred by T1
- **file discovery and configuration** — ESLint's, not ours
- **non-ASCII identifiers and text** — unspecified in both implementations; out of scope until a rule needs them

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
| RV3 | T8 **and** T12 — both conformance gates | `/adversarial-review` ×2 | A1 |
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

### F4 · Rename `Rule.code` to `Rule.id` across the Python package
The manifest field is `id` (T1). Renaming the Python side keeps one word everywhere instead of a permanent seam. Covers the `RuleCode` StrEnum (→ `RuleId`), `Violation.code`, the `Rule.code` `ClassVar` and its 19 assignments, `has_noqa`'s parameter, both rule templates, both generators, and the README / CONTRIBUTING_RULES prose.

**Untouched**, because they carry the *value* rather than the field name: the `# noqa: ML100` suppression syntax and `Violation.format`'s `path:line:col: ML100 message` output. Renaming those would be a user-visible break for no gain.

`justfile:101`'s inline `python3 -c` hardcodes the `violation.py` sentinel and prints `RuleCode.<code>`, so it moves in lockstep; A1 extracts that same one-liner into `scripts/scaffold_rule.py`, and whichever lands second rebases onto the first.

**Acceptance:** grep finds no rule-identifier `code` left in `src/`, `scripts/` or `tests/`. `just new-rule ML999` still scaffolds a working rule and injects the enum member. Suppression syntax and output format byte-unchanged, asserted by test. Lands **before T3**, so the emitter reads `rule.id` with no mapping line.

### F5 · Structured reporting and message ids in Python
`messageIds` is a manifest field (T1) and the conformance corpus asserts a `messageId` and a `data` payload per finding, so Python must report structurally instead of pre-formatting a sentence at the call site. `report()` gains a message-id-plus-data form and each rule declares the ids it can emit. Wide but shallow: 20 `self.report` call sites plus ML400's direct `Violation` construction, and 17 of 19 rules emit exactly one message.

**Untouched:** `Violation.format`'s `path:line:col: ML100 message` output. The rendered sentence is still what users see — it is now produced from the id and the data rather than passed in.

**Acceptance:** every rule declares a non-empty `messageIds`, asserted by a test rather than left to review. Rendered output byte-unchanged for every rule's `bad_example`, asserted by test. Lands **before T3**, which serialises the field.

## E2 · Tracer bullet

Naive ML500 means spelling-map lookup over identifiers and comments, with **no exemption logic**. The slice ends publishable.

### T1 · Manifest JSON schema, Pydantic model and categories.json
`shared/schema/rule-manifest.schema.json` plus `scripts/manifest_model.py` (GEMINI.md mandates Pydantic for file-loaded data) plus `shared/categories.json`.

Per rule: `id`, `category`, `concept`, `summary`, `suggestion`, `rationale`, `messageIds`, `neutralData?`, `exemptions?`, `badExample`, `goodExamples`, `docUrl`. Envelope: `manifestVersion`, `language` (closed enum), `package`, `version`.

Deliberately out of v1: message *templates*, severity, fixability. `manifestVersion` exists so they can be added later. The message **identifiers** are in — they are cheap to share and they are what stops a language reporting a code under a different message identity; see *Behavioural conformance* for `messageIds` and `neutralData`, and **F5** for the Python side.

#### `concept` versus `summary`/`suggestion`

`concept` states what the code *means*, naming no language's constructs. It MUST be byte-identical in every manifest that implements the code — it is what "`ML###` names a concept" is cashed out as, and it is the only rule text T8 diffs.

`summary` and `suggestion` are **presentation**: one language's phrasing of the symptom and of the remedy. They name that language's constructs, and mostly cannot match. Of the 19 current rules only four (ML201, ML300, ML500, ML501) have summaries that could be byte-identical across languages; the other 15 name `NamedTuple`, `NewType`, `Mapping`, `dataclass(frozen=True)`, `dataclasses.replace`, Pydantic or `patch(new=Mock())`. A gate that diffs `summary` therefore looks healthy for exactly as long as the tracer lasts — ML500 and ML501 are two of the four — and breaks on the third rule ported, which the note after K3 nominates as ML400 or the ML100 family. Both are in the un-shareable set. `concept` is the field that stays writable for all 19.

The field is `id`, not `code`. ESLint's own word for `@ml-lints/ML500` is the rule *ID*, and inside a manifest entry `code` collides with `badExample`/`goodExamples`, which hold literal source code. Python's `Rule.code` / `RuleCode` / `Violation.code` are renamed to match in **F4** rather than mapped at the emitter boundary, so one word holds across both implementations and the shared artefact.

Sourcing: Python declares `concept` as a `ClassVar` beside `summary`; TypeScript as `meta.docs.concept`. `summary` continues to map to the standard `meta.docs.description` (T4), which is *why* it cannot also carry the concept — that field is what editors surface and what `eslint-plugin/require-meta-docs-description` polices, so it has to read as advice to a TypeScript author.

`concept` is not user-facing. Violation messages, `--explain` and the per-language doc sections keep using `summary`/`suggestion`, so T9's byte-identical doc requirement is unaffected.

#### Worked examples

**ML100** — category `return-types`. `concept` (must match, both manifests): *"Function returns an unstructured key-value mapping instead of a named type with declared fields"*.

| | Python | TypeScript |
|---|---|---|
| `summary` | Function returns a bare `dict` | Function returns a bare `Record` |
| `suggestion` | Use a dataclass instead | Use an interface with named fields instead |

**ML400** — category `data-trust`. `concept` (must match, both manifests): *"Data from an external source is used without being validated against a declared schema"*.

| | Python | TypeScript |
|---|---|---|
| `summary` | Unvalidated external data used without Pydantic validation | `JSON.parse` result used without schema validation |
| `suggestion` | Validate with a Pydantic model before use | Validate with a Zod schema before use |

Both are rules whose remedy genuinely differs by language, and in both the shared field is writable without strain. Neither TypeScript rule is scheduled here — these examples exist to show the split holds outside the four rules that happen to share wording, not to commit to a port order.

**Acceptance:** rules sorted by code; serialised with `indent=2, sort_keys=True` and a trailing newline, because byte-stability is what makes `--check` work. `concept`, `summary`, `suggestion` and `messageIds` are all required and non-empty, and `messageIds` is sorted. Schema validates a hand-written ML500 example, plus the ML400 and ML100 pairs above. Must survive the question *"what breaks when Rust is added"*.

### RV1 · Design review: manifest schema
Run `/adversarial-design-review` on T1's schema.
**Acceptance:** verdict recorded before T3 and T6 encode the schema.

### T2 · shared/ directory, sync script and justfile wiring
A wheel and an npm tarball must each *contain* the spelling map; neither can reach `../../shared/` after install. Symlinks are unreliable on Windows and in `npm pack`. Hatchling `force-include` of `../../` breaks `uv build --sdist` and editable installs.

So `shared/spelling_map.json` is truth, vendored copies are **committed** into each package, and `scripts/sync_shared.py` copies with a `--check` mode. `precommit` syncs and auto-stages, reusing the existing `README.md`/`docs` pattern; `just ci` runs `--check`.

**Acceptance:** hand-editing a vendored copy fails `just ci`. A fresh `git clone` runs the suite with no build step.

### T3 · Python manifest export
`ml-lints --list-rules --format json [--out PATH] [--check PATH]`, mirroring `generate_rule_docs.py`'s `--check` semantics. Extend the CLI rather than adding a script: the installed artefact should be interrogable (`uvx ml-lints --list-rules --format json`), which is the same self-describing thesis as `--explain`.
**Acceptance:** `packages/py/rule-manifest.json` committed and byte-stable across runs; `--check` fails on drift. All 19 rules declare a non-empty `concept`, asserted by a test rather than left to review.

### T4 · packages/ts skeleton
`package.json`, `tsconfig.json`, `createRule` helper, flat-config `recommended` preset, `index.ts` with the two scaffolding sentinels.

Rule ID is the bare code (`@ml-lints/ML500`) so `RuleCreator`'s `urlCreator` generates the doc URL mechanically. `summary` maps to the **standard** `meta.docs.description` field, so `eslint-plugin/require-meta-docs-description` enforces its presence for free. `concept` rides alongside it as a custom `meta.docs.concept`, typed as required by `createRule`, because it is the shared field T8 diffs and must not be optional to forget.

**Acceptance:** `npx eslint` loads the plugin. Confirm whether `eslint-plugin-eslint-plugin` objects to non-kebab rule names, and record the answer.

### T5 · TypeScript ML500, naive
Spelling-map lookup over identifiers and comments via `sourceCode.getAllComments()`. **No exemption logic** — that is K1.
**Acceptance:** flags `const color = 1`; reports through `meta.messages` under the shared `messageId` with `found` and `suggestion` data, not a hardcoded string. Behaviour beyond that single case is pinned by **T12**, not here — this task exists to have something to run the corpus against.

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

### T8 · Metadata conformance gate (gate 1 of 2)
Lives at `shared/conformance/`, reads **only the two committed JSON files**, so it needs neither toolchain.

Toolchain-freedom is a *consequence* of what this gate checks, not a constraint imposed on it. Metadata is committed JSON, so diffing it needs no interpreter; behaviour is not, so pinning it needs both. Had the constraint come first — one cheap gate, and whatever it can reach is the guarantee — the guarantee would have shrunk to "the words match", which is why **T12** is a separate task rather than an extension of this one. Neither gate is optional and neither subsumes the other; **RV3** reviews both.

Three buckets, not two:

| Bucket | Fields | Why |
|---|---|---|
| Must be byte-identical | `category`, `concept`, `messageIds` | This is the guarantee "both implementations agree on what each `ML###` means" reduces to. `messageIds` carries identifiers only — the templates behind them are not compared, and neither is `neutralData`, which is a per-language declaration consumed by T12 |
| Required non-empty on both, deliberately **not** compared | `summary`, `suggestion`, `rationale` | Each is one language's phrasing and names that language's constructs; comparing them fails on 15 of 19 rules, and forcing a wording that matches would help no author in either language. Python's ML500 rationale likewise discusses import machinery with no TypeScript analogue |
| Not checked | `exemptions` (TypeScript's differ by design), examples | Per-language by definition |

The middle bucket is the point of D1: presentation is checked for *presence*, never for equality.

Also checked: every category ∈ `categories.json`; no duplicate `id`s; every `id` matches `^ML\d{3}$`; every `id` has a `docs/rules/<ID>.md`; `docUrl` matches the canonical template exactly, or ESLint's `meta.docs.url` 404s silently.

Do **not** assert TypeScript ⊆ Python — that would block a future TypeScript-only rule.

**Acceptance:** must demonstrably **fail** when a shared code's `concept` is altered in one manifest, when a `messageId` is renamed in one manifest, when a category is misspelt `localization`, and when a `summary` is emptied. It must **pass** when one language's `summary` is reworded to a different non-empty string — that case is what proves the split is real rather than decorative. Failure messages quote both sides verbatim. Wired into `just ci` as its own recipe, demonstrated by a hand-edited manifest failing the recipe.

### T12 · Behavioural conformance corpus for naive ML500
*Behavioural conformance* instantiated for the tracer's one shared rule. Tier 1: a scenario set covering span classification — identifier, comment, doc comment, plain string literal — with both polarities, realised in each language. Tier 2: an answer key covering word-splitting, case restoration, whole-name reconstruction, URL and dotted-name skipping, and offsets across newlines. Plus the two runners and the two adapters. Scoped to naive ML500: no exemptions, because those are K1 and divergent by design.

Depends on T5 — there has to be a TypeScript ML500 to grade.

**Acceptance:** must demonstrably **fail** when one implementation's word-splitting is changed and the other's is not; when case restoration is dropped in one language; when one language stops scanning doc comments; when a claimed scenario loses its realisation; and when an adapter returns a constant offset. It must **pass** when one language's rendered message sentence is reworded — that case is what proves the sentence is genuinely free rather than accidentally identical. Failure messages quote the input, both expected sides and both actual sides verbatim. Wired into `just ci` as its own recipe — separate from T8's, because this one needs both toolchains and T8's needs neither, and a Python-only contributor should be told which half they cannot run.

### RV3 · Review: both conformance gates
Run `/adversarial-review T8 from docs/typescript-port.md` **and** `/adversarial-review T12 from docs/typescript-port.md`. One gate covers both halves because passing either alone is the failure this design is guarding against: a green metadata gate with no behavioural corpus is precisely the "agrees on the words, never checked the answers" state, and a behavioural corpus with a decorative metadata gate lets a code drift its `concept` unremarked. Reviewing them together also forces the reviewer to check the seam — that nothing is asserted twice and, more importantly, that nothing falls between them.

**Acceptance:** for T8, reviewer confirms the metadata gate bites on deliberately injected metadata drift, and passes a reworded `summary`. For T12, reviewer confirms the fixture runner bites on a deliberately divergent implementation — not merely on a deliberately broken fixture — and passes a reworded message sentence. Each falsification case named in T8's and T12's acceptance is run and observed to fail, rather than accepted on the strength of a green suite. A REJECT on either half rejects RV3.

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

**Acceptance:** scaffolding a code that exists in the *other* language prints its `category`, `concept` and `messageIds` to be copied **verbatim** (T8 diffs all three), alongside that language's `summary` and `suggestion` as reference phrasing to be **adapted**, clearly labelled as such. That turns T8 from a nag into a rarely-firing backstop without tempting the author to paste Python idiom into a TypeScript message.

### A2 · Documentation
`CONTRIBUTING_RULES.md`, `GEMINI.md`, `README.md`. Includes fixing `GEMINI.md:40,44`, which references a `.pre-commit-config.yaml` that does not exist — the real hook is `.githooks/pre-commit` calling `just precommit`.
**Acceptance:** a fresh clone runs `just setup-dev && just ci` green with no manual steps, per GEMINI.md's requirement that no step relies on the developer remembering it.

---

## Accepted rework

Building `packages/ts` alongside `src/ml_lints` means E4 rewrites justfile paths, ruff globs and CI wiring that E2 will have just written. That is the deliberate cost of flying the spine first.
