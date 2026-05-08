# Changelog

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
