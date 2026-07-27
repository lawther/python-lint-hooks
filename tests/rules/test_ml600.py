"""Tests for ML600 — `@patch(new=Mock(...))` shares one mock instance across tests.

See CONTRIBUTING_RULES.md for the full testing guide.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from tests.conftest import check, codes

# ---------------------------------------------------------------------------
# Positive tests — the rule SHOULD fire
# ---------------------------------------------------------------------------


def test_ml600_flags_new_async_mock_decorator(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from unittest.mock import AsyncMock, patch

        @patch("api.client.send", new=AsyncMock())
        def test_send(mock_send):
            ...
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML600"]


def test_ml600_flags_patch_object_decorator(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from unittest import mock

        @mock.patch.object(mock.sentinel, "attr", new=mock.Mock())
        def test_send():
            ...
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML600"]


def test_ml600_flags_new_referencing_module_level_mock(tmp_path: Path) -> None:
    # `new=` doesn't have to construct the Mock inline — a bare name pointing at a
    # module-level instance is evaluated once at import time too, so it's decorated
    # onto every test with the exact same shared object. This is the same footgun the
    # rule exists to catch, just one level of indirection away from `new=Mock()`.
    code = textwrap.dedent("""\
        from unittest.mock import AsyncMock, patch

        shared_mock = AsyncMock()

        @patch("api.client.send", new=shared_mock)
        def test_send():
            ...
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML600"]


def test_ml600_flags_new_referencing_annotated_module_level_mock(tmp_path: Path) -> None:
    # Same as above but via an annotated module-level assignment, since the project's
    # own style mandates type hints on every binding — this is the realistic shape.
    code = textwrap.dedent("""\
        from unittest.mock import AsyncMock, patch

        shared_mock: AsyncMock = AsyncMock()

        @patch("api.client.send", new=shared_mock)
        def test_send():
            ...
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML600"]


def test_ml600_flags_new_via_decorator_factory(tmp_path: Path) -> None:
    # The decorator itself doesn't have to be a bare `patch(...)` call — a helper that
    # returns `patch` and is then called (`@_get_patcher()(...)`) produces the exact same
    # shared-instance decorator at runtime. `_dotted_name` only walks Name/Attribute chains,
    # so a Call in the callee position silently fell through to "not a patch call".
    code = textwrap.dedent("""\
        from unittest.mock import AsyncMock, patch

        def _get_patcher():
            return patch

        @_get_patcher()("api.client.send", new=AsyncMock())
        def test_send():
            ...
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML600"]


def test_ml600_flags_new_via_mock_class_factory(tmp_path: Path) -> None:
    # Symmetric to the decorator-factory case above, but the indirection is on the `new=`
    # side: a factory that just hands back the mock class, immediately called. Same
    # single-evaluation-at-import-time footgun, just one more hop away from `new=Mock()`.
    code = textwrap.dedent("""\
        from unittest.mock import AsyncMock, patch

        def _get_mock_class():
            return AsyncMock

        @patch("api.client.send", new=_get_mock_class()())
        def test_send():
            ...
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML600"]


def test_ml600_flags_two_hop_decorator_factory_chain(tmp_path: Path) -> None:
    # A factory can itself be reached through another factory — `_get_patcher2` doesn't
    # return `patch` directly, it returns the *result of calling* `_get_patcher`, which
    # does. Resolving only one hop stops at `_get_patcher2` and never discovers `patch`.
    code = textwrap.dedent("""\
        from unittest.mock import AsyncMock, patch

        def _get_patcher():
            return patch

        def _get_patcher2():
            return _get_patcher()

        @_get_patcher2()("api.client.send", new=AsyncMock())
        def test_send():
            ...
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML600"]


def test_ml600_flags_two_hop_mock_alias_chain(tmp_path: Path) -> None:
    # Same root cause on the `new=` side: `b` aliases `a`, and `a` is the module-level
    # mock instance. A single dict lookup for `b` finds nothing, since only `a` maps
    # directly to a mock class — the alias chain has to be followed to the end.
    code = textwrap.dedent("""\
        from unittest.mock import AsyncMock, patch

        a = AsyncMock()
        b = a

        @patch("api.client.send", new=b)
        def test_send():
            ...
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML600"]


def test_ml600_flags_new_via_class_attribute_factory(tmp_path: Path) -> None:
    # A factory doesn't have to be a bare module-level function — `Helpers.get_patcher`
    # is reached through an attribute access, not a plain `Name`, so it needs dotted-name
    # resolution rather than the `ast.Name`-only check the factory lookup used to do.
    code = textwrap.dedent("""\
        from unittest.mock import AsyncMock, patch

        class Helpers:
            @staticmethod
            def get_patcher():
                return patch

        @Helpers.get_patcher()("api.client.send", new=AsyncMock())
        def test_send():
            ...
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML600"]


def test_ml600_ok_self_referential_alias_does_not_crash(tmp_path: Path) -> None:
    # `x` and `y` alias each other — nonsensical code that would NameError at runtime,
    # but the rule still has to walk the AST without recursing forever. Cycle protection
    # should just give up and report nothing, not hang or raise.
    code = textwrap.dedent("""\
        from unittest.mock import patch

        x = y
        y = x

        @patch("api.client.send", new=x)
        def test_send():
            ...
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml600_flags_two_hop_mock_class_factory_chain(tmp_path: Path) -> None:
    # Symmetric to the decorator-chain case: `_get_cls2` doesn't hand back `AsyncMock`
    # directly, it hands back the result of calling `_get_cls`, which does.
    code = textwrap.dedent("""\
        from unittest.mock import AsyncMock, patch

        def _get_cls():
            return AsyncMock

        def _get_cls2():
            return _get_cls()

        @patch("api.client.send", new=_get_cls2()())
        def test_send():
            ...
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML600"]


def test_ml600_flags_decorator_on_class(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from unittest.mock import MagicMock, patch

        @patch("api.client.send", new=MagicMock())
        class TestSend:
            def test_a(self):
                ...
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML600"]


# ---------------------------------------------------------------------------
# Negative tests — the rule MUST NOT fire
# ---------------------------------------------------------------------------


def test_ml600_ok_new_callable(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from unittest.mock import AsyncMock, patch

        @patch("api.client.send", new_callable=AsyncMock)
        def test_send(mock_send):
            ...
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml600_ok_context_manager_is_fine(tmp_path: Path) -> None:
    # Unlike the decorator form, this expression re-evaluates on every call to
    # test_send, so each test gets its own fresh MagicMock. Not the anti-pattern.
    code = textwrap.dedent("""\
        from unittest.mock import MagicMock, patch

        def test_send():
            with patch("api.client.send", new=MagicMock(return_value=1)):
                ...
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml600_ok_new_with_preconfigured_fixture_mock(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from unittest.mock import AsyncMock, patch

        def test_send(configured_mock: AsyncMock) -> None:
            with patch("api.client.send", new=configured_mock):
                ...
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml600_ok_new_with_unrelated_call(tmp_path: Path) -> None:
    # `new=` here is a Call (rules out the module-level-name lookup) whose callee isn't
    # one of the recognised mock classes, so it must fall through to "not flagged".
    code = textwrap.dedent("""\
        from unittest.mock import patch

        def build_stub() -> object:
            return object()

        @patch("api.client.send", new=build_stub())
        def test_send():
            ...
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml600_ok_unrelated_call_with_new_kwarg(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from unittest.mock import AsyncMock

        def build(new: AsyncMock = AsyncMock()) -> None:
            ...
    """)
    violations = check(code, tmp_path)
    assert "ML600" not in codes(violations)


def test_ml600_ok_new_references_undefined_name(tmp_path: Path) -> None:
    # `undefined_name` isn't bound anywhere at module scope, so the alias resolver has
    # nothing to look up — it must give up cleanly rather than assume a match.
    code = textwrap.dedent("""\
        from unittest.mock import patch

        @patch("api.client.send", new=undefined_name)
        def test_send():
            ...
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml600_ok_new_aliases_non_mock_value(tmp_path: Path) -> None:
    # `sentinel` is a module-level name, but it doesn't point at a mock — the alias
    # chain has to terminate on "not a mock" rather than flagging every bare name.
    code = textwrap.dedent("""\
        from unittest.mock import patch

        sentinel = object()

        @patch("api.client.send", new=sentinel)
        def test_send():
            ...
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml600_ok_self_referential_decorator_factory_does_not_crash(tmp_path: Path) -> None:
    # `_get_patcher` calls itself and never bottoms out at `patch` — cycle protection
    # has to stop the recursion rather than looping forever.
    code = textwrap.dedent("""\
        from unittest.mock import patch

        def _get_patcher():
            return _get_patcher()

        @_get_patcher()("api.client.send", new=object())
        def test_send():
            ...
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml600_ok_decorator_factory_calls_undefined_helper(tmp_path: Path) -> None:
    # `_get_patcher` hands off to a name that isn't defined anywhere in the module —
    # the chain has to end on "unknown", not assume it eventually resolves to `patch`.
    code = textwrap.dedent("""\
        from unittest.mock import patch

        def _get_patcher():
            return _undefined_helper()

        @_get_patcher()("api.client.send", new=object())
        def test_send():
            ...
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml600_ok_self_referential_mock_class_factory_does_not_crash(tmp_path: Path) -> None:
    # Same cycle-protection requirement as the decorator-factory case above, but on the
    # `new=` side: `_get_cls` calls itself and never bottoms out at a mock class.
    code = textwrap.dedent("""\
        from unittest.mock import patch

        def _get_cls():
            return _get_cls()

        @patch("api.client.send", new=_get_cls()())
        def test_send():
            ...
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml600_ok_mock_class_factory_calls_undefined_helper(tmp_path: Path) -> None:
    # `_get_cls` hands off to an undefined name rather than a recognised mock class —
    # the chain has to end on "unknown" instead of assuming a match.
    code = textwrap.dedent("""\
        from unittest.mock import patch

        def _get_cls():
            return _undefined_thing()

        @patch("api.client.send", new=_get_cls()())
        def test_send():
            ...
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml600_ok_mock_class_factory_returns_non_callable_non_name(tmp_path: Path) -> None:
    # `_get_cls` returns a plain literal — neither a mock class reference nor a call to
    # another factory, so the chain must terminate without a name to keep following.
    code = textwrap.dedent("""\
        from unittest.mock import patch

        def _get_cls():
            return 5

        @patch("api.client.send", new=_get_cls()())
        def test_send():
            ...
    """)
    violations = check(code, tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------------


def test_noqa_ml600_suppresses(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from unittest.mock import AsyncMock, patch

        @patch("api.client.send", new=AsyncMock())  # noqa: ML600
        def test_send(mock_send):
            ...
    """)
    violations = check(code, tmp_path)
    assert "ML600" not in codes(violations)
