# Changelog

## [0.15.0](https://github.com/lawther/python-lint-hooks/compare/v0.14.0...v0.15.0) (2026-09-16)


### Features

* **corpus:** sweep rules across external checkouts to find false positives ([7f2edbe](https://github.com/lawther/python-lint-hooks/commit/7f2edbe8afc5c46bd929cad091c0d9c81a71bd3b))
* **ML001:** add a rule flagging files that aren't clean UTF-8 ([88f0d7d](https://github.com/lawther/python-lint-hooks/commit/88f0d7d8172a9cbafb1583c65b5e3f1e52859d70))


### Bug Fixes

* **ML001:** compare normalised codec names, not raw cookie spelling ([29ab95e](https://github.com/lawther/python-lint-hooks/commit/29ab95e7ab850ac67151267c0d0ada78bf7636a2))
* **ML500:** audit every spelling-map entry and drop 66 ([a15e6e6](https://github.com/lawther/python-lint-hooks/commit/a15e6e690ecca4308ac649d4d9624b3715e74054))
* **ML500:** drop spelling-map entries that are wrong in any codebase ([a07d2b5](https://github.com/lawther/python-lint-hooks/commit/a07d2b578b3c50584e645eec1ef5eea4fefceb06))
* **ML500:** scan real comment tokens, not every '#' in a line ([d63b841](https://github.com/lawther/python-lint-hooks/commit/d63b8419ff0950af237befcb5afc19a165c6a60a))
* **ML700,ML701:** see three more substitution shapes, warn about memoised guards ([8fa027f](https://github.com/lawther/python-lint-hooks/commit/8fa027fdece2bac376455c3695b1bb8a90d2b09b))
* **ML701:** check a class body's own binding before an enclosing function's ([d5952cf](https://github.com/lawther/python-lint-hooks/commit/d5952cfb7b19769f1d706b52d106f24d1e8c9cbf))
* **ML701:** give class bodies their own scope ([07da56d](https://github.com/lawther/python-lint-hooks/commit/07da56d8a1fad83a6cb10335dc48fdc2d3de3ca0))
* **ML701:** give the zone- and constant-name tables a real scope model ([7f4eb63](https://github.com/lawther/python-lint-hooks/commit/7f4eb6352be565e5686ff51fa732c0ded06e991f))
* **ML701:** invalidate tuple/list-unpacking rebind targets ([ac03712](https://github.com/lawther/python-lint-hooks/commit/ac037126979855c2226e286a70d4dec9ceb42487))
* **ML701:** read the zone identity through the key= keyword too ([166a1ad](https://github.com/lawther/python-lint-hooks/commit/166a1ad77a6227eab1a5fac148a04d5f2fcdc342))
* **ML701:** show what a named fallback is bound to ([3340a3e](https://github.com/lawther/python-lint-hooks/commit/3340a3eceb52796d9a0b1293c5867b2500ef25d9))
* **ML701:** tell a derived zone apart from an invented one ([0025a75](https://github.com/lawther/python-lint-hooks/commit/0025a75af1ab359108be1d671de9fceb4f5d9cd8))
* **noqa:** honour only real comment tokens, not '# noqa' in strings ([a0bc36d](https://github.com/lawther/python-lint-hooks/commit/a0bc36d7ecaed1c0e53af0ce9df82867077d7eeb))
* remove 'ax' as a spelling ([94eee54](https://github.com/lawther/python-lint-hooks/commit/94eee54073e63f508ab324ff53424b0287b52461))
* **runner:** don't abort the run on an unreadable or unparseable file ([5591f71](https://github.com/lawther/python-lint-hooks/commit/5591f71a3a26874453be774f4402069ded1f2f38))


### Performance Improvements

* **index:** resolve an import through a name bucket, not a full scan ([b2e3532](https://github.com/lawther/python-lint-hooks/commit/b2e353238d2d315be921202e98780cc2207b1201))


### Documentation

* Add ML7xx rule for time correctness ([106186c](https://github.com/lawther/python-lint-hooks/commit/106186cc6cade986056bfe080a9c54abfa2f7337))
* **corpus:** replace the all-rules warning with what the sweep costs ([e6212d6](https://github.com/lawther/python-lint-hooks/commit/e6212d6151f83147000f2434536f059625eb08f5))
* **corpus:** warn that an all-rules sweep is impractical until mlp-kzi lands ([a463b16](https://github.com/lawther/python-lint-hooks/commit/a463b16fb4159d8a15175a0ab00cb467b9cdfc35))
* **ML701:** correct _is_zone_name docstring for class scope ([487ab9d](https://github.com/lawther/python-lint-hooks/commit/487ab9d1f38acdb4558f217634a30eead53993dd))

## [0.14.0](https://github.com/lawther/python-lint-hooks/compare/v0.13.0...v0.14.0) (2026-09-14)


### Features

* add shared analyse-ai-readiness script and recipes ([d03e3ce](https://github.com/lawther/python-lint-hooks/commit/d03e3ce343e0f463b4280ffb7b9ff8d0b2ce5b52))
* enforce shared reject-blocked-by-dependency-type hook ([b4506d4](https://github.com/lawther/python-lint-hooks/commit/b4506d43839c7ffed0abb7bf27f234625554fb99))
* **hooks:** add check-hooks-drift, wired into .githooks/pre-commit ([0bb4522](https://github.com/lawther/python-lint-hooks/commit/0bb45221b5bb0ea514b9e6fc3afc416d3cda13b5))
* **rules:** add ML700 for widened timezone annotations ([b8e2437](https://github.com/lawther/python-lint-hooks/commit/b8e2437255e5e8019cfdf4f95b5d5cc9057e38ef))
* **rules:** add ML701 for silent timezone substitution ([160ec30](https://github.com/lawther/python-lint-hooks/commit/160ec30d2a1f3f212c1e04e7bacb7d249cdbfb54))
* **rules:** add ML702 for midnight floors without a zone conversion ([bc63d3b](https://github.com/lawther/python-lint-hooks/commit/bc63d3b2993c2eee59f850c4f44a494ed21f876c))


### Bug Fixes

* **check-bead-model:** exempt bd create --help/-h from the label guard ([774dd1c](https://github.com/lawther/python-lint-hooks/commit/774dd1cda1e4b4fc284cc35491c31c3c6301a321))
* **hooks:** scope block_override_flags.py's match to one command segment ([52c5db7](https://github.com/lawther/python-lint-hooks/commit/52c5db7559193d8936e23bfc85a93b9ebe64f740))
* **hooks:** scope block_override_flags.py's match to one command segment ([1404bac](https://github.com/lawther/python-lint-hooks/commit/1404bac2b864909753cf87afd16091d82167a629))
* **ML702:** require a literal hour=0 for the midnight-floor sink ([961c91e](https://github.com/lawther/python-lint-hooks/commit/961c91e9edc0a0685df0760307800953a7809099))
* remove potentially wrong 'license' suggestion ([2d5d149](https://github.com/lawther/python-lint-hooks/commit/2d5d149fe5da9fe6db60eaa7cdd95bfd21b6c5e0))
* resolve git via an absolute path in analyse_ai_readiness ([8e6a0ec](https://github.com/lawther/python-lint-hooks/commit/8e6a0ecca9d27b0068268bec25343c0ebe6d0122))


### Reverts

* remove ML702 pending the mlp-bfy decision ([2be10e4](https://github.com/lawther/python-lint-hooks/commit/2be10e4c3764b293a07b41ad9494f956e6bf0c85))


### Documentation

* add TypeScript port specification ([e51f710](https://github.com/lawther/python-lint-hooks/commit/e51f7109f6534f2128609120ac81cccc5054416f))
* **rules:** enrol in the agent_rules rules family ([3a2bd43](https://github.com/lawther/python-lint-hooks/commit/3a2bd4332100358dec779b036e8a8bd3293ed89e))
* specify behavioural conformance and split T8 into two gates ([1ba7073](https://github.com/lawther/python-lint-hooks/commit/1ba70734cfd75cf1ec56d5f9947268453c577bd9))
* specify shared/categories.json and widen RV1 to cover it ([3861846](https://github.com/lawther/python-lint-hooks/commit/386184607af1efdb69a1b3587c43114a205962ce))
* split manifest concept from per-language summary and suggestion ([e0e2e52](https://github.com/lawther/python-lint-hooks/commit/e0e2e529276fb07bb1ad01dd39c66a9e644b1fdf))

## [0.13.0](https://github.com/lawther/python-lint-hooks/compare/v0.12.5...v0.13.0) (2026-08-20)


### Features

* exempt designated converter functions from ML109 ([01df403](https://github.com/lawther/python-lint-hooks/commit/01df4037892ea4d4766df5a38b3079d74daa44ed))


### Bug Fixes

* ingest definitions inside conditional blocks ([7b7f04e](https://github.com/lawther/python-lint-hooks/commit/7b7f04e87e1bcfec7f9f37caf5fc76e505d8b9ca))
* require a directory boundary when matching an import to a module ([951dbdc](https://github.com/lawther/python-lint-hooks/commit/951dbdc24caa9f74648152064db6a81c44b1553e))
* resolve NewType identities through re-export chains ([aa54991](https://github.com/lawther/python-lint-hooks/commit/aa54991a0bcd30497527e4be7d7b9c159340f3b5))


### Documentation

* Clarify AI agent development focus ([b8ff1d9](https://github.com/lawther/python-lint-hooks/commit/b8ff1d97e047f65e84d1a656d70d89e999ee2a7a))
* spell out the converter shape in ML109's hint ([36a18c7](https://github.com/lawther/python-lint-hooks/commit/36a18c77d42c1936bed4b9641dffd8c9bcba0a95))
* Update project description ([355351c](https://github.com/lawther/python-lint-hooks/commit/355351cfdc85d131aa3043bb22331289d119ce68))

## [0.12.5](https://github.com/lawther/python-lint-hooks/compare/v0.12.4...v0.12.5) (2026-07-27)


### Bug Fixes

* **lint:** expand just lint scope and fix script lint issues ([678dad5](https://github.com/lawther/python-lint-hooks/commit/678dad5044724b627babdd37b0282a4551bcfc64))
* **lint:** resolve ruff errors for PERF and pep8-naming rules ([23dd47d](https://github.com/lawther/python-lint-hooks/commit/23dd47d70bd3c141898b8dc1340072f95a26d5fe))
* **lint:** resolve ruff lint errors for ALL rules configuration ([83fbc3a](https://github.com/lawther/python-lint-hooks/commit/83fbc3a8c6ca860b18aa49656db4871b3256a5e7))
* resolve ruff lint errors for new INP, FBT, and PIE rules ([a137cb0](https://github.com/lawther/python-lint-hooks/commit/a137cb057a0804454b2443603adc56cffad5f6b0))

## [0.12.4](https://github.com/lawther/python-lint-hooks/compare/v0.12.3...v0.12.4) (2026-07-27)


### Bug Fixes

* **ml600:** flag new= and decorators reached through a factory call ([893499b](https://github.com/lawther/python-lint-hooks/commit/893499bbf6718dcf1ad6fd1d73069c0a73fdc6ca))
* **ml600:** render the actual new= expression in violation messages ([769fc3a](https://github.com/lawther/python-lint-hooks/commit/769fc3a93ccf2e1439ac57460b35f7b64a9e5df8))
* **ml600:** resolve mock/patch indirection to a fixed point, not one hop ([8d0c1bb](https://github.com/lawther/python-lint-hooks/commit/8d0c1bb68eceaf0ded2860e6d38af3b5f2ee1d07)), closes [#37](https://github.com/lawther/python-lint-hooks/issues/37)


### Documentation

* update README for pypi rename to ml-lints ([0824eef](https://github.com/lawther/python-lint-hooks/commit/0824eef56663f307caacd97afa42626d74099903))

## [0.12.3](https://github.com/lawther/python-lint-hooks/compare/v0.12.2...v0.12.3) (2026-07-26)


### Bug Fixes

* **cli:** stop nested pyproject.toml from silently shifting root detection ([b66b093](https://github.com/lawther/python-lint-hooks/commit/b66b093919cf77587ba2bdd0338c7188e1f5eb22))

## [0.12.2](https://github.com/lawther/python-lint-hooks/compare/v0.12.1...v0.12.2) (2026-07-26)


### Bug Fixes

* remove incorrect spelling mappings ([7b70066](https://github.com/lawther/python-lint-hooks/commit/7b70066489ee7faa12b66e2aa795242e243355a7))

## [0.12.1](https://github.com/lawther/python-lint-hooks/compare/v0.12.0...v0.12.1) (2026-07-26)


### Bug Fixes

* **ci:** correct PyPI GitHub Action repository path ([a101777](https://github.com/lawther/python-lint-hooks/commit/a101777e8f51d7b698ad15936171fa36caab1281))

## [0.12.0](https://github.com/lawther/python-lint-hooks/compare/v0.11.0...v0.12.0) (2026-07-26)


### Features

* rename project to ml-lints and module to ml_lints ([4e2e1aa](https://github.com/lawther/python-lint-hooks/commit/4e2e1aa89e5b2bfe244838ae43383412bbb0aa9c))
* **rules:** add ML600 to ban [@patch](https://github.com/patch)(new=Mock(...)) decorators ([765b94d](https://github.com/lawther/python-lint-hooks/commit/765b94de03aff2d0530e640dfb902f018487e5e8))


### Bug Fixes

* **cli:** load pyproject.toml per target project root when linting external directories ([81f45f9](https://github.com/lawther/python-lint-hooks/commit/81f45f91fa87a206d45c9ebba8c936b3ecb5dab4)), closes [#32](https://github.com/lawther/python-lint-hooks/issues/32)
* **cli:** resolve path objects in _collect_out_of_root_files consistently ([516e1dd](https://github.com/lawther/python-lint-hooks/commit/516e1dd631b7c5ea4f08397ce4ec5d46bd6db67d))
* **cli:** stop --select/--ignore/--exclude from swallowing paths ([6f367e3](https://github.com/lawther/python-lint-hooks/commit/6f367e3c8dae80e63e2190ac58db8cd197f16f0a))
* resolve project root and gitignore per target path ([cbb8c0d](https://github.com/lawther/python-lint-hooks/commit/cbb8c0d63ee5eb80199c55a29fe8b3a779848549)), closes [#30](https://github.com/lawther/python-lint-hooks/issues/30)


### Documentation

* add missing rule-category rows to CONTRIBUTING_RULES.md ([f4fc7ae](https://github.com/lawther/python-lint-hooks/commit/f4fc7ae89570ef4f810db82ac8307f6f907308a2))

## [0.11.0](https://github.com/lawther/python-lint-hooks/compare/v0.10.1...v0.11.0) (2026-06-08)


### Features

* **rules:** add ML110 to detect variable-length tuple parameter annotations ([863896f](https://github.com/lawther/python-lint-hooks/commit/863896fd8a87a45033856412c96ce81cdcd16425))
* **rules:** add ML202 to detect __dict__/vars() spread into constructors ([348ef41](https://github.com/lawther/python-lint-hooks/commit/348ef418039a73da70c28bc1e326de7eedf03a61))


### Bug Fixes

* make register decorator generic to preserve subclass types ([3032f66](https://github.com/lawther/python-lint-hooks/commit/3032f661524db2a08622b64d7968ea4c14c399cb))

## [0.10.1](https://github.com/lawther/python-lint-hooks/compare/v0.10.0...v0.10.1) (2026-06-03)


### Bug Fixes

* remove American-to-British spelling mappings for practice variants ([804caf1](https://github.com/lawther/python-lint-hooks/commit/804caf10aa6b772ed3c87f6aa542c40563e28448))
* remove incorrect spelling mapping for ankle ([483a58b](https://github.com/lawther/python-lint-hooks/commit/483a58b3bac71b9f862e25669a203311553ff648))

## [0.10.0](https://github.com/lawther/python-lint-hooks/compare/v0.9.0...v0.10.0) (2026-06-03)


### Features

* **ml500:** exempt override methods from Australian English check ([eb4a7b3](https://github.com/lawther/python-lint-hooks/commit/eb4a7b39f69bad45f248bd70cedc96abb594dfa7))


### Bug Fixes

* **ml500:** resolve base-class chains longer than two levels ([5a67b40](https://github.com/lawther/python-lint-hooks/commit/5a67b40eac20115fc741df445829336e3ff42634))


### Documentation

* remove bad merge from README ([b8f1cb1](https://github.com/lawther/python-lint-hooks/commit/b8f1cb18b1857908a71e6a7d00ce0ebd5b7ef92d))
* update ML500 rule documentation and test examples to exclude overridden methods ([57ed9e0](https://github.com/lawther/python-lint-hooks/commit/57ed9e026aa9ca28a332f4f9b344208a27af9a39))

## [0.9.0](https://github.com/lawther/python-lint-hooks/compare/v0.8.0...v0.9.0) (2026-05-29)


### Features

* **rules:** add ML501 to detect hacky pluralisation in strings ([ace61d7](https://github.com/lawther/python-lint-hooks/commit/ace61d756c79274e6661d3b618ce9b2b07a97c48))


### Documentation

* **rules:** improve ML300 rationale to explain Python's scoping illusion ([4d85cea](https://github.com/lawther/python-lint-hooks/commit/4d85ceac35717a88f6ea43e7e3e7dfb364ebed45))

## [0.8.0](https://github.com/lawther/python-lint-hooks/compare/v0.7.7...v0.8.0) (2026-05-15)


### Features

* **rules:** add ML108 and ML109 for redundant NewType casts ([ecfffd9](https://github.com/lawther/python-lint-hooks/commit/ecfffd9bd59091367d80113fc30564b454c74b01))
* **rules:** catch redundant NewType casts on for-loop and comprehension targets ([6ac09b6](https://github.com/lawther/python-lint-hooks/commit/6ac09b69229f3431df207df17692c8f247333555))


### Bug Fixes

* **rules:** make ML108 and ML109 messages name a concrete fix ([6ab3aee](https://github.com/lawther/python-lint-hooks/commit/6ab3aee797a6d1465cc924017bcf69b4798e461b))

## [0.7.7](https://github.com/lawther/python-lint-hooks/compare/v0.7.6...v0.7.7) (2026-05-15)


### Bug Fixes

* **rules:** exempt to_dict and as_dict from ML102 ([5eb8939](https://github.com/lawther/python-lint-hooks/commit/5eb8939543f41078c5c9d56e1c731a5174776605))
* **rules:** exempt URLs and dotted names from ML500 spelling checks ([d12f659](https://github.com/lawther/python-lint-hooks/commit/d12f659f68698ce1f27f9f07cc737d5b88051e87))

## [0.7.6](https://github.com/lawther/python-lint-hooks/compare/v0.7.5...v0.7.6) (2026-05-15)


### Bug Fixes

* **rules:** allow noqa on closing docstring line to suppress ML500 ([f91548a](https://github.com/lawther/python-lint-hooks/commit/f91548acacbaa9e0dd348ec6255baa53f546160e))
* **rules:** exempt imported names from ML500 spelling checks ([48945fa](https://github.com/lawther/python-lint-hooks/commit/48945fa6cb60026370ceaf7d180f32db6d343db4))


### Documentation

* **rules:** document ML500 automatic exemptions in README ([6ff1a3a](https://github.com/lawther/python-lint-hooks/commit/6ff1a3a22131d2164dbcd944a07bcbaa6b27d7f1))

## [0.7.5](https://github.com/lawther/python-lint-hooks/compare/v0.7.4...v0.7.5) (2026-05-15)


### Documentation

* **cli:** clarify override behavior of exclude, select, and ignore flags ([801ad84](https://github.com/lawther/python-lint-hooks/commit/801ad84ce4fdc3767661571be933382d96ee0c88))

## [0.7.4](https://github.com/lawther/python-lint-hooks/compare/v0.7.3...v0.7.4) (2026-05-10)


### Bug Fixes

* **rules:** add 'initializer' to ML500 spelling map ([dfdf10a](https://github.com/lawther/python-lint-hooks/commit/dfdf10a98e56f2f79ba26105745f259403e5e573))

## [0.7.3](https://github.com/lawther/python-lint-hooks/compare/v0.7.2...v0.7.3) (2026-05-10)


### Bug Fixes

* **rules:** implement case-preserving and aggregated suggestions for ML500 ([c0a96b1](https://github.com/lawther/python-lint-hooks/commit/c0a96b17f0c1cad3474c42c35edbf68fb706e9d5))


### Documentation

* remove mention of inner class exemptions from README ([9d566d6](https://github.com/lawther/python-lint-hooks/commit/9d566d670818aa9fc550a46d2e005bfe8aa04969))

## [0.7.2](https://github.com/lawther/python-lint-hooks/compare/v0.7.1...v0.7.2) (2026-05-10)


### Bug Fixes

* **rules:** flag American English in docstrings (ML500) ([5f083f5](https://github.com/lawther/python-lint-hooks/commit/5f083f5ba2e8241d71434591832a06e31df4d57d))

## [0.7.1](https://github.com/lawther/python-lint-hooks/compare/v0.7.0...v0.7.1) (2026-05-10)


### Bug Fixes

* removed erroneous words ([352f682](https://github.com/lawther/python-lint-hooks/commit/352f682996a0454cd2fbd048dc42c8ebcd93ed56))

## [0.7.0](https://github.com/lawther/python-lint-hooks/compare/v0.6.1...v0.7.0) (2026-05-10)


### Features

* **rules:** add ML106 and ML107 to detect forbidden Mapping types ([8db371c](https://github.com/lawther/python-lint-hooks/commit/8db371c91460ea58084d43233ca60754788c33ac))
* **rules:** add ML500 to enforce Australian English spelling ([8041781](https://github.com/lawther/python-lint-hooks/commit/80417816f564cbbc44636a1cd1c5f89e1ef62c1a))


### Bug Fixes

* **cli:** implement Ruff-style path exclusion logic ([d0686f3](https://github.com/lawther/python-lint-hooks/commit/d0686f3a4c106ad3accf632e574ef72b44535249)), closes [#15](https://github.com/lawther/python-lint-hooks/issues/15)


### Documentation

* implement rationale and examples for all lint rules ([7aa5d7e](https://github.com/lawther/python-lint-hooks/commit/7aa5d7e9c91288c15a8e4570bc2b9f17875218c3))
* update legacy rule references in README ([4af4329](https://github.com/lawther/python-lint-hooks/commit/4af43290f1af49baf89fd336ca88f458e752dabd))

## [0.6.1](https://github.com/lawther/python-lint-hooks/compare/v0.6.0...v0.6.1) (2026-05-08)


### Bug Fixes

* exclude ClassVar fields from ML201 all-forbidden-types check ([42cf5b1](https://github.com/lawther/python-lint-hooks/commit/42cf5b1f474488af94f7a23bee7db6559b36ab97))
* recognise [@alias](https://github.com/alias).dataclass regardless of module alias name ([d51ae7e](https://github.com/lawther/python-lint-hooks/commit/d51ae7e67b83d24d7e9473b70524027ac302b96e))
* recognise t.NewType regardless of typing module alias name ([0f26908](https://github.com/lawther/python-lint-hooks/commit/0f26908bf9201b62101741b47d261438ac6bf800))

## [0.6.0](https://github.com/lawther/python-lint-hooks/compare/v0.5.0...v0.6.0) (2026-05-08)


### Features

* add per-file branch coverage breakdown to just test output ([417afcb](https://github.com/lawther/python-lint-hooks/commit/417afcb6cf887829873298e98616219c86a9c55e))
* introduce RuleCode StrEnum for type-safe rule codes ([f72ecd6](https://github.com/lawther/python-lint-hooks/commit/f72ecd64c007a41086815a189c985b99b9acc2ef))


### Bug Fixes

* handle ast.Starred in _get_names so starred unpack variables are tainted ([46be6e0](https://github.com/lawther/python-lint-hooks/commit/46be6e0115087cad9626c41c50eefa626e77aef9))
* isolate comprehension variable taint with per-comprehension scope ([a0731f7](https://github.com/lawther/python-lint-hooks/commit/a0731f75d6846ce2cfcebd2eb7f68c77014cee3a))
* unconditionally update loop-variable taint in enter_For ([e49073d](https://github.com/lawther/python-lint-hooks/commit/e49073dfeda9ad114ce2ad128600868d28970b52))
* use gen.iter as source_node in comprehension taint propagation ([54750ac](https://github.com/lawther/python-lint-hooks/commit/54750ac60d46f24636baa107f88658c8572d5579))

## [0.5.0](https://github.com/lawther/python-lint-hooks/compare/v0.4.0...v0.5.0) (2026-05-08)


### Features

* add docs-rules, check-rules-docs, and new-rule justfile recipes ([e5ac3f5](https://github.com/lawther/python-lint-hooks/commit/e5ac3f5657548104bc7d97690e7d6e30617a8ff5))
* add ML400 rule to detect unvalidated external data usage ([8bd289b](https://github.com/lawther/python-lint-hooks/commit/8bd289b8e530642cae8161dadfce69cfe02af8cb))


### Bug Fixes

* disallow bare # noqa suppressions to prevent over-suppression ([9e6e668](https://github.com/lawther/python-lint-hooks/commit/9e6e6689b9f0befc8c1c38a4eca9c5ca2c3268cc))
* include ml400_untrusted_data.py omitted from previous staging ([53f31a6](https://github.com/lawther/python-lint-hooks/commit/53f31a63fcfcb688d6ae6b5d1c1da6524f0132ff))
* suppress ML400 on tomllib.load in cli (pre-validation navigation) ([4b65652](https://github.com/lawther/python-lint-hooks/commit/4b6565272ce57b1d044c719c2082fe580b3b7fd0))


### Documentation

* add CONTRIBUTING_RULES.md and link from GEMINI.md ([485b189](https://github.com/lawther/python-lint-hooks/commit/485b189259fedc2379739011be4fd9017c0e4059))
* update justfile integration example in README ([e6d12ef](https://github.com/lawther/python-lint-hooks/commit/e6d12efcceb5b7a3c927514bedcc061bd07234d0))

## [0.4.0](https://github.com/lawther/python-lint-hooks/compare/v0.3.0...v0.4.0) (2026-05-06)


### Features

* add ML105 to catch NewType bypasses of return type rules ([0321c6d](https://github.com/lawther/python-lint-hooks/commit/0321c6db90c8b67f28296bd43028ad84fc7ccd65))
* add ML201 to catch classes wrapping only forbidden types ([4e9886d](https://github.com/lawther/python-lint-hooks/commit/4e9886de156bb132d4bd6002f9662e4f76a9300e))

## [0.3.0](https://github.com/lawther/python-lint-hooks/compare/v0.2.0...v0.3.0) (2026-05-06)


### Features

* add pytest-randomly to development dependencies ([14cd9f8](https://github.com/lawther/python-lint-hooks/commit/14cd9f800263df0d6979556e370dd5db4e4dbd68))
* add Ruff-like --select and --ignore CLI filtering ([71e76aa](https://github.com/lawther/python-lint-hooks/commit/71e76aa158e53d6aa764bb3aca92437a6622c2b7))
* enforce frozen=True for dataclasses (ML005) ([5b46303](https://github.com/lawther/python-lint-hooks/commit/5b46303192d9830e837b6a3480ff2a60a842dfd3))
* expanded return type enforcement and thematic renumbering ([ed4a0f4](https://github.com/lawther/python-lint-hooks/commit/ed4a0f4403e1db7f2b71137ca626fb4784ce72f5)), closes [#5](https://github.com/lawther/python-lint-hooks/issues/5)


### Documentation

* document --select, --ignore and prefix matching behavior ([988de6a](https://github.com/lawther/python-lint-hooks/commit/988de6a6428da1ce20b08c6d1684c753244f64f5))
* update README with ML005 and new CLI options ([49400bf](https://github.com/lawther/python-lint-hooks/commit/49400bfee22fc5dae417e14246085a6a2a6b2494))

## [0.2.0](https://github.com/lawther/python-lint-hooks/compare/v0.1.0...v0.2.0) (2026-05-06)


### Features

* add Ruff-like exclusion options to CLI ([8a137ff](https://github.com/lawther/python-lint-hooks/commit/8a137ffba6278a62f62999863a9efd4c46d6ba18))


### Documentation

* add GEMINI.md coding conventions and link in CLAUDE.md ([407948d](https://github.com/lawther/python-lint-hooks/commit/407948d51f03a7f5e6ae4e7d8276df053e31aeb8))

## 0.1.0 (2026-05-06)


### Features

* initial implementation of ML001 (bare dict/tuple returns) and ML002 (class inside function) ([d2756d7](https://github.com/lawther/python-lint-hooks/commit/d2756d74c603058852c30b11c35bf2e5295dad41))


### Bug Fixes

* commit ruff auto-fixes missed by precommit staging; rename noqa section comment ([b2a0fc3](https://github.com/lawther/python-lint-hooks/commit/b2a0fc3550624600ecb4e96e46a1ad47bf967bad))


### Documentation

* add README covering installation, rules, configuration and integration ([eee9cf1](https://github.com/lawther/python-lint-hooks/commit/eee9cf1777510086c34478adb8e938edf0494d1b))
