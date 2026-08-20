"""Tests for ML109 — cast between two NewTypes sharing the same base."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from tests.conftest import check_project, codes

if TYPE_CHECKING:
    from pathlib import Path


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


def test_cross_cast_in_for_loop_flagged(tmp_path: Path) -> None:
    # for x in iter: bound x to the element NewType; cross-casting it should fire.
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            GoogleEventId = NewType("GoogleEventId", str)
            GCalEventId = NewType("GCalEventId", str)

            def process(events: list[GoogleEventId]) -> None:
                for eid in events:
                    _ = GCalEventId(eid)
        """),
    }
    violations = check_project(files, tmp_path)
    assert codes(violations) == ["ML109"]


def test_cross_cast_in_comprehension_flagged(tmp_path: Path) -> None:
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            GoogleEventId = NewType("GoogleEventId", str)
            GCalEventId = NewType("GCalEventId", str)

            def collect(events: list[GoogleEventId]) -> list[GCalEventId]:
                return [GCalEventId(eid) for eid in events]
        """),
    }
    violations = check_project(files, tmp_path)
    assert codes(violations) == ["ML109"]


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


def test_cross_cast_via_module_reexport_flagged(tmp_path: Path) -> None:
    # The argument's NewType is imported from a module that itself only re-exports it.
    # Resolution must follow the alias chain through to the defining module, otherwise
    # the identical cast fires or stays silent depending purely on which import the
    # call site happened to use.
    files = {
        "pkg/common.py": textwrap.dedent("""\
            from typing import NewType

            GCalEventId = NewType("GCalEventId", str)
        """),
        "pkg/interval_ops.py": textwrap.dedent("""\
            from pkg.common import GCalEventId

            __all__ = ["GCalEventId"]
        """),
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            from pkg.interval_ops import GCalEventId

            CaseyEventId = NewType("CaseyEventId", str)

            def caller(gcal: GCalEventId) -> None:
                _ = CaseyEventId(gcal)
        """),
    }
    violations = check_project(files, tmp_path)
    ml109 = [v for v in violations if v.code == "ML109"]
    assert len(ml109) == 1
    assert ml109[0].path.name == "app.py"


def test_cross_cast_via_package_init_reexport_flagged(tmp_path: Path) -> None:
    # Same as above, but the re-exporting module is a package's __init__.py, which the
    # dotted-name → path mapping must also recognise.
    files = {
        "pkg/db/__init__.py": textwrap.dedent("""\
            from pkg.db.common import GCalEventId

            __all__ = ["GCalEventId"]
        """),
        "pkg/db/common.py": textwrap.dedent("""\
            from typing import NewType

            GCalEventId = NewType("GCalEventId", str)
        """),
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            from pkg.db import GCalEventId

            CaseyEventId = NewType("CaseyEventId", str)

            def caller(gcal: GCalEventId) -> None:
                _ = CaseyEventId(gcal)
        """),
    }
    violations = check_project(files, tmp_path)
    ml109 = [v for v in violations if v.code == "ML109"]
    assert len(ml109) == 1
    assert ml109[0].path.name == "app.py"


def test_reexport_chain_gives_same_identity_as_direct_import(tmp_path: Path) -> None:
    # A cast through a re-export must resolve to the *same* NewType identity as the
    # direct import, so casting a value to its own NewType is a self-cast (ML108),
    # never a cross-cast (ML109).
    files = {
        "pkg/common.py": textwrap.dedent("""\
            from typing import NewType

            GCalEventId = NewType("GCalEventId", str)
        """),
        "pkg/reexport.py": textwrap.dedent("""\
            from pkg.common import GCalEventId

            __all__ = ["GCalEventId"]
        """),
        "pkg/app.py": textwrap.dedent("""\
            from pkg.common import GCalEventId
            from pkg.reexport import GCalEventId as AliasedGCalEventId

            def caller(gcal: GCalEventId) -> None:
                _ = AliasedGCalEventId(gcal)
        """),
    }
    violations = check_project(files, tmp_path)
    assert codes(violations) == ["ML108"]


def test_reexport_of_unknown_symbol_stays_silent(tmp_path: Path) -> None:
    # The chain walk must not resolve a name that no module in the chain actually
    # defines as a NewType — an unresolvable argument type means no violation.
    files = {
        "pkg/hop.py": textwrap.dedent("""\
            from pkg.missing import SomeId

            __all__ = ["SomeId"]
        """),
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            from pkg.hop import SomeId

            CaseyEventId = NewType("CaseyEventId", str)

            def caller(value: SomeId) -> None:
                _ = CaseyEventId(value)
        """),
    }
    violations = check_project(files, tmp_path)
    assert violations == []


def test_circular_reexport_terminates(tmp_path: Path) -> None:
    # Two modules importing the same name from each other must not send the chain
    # walk into an infinite loop.
    files = {
        "pkg/a.py": 'from pkg.b import Spinning\n\n__all__ = ["Spinning"]\n',
        "pkg/b.py": 'from pkg.a import Spinning\n\n__all__ = ["Spinning"]\n',
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            from pkg.a import Spinning

            CaseyEventId = NewType("CaseyEventId", str)

            def caller(value: Spinning) -> None:
                _ = CaseyEventId(value)
        """),
    }
    violations = check_project(files, tmp_path)
    assert violations == []
