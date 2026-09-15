# ML500 spelling-map audit

`src/ml_lints/rules/spelling_map.json` is a flat American → Australian word map with no
per-entry context, so an entry is either always right or it is a standing false positive.
This document is the record of auditing every entry: what was removed, and — more useful to
the next reader — which suspicious entries were examined and deliberately kept, so the same
judgements are not re-derived.

JSON carries no comments, which is why the reasoning lives here rather than beside the data.

## What counts as a defect

**Homograph.** The key is also correct Australian English in another sense, so the rule is
right only for one meaning. `tire` → `tyre` is right for the noun and wrong for the verb.

**Different word.** Key and value are not spellings of the same word. `ton` → `tonne`
converts between units 10% apart; `bevy` → `bevvy` turns a group into a drink.

**Archaic value.** The value is a real British form but not current Australian usage.
`reflection` → `reflexion` and its `-xion` siblings.

**Code-ubiquitous key.** The key is genuinely the American spelling, but it is the standard
identifier for a technical concept, so the rule mostly fires on names a developer is
mirroring rather than choosing. `analog` was removed on these grounds in a07d2b5.

A fifth defect surfaced during the audit and has no Australian-English content at all:
**broken entries** — values half-transformed (`colorize` → `colourize`), values that are a
different inflection of the key (`tranquility` → `tranquilly`), and hyphenated keys that
`WORDS_RE` can never match, so the entry was dead.

## Provenance

The obscure wrong entries cluster in a way that points at the source list: `baste` →
`baist`, `lathe` → `laith`, `slough` → `sleugh` and `backtender` → `backtenter` are Scots
or dialect forms that Merriam-Webster labels "British spelling of", not Australian English.
The `-xion` entries removed in a07d2b5 have the same shape. Treat any remaining oddity in
the same family as suspect rather than authoritative.

## Removed

### Homograph or code-ubiquitous

| removed | suggested | reason |
|---|---|---|
| `annex` | annexe | `annexe` is the noun; `annex` is the verb, and "Unicode Standard Annex" is the term of art. |
| `draft` | draught | A draft document, draft PR or `draft4` JSON Schema is Australian English. `draught` is beer and air. `draftsman`, `drafty` and the rest of the family are correct and stay. |
| `gray`, `grays` | grey, greys | Correct for the colour, but `gray` is the SI unit of absorbed dose and a matplotlib colormap name. Narrowed by inflection: `grayed`, `graying`, `grayish` and `grayness` are unambiguous and stay. |
| `groin`, `groins` | groyne, groynes | `groin` is the body part; a `groyne` is the coastal structure. |
| `artifact`, `artifacts` | artefact, artefacts | `artefact` is the Australian prose spelling, but `artifact` is the identifier in pytest, optuna, MLflow, GitHub Actions and esphome. Same call as `analog`. |
| `catalog`, `catalogs` | catalogue | Data catalog, SQL catalog, Iceberg catalog — the technical term is spelled this way everywhere. |
| `dialog`, `dialogs` | dialogue | A dialog box is the standard term and a widget class name in every GUI toolkit. |
| `epilog`, `epilogs` | epilogue | `epilog` is the argparse, click and typer parameter name. |
| `prolog`, `prologs` | prologue | Prolog is a language; `rst_prolog` is a Sphinx setting. |

### Different word, or a value that is not the Australian form of the key

`mocha` → moka (a coffee against a pot), `griffin`/`griffins` → gryphon (a variant form;
`griffin` is the headword), `pizzazz` → pzazz, `preventer` → preventor, `tendentious` →
tendencious, `syntagma` → syntagm, `doorman` → doorsman, `baste` → baist, `lathe` → laith,
`slough` → sleugh, `backtender` → backtenter, `pummel` → pummelled (the value was the past
tense of the key).

### Archaic value

`gluing` → glueing, `carcass` → carcase, `almanac`/`almanacs` → almanack, `doily` → doyley,
`wagon`/`wagons` → waggon (dated), `siphon` and its three inflections → syphon (a variant of
the headword), `sulfate`/`sulfates`/`sulfide`/`sulfides`/`sulfur`/`sulfurous` → sulph-
(Commonwealth-obsolete; Australian curricula and IUPAC use `sulf-`),
`chimera`/`chimeras`/`chimeric`/`chimerism` → chimaera (a less common variant),
`fetus`/`fetuses`/`fetal`/`fetid` → foet- (`fetus` is the primary Australian and scientific
spelling), `ecumenical` → oecumenical, `primeval` → primaeval, `peony` → paeony,
`presidium`/`presidiums` → praesidium, `bougainvillea`/`bougainvilleas` → bougainvillaea,
`stoichiometry` → stoicheiometry.

### Dead entries

`estr-`, `feto-`, `leuk-` and `paleo-` end in a hyphen, and the rule tokenises on
`\b[a-zA-Z]+\b`, so no input could ever match them.

## Repaired rather than removed

| entry | was | now |
|---|---|---|
| `colorize` and its three inflections | colourize … | colourise, colourised, colourises, colourising |
| `anesthetize` and its three inflections | anaesthetize … | anaesthetise, anaesthetised, anaesthetises, anaesthetising |
| `tranquilize` and its five inflections | tranquillize … | tranquillise, tranquillised, tranquilliser, tranquillisers, tranquillises, tranquillising |
| `tranquility` | tranquilly (an adverb) | tranquillity |
| `snowplow` | snowploughs (a plural) | snowplough |
| `pummeled` | pummelling | pummelled, with `pummeling` → `pummelling` added to complete the pair |

## Considered and kept

| entry | why it stays |
|---|---|
| `labor` → labour | The Australian Labor Party is the only Australian-English use of `labor`, and a proper noun in a comment is a narrow loss against a common misspelling. |
| `rigor` → rigour | Correct only inside `rigor mortis` and the medical sense, both fixed phrases that rarely reach code. |
| `arbor` → arbour | The machine-tool sense is real but belongs to machining, not this fleet's domains. |
| `savory` → savoury | `savory` the herb is a different plant, not a spelling variant, but it is vanishingly rare next to the adjective. |
| `fiber`, `fibers` → fibre | Unlike `artifact`, there is no Python API pressure: the corpus hits are prose about muscle fibre. |
| `micrometer`, `micrometers` → micrometre | A micrometer gauge is an instrument, but the corpus hits are all the unit, and the instrument is rare in code. |
| `artifact` vs `artefact`, again | The removal is a code-ubiquity call, not a claim that `artifact` is Australian English. Prose should still say artefact. |
| `busses`, `bussing`, `minibusses`, `gasses` | Each has a valid other reading (to buss, to gas), but the values are the standard Australian forms and the other readings do not occur in code. |
| `misspelled` → misspelt | `misspelt` is the British and Australian form; `misspelled` is North American. |
| `judgment` → judgement | `judgement` is the Commonwealth spelling. Australian legal writing prefers `judgment`, which is the one context where this entry over-fires. |
| `balk` → baulk | `baulk` is the British and Australian spelling; `balk` is the American headword. Kept despite reading as a near-variant pair. |
| `eon` → aeon | `aeon` is the Australian spelling; `eon` is common in geological writing but is the American form. |
| `apothegm` → apophthegm | Both are rare; `apophthegm` is the standard British form, not an archaism. |
| `amoxicillin` → amoxycillin | Australian medical usage (and the TGA) spells it `amoxycillin`. |
| `homeopath` and family → homoeopath | The `oe` form is current Australian usage, unlike the `-xion` family. |
| `licenses` → licences | Kept in a07d2b5: the noun plural. The verb sense (`the module licenses X`) is the one misfire, and it is rare next to the noun. |
| `defense`, `offense`, `pretense` → -ence | Noun-only, so they have no verb form to collide with, unlike `licensed`. |
| `serialize`, `initialize`, `normalize` and the rest of the `-ize` family | The largest source of findings and the rule's whole point. Third-party API names reach them through attribute access or keyword arguments, which the rule already exempts, and overridden methods are exempt through the base-class check. |

## Effect

Over the 60,537-file corpus the audit takes ML500 from 150,632 hits across 20,928 files to
145,488 across 20,617 — 5,144 fewer findings (3.4%) in 311 fewer files. `artifact` alone
accounts for roughly half of the drop.

## Re-running the measurement

```sh
just corpus-lint ML500   # whole-corpus count
just corpus-diff ML500   # only what a working-tree change adds or removes
```
