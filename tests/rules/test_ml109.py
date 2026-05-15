"""Tests for ML109 — cast between two NewTypes sharing the same base."""

from __future__ import annotations

import textwrap
from pathlib import Path

from tests.conftest import check_project, codes


def test_cross_cast_same_base_flagged(tmp_path: Path) -> None:
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            GoogleEventId = NewType("GoogleEventId", str)
            GCalEventId = NewType("GCalEventId", str)

            def consume(eid: GCalEventId) -> None: ...

            def caller(google: GoogleEventId) -> None:
                consume(GCalEventId(google))
        """),
    }
    violations = check_project(files, tmp_path)
    assert codes(violations) == ["ML109"]
    assert "GoogleEventId" in violations[0].message
    assert "GCalEventId" in violations[0].message


def test_cross_cast_across_modules_flagged(tmp_path: Path) -> None:
    files = {
        "pkg/sync.py": textwrap.dedent("""\
            from typing import NewType

            GoogleEventId = NewType("GoogleEventId", str)
        """),
        "pkg/models.py": textwrap.dedent("""\
            from typing import NewType

            GCalEventId = NewType("GCalEventId", str)
        """),
        "pkg/app.py": textwrap.dedent("""\
            from pkg.models import GCalEventId
            from pkg.sync import GoogleEventId

            def caller(google: GoogleEventId) -> None:
                _ = GCalEventId(google)
        """),
    }
    violations = check_project(files, tmp_path)
    ml109 = [v for v in violations if v.code == "ML109"]
    assert len(ml109) == 1
    assert ml109[0].path.name == "app.py"


def test_cross_cast_different_bases_not_flagged(tmp_path: Path) -> None:
    # UserId wraps str, CustomerNumber wraps int — different bases.
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            UserId = NewType("UserId", str)
            CustomerNumber = NewType("CustomerNumber", int)

            def caller(user: UserId) -> None:
                _ = CustomerNumber(user)
        """),
    }
    violations = check_project(files, tmp_path)
    assert violations == []


def test_chained_newtypes_resolve_to_same_base(tmp_path: Path) -> None:
    # B = NewType("B", A) where A = NewType("A", str) — both resolve to str.
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            BaseId = NewType("BaseId", str)
            DerivedId = NewType("DerivedId", BaseId)
            OtherId = NewType("OtherId", str)

            def caller(x: DerivedId) -> None:
                _ = OtherId(x)
        """),
    }
    violations = check_project(files, tmp_path)
    assert codes(violations) == ["ML109"]


def test_self_cast_not_flagged_by_ml109(tmp_path: Path) -> None:
    # ML109 must not fire when both sides are the same NewType — that's ML108.
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            UserId = NewType("UserId", str)

            def caller(user: UserId) -> None:
                _ = UserId(user)
        """),
    }
    violations = check_project(files, tmp_path)
    assert "ML109" not in [v.code for v in violations]


def test_literal_argument_not_flagged(tmp_path: Path) -> None:
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            UserId = NewType("UserId", str)
            CustomerId = NewType("CustomerId", str)

            def caller() -> None:
                _ = UserId("alice")
                _ = CustomerId("bob")
        """),
    }
    violations = check_project(files, tmp_path)
    assert violations == []


def test_widening_not_flagged(tmp_path: Path) -> None:
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            UserId = NewType("UserId", str)
            CustomerId = NewType("CustomerId", str)

            def caller(user: UserId) -> None:
                _ = CustomerId(str(user))
        """),
    }
    violations = check_project(files, tmp_path)
    assert violations == []


def test_cross_cast_via_attribute_flagged(tmp_path: Path) -> None:
    files = {
        "pkg/models.py": textwrap.dedent("""\
            from typing import NamedTuple, NewType

            GCalEventId = NewType("GCalEventId", str)

            class Pending(NamedTuple):
                event_id: GCalEventId
        """),
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            from pkg.models import Pending

            GoogleEventId = NewType("GoogleEventId", str)

            def caller(pending: Pending) -> None:
                _ = GoogleEventId(pending.event_id)
        """),
    }
    violations = check_project(files, tmp_path)
    ml109 = [v for v in violations if v.code == "ML109"]
    assert len(ml109) == 1
    assert ml109[0].path.name == "app.py"


def test_noqa_suppresses(tmp_path: Path) -> None:
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            UserId = NewType("UserId", str)
            CustomerId = NewType("CustomerId", str)

            def caller(user: UserId) -> None:
                _ = CustomerId(user)  # noqa: ML109
        """),
    }
    violations = check_project(files, tmp_path)
    assert violations == []
