# Changelog

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
