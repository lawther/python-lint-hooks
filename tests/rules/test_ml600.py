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


def test_ml600_ok_unrelated_call_with_new_kwarg(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from unittest.mock import AsyncMock

        def build(new: AsyncMock = AsyncMock()) -> None:
            ...
    """)
    violations = check(code, tmp_path)
    assert "ML600" not in codes(violations)


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
