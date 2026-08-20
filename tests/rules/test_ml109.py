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


def test_designated_converter_not_flagged(tmp_path: Path) -> None:
    # A function whose signature *is* the conversion is the sanctioned way to keep two
    # NewTypes distinct while still crossing between them. Flagging it would make `# noqa`
    # the only way to express a deliberate, documented conversion.
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            GoogleEventId = NewType("GoogleEventId", str)
            GCalEventId = NewType("GCalEventId", str)

            def adopt_google_event_id(google: GoogleEventId) -> GCalEventId:
                return GCalEventId(google)
        """),
    }
    violations = check_project(files, tmp_path)
    assert violations == []


def test_designated_converter_with_docstring_and_guard_not_flagged(tmp_path: Path) -> None:
    # A converter is still a converter when it has a docstring and validates its input
    # first — the exemption keys off the return statement, not a single-statement body.
    files = {
        "pkg/app.py": textwrap.dedent('''\
            from typing import NewType

            GoogleEventId = NewType("GoogleEventId", str)
            GCalEventId = NewType("GCalEventId", str)

            def adopt_google_event_id(google: GoogleEventId) -> GCalEventId:
                """Legacy events have no GCal id of their own."""
                if not google:
                    msg = "empty id"
                    raise ValueError(msg)
                return GCalEventId(google)
        '''),
    }
    violations = check_project(files, tmp_path)
    assert violations == []


def test_converter_across_modules_not_flagged(tmp_path: Path) -> None:
    # The declared return type resolves through an import like any other annotation.
    files = {
        "pkg/ids.py": textwrap.dedent("""\
            from typing import NewType

            GoogleEventId = NewType("GoogleEventId", str)
            GCalEventId = NewType("GCalEventId", str)
        """),
        "pkg/convert.py": textwrap.dedent("""\
            from pkg.ids import GCalEventId, GoogleEventId

            def adopt(google: GoogleEventId) -> GCalEventId:
                return GCalEventId(google)
        """),
    }
    violations = check_project(files, tmp_path)
    assert violations == []


def test_cast_mid_body_still_flagged(tmp_path: Path) -> None:
    # Only the direct return value is exempt. A cast buried mid-body is exactly the
    # scattered, unexplained crossing the rule exists to catch, even inside a function
    # that happens to declare the right return type.
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            GoogleEventId = NewType("GoogleEventId", str)
            GCalEventId = NewType("GCalEventId", str)

            def sink(eid: GCalEventId) -> None: ...

            def adopt(google: GoogleEventId) -> GCalEventId:
                sink(GCalEventId(google))
                return GCalEventId(google)
        """),
    }
    violations = check_project(files, tmp_path)
    ml109 = [v for v in violations if v.code == "ML109"]
    assert len(ml109) == 1
    # The mid-body call, not the returned one.
    assert ml109[0].line == 9


def test_converter_returning_non_parameter_still_flagged(tmp_path: Path) -> None:
    # Converting something the function fetched from elsewhere is not "this function's
    # job is converting its input" — it is an ordinary crossing that needs justifying.
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            GoogleEventId = NewType("GoogleEventId", str)
            GCalEventId = NewType("GCalEventId", str)

            def adopt(unrelated: str) -> GCalEventId:
                current: GoogleEventId = GoogleEventId(unrelated)
                return GCalEventId(current)
        """),
    }
    violations = check_project(files, tmp_path)
    assert codes(violations) == ["ML109"]


def test_converter_with_mismatched_return_annotation_still_flagged(tmp_path: Path) -> None:
    # The exemption requires the declared return type to be the NewType being constructed.
    # A function returning something else is not declaring this conversion.
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            GoogleEventId = NewType("GoogleEventId", str)
            GCalEventId = NewType("GCalEventId", str)
            OtherId = NewType("OtherId", str)

            def adopt(google: GoogleEventId) -> OtherId:
                return GCalEventId(google)
        """),
    }
    violations = check_project(files, tmp_path)
    assert codes(violations) == ["ML109"]


def test_unannotated_converter_still_flagged(tmp_path: Path) -> None:
    # Without a return annotation the function declares nothing, so there is no
    # signature-level statement of intent to defer to.
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            GoogleEventId = NewType("GoogleEventId", str)
            GCalEventId = NewType("GCalEventId", str)

            def adopt(google: GoogleEventId):
                return GCalEventId(google)
        """),
    }
    violations = check_project(files, tmp_path)
    assert codes(violations) == ["ML109"]


def test_nested_function_return_does_not_exempt_outer_cast(tmp_path: Path) -> None:
    # The exemption belongs to the function that owns the return statement. A cast in an
    # enclosing function must not inherit a nested function's declared conversion.
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            GoogleEventId = NewType("GoogleEventId", str)
            GCalEventId = NewType("GCalEventId", str)

            def outer(google: GoogleEventId) -> GCalEventId:
                def inner(nested: GoogleEventId) -> GCalEventId:
                    return GCalEventId(nested)
                _ = GCalEventId(google)
                return inner(google)
        """),
    }
    violations = check_project(files, tmp_path)
    ml109 = [v for v in violations if v.code == "ML109"]
    # Only the outer, mid-body cast; the nested function's return is its own converter.
    assert len(ml109) == 1
    assert ml109[0].line == 9


def test_self_cast_in_converter_shape_still_flagged_as_ml108(tmp_path: Path) -> None:
    # The exemption is for crossings that must stay distinct. A function that "converts" a
    # NewType to itself is pure ceremony, so ML108 must still fire.
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            EventId = NewType("EventId", str)

            def passthrough(eid: EventId) -> EventId:
                return EventId(eid)
        """),
    }
    violations = check_project(files, tmp_path)
    assert codes(violations) == ["ML108"]


def test_async_converter_not_flagged(tmp_path: Path) -> None:
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            GoogleEventId = NewType("GoogleEventId", str)
            GCalEventId = NewType("GCalEventId", str)

            async def adopt(google: GoogleEventId) -> GCalEventId:
                return GCalEventId(google)
        """),
    }
    violations = check_project(files, tmp_path)
    assert violations == []


def test_sibling_package_ending_in_the_imported_package_name_does_not_mask_the_import(tmp_path: Path) -> None:
    # `from db.models.common import ...` must resolve to db/models/common.py even when the
    # project also contains mydb/models/common.py. Matching an import's dotted name against
    # ingested paths by suffix has to respect directory boundaries: "mydb/models/common.py"
    # ends with the characters "db/models/common.py" without being that module at all. Treat
    # it as a candidate and the import looks ambiguous, so the index resolves nothing and the
    # rule goes quiet — the same silent, import-shape-dependent coverage loss this rule was
    # already fixed for once, but triggered by an unrelated package merely being named badly.
    files = {
        "db/models/common.py": textwrap.dedent("""\
            from typing import NewType

            GCalEventId = NewType("GCalEventId", str)
        """),
        "mydb/models/common.py": "UNRELATED = 1\n",
        "app.py": textwrap.dedent("""\
            from typing import NewType

            from db.models.common import GCalEventId

            CaseyEventId = NewType("CaseyEventId", str)

            def caller(gcal: GCalEventId) -> None:
                _ = CaseyEventId(gcal)
        """),
    }
    violations = check_project(files, tmp_path)
    assert codes(violations) == ["ML109"]


def test_newtype_imported_under_type_checking_still_resolves(tmp_path: Path) -> None:
    # `from __future__ import annotations` plus an `if TYPE_CHECKING:` import block is the
    # standard way to keep typing-only imports out of the runtime import graph — ml_lints'
    # own modules are written this way. The names it binds are ordinary module-level names,
    # because an `if` introduces no scope. Ingesting only the statements directly in
    # `Module.body` skips the block entirely, so every NewType a file imports that way is
    # unresolvable and the rule goes silent across that whole file.
    files = {
        "pkg/common.py": textwrap.dedent("""\
            from typing import NewType

            GCalEventId = NewType("GCalEventId", str)
        """),
        "pkg/app.py": textwrap.dedent("""\
            from __future__ import annotations

            from typing import TYPE_CHECKING, NewType

            if TYPE_CHECKING:
                from pkg.common import GCalEventId

            CaseyEventId = NewType("CaseyEventId", str)

            def caller(gcal: GCalEventId) -> None:
                _ = CaseyEventId(gcal)
        """),
    }
    violations = check_project(files, tmp_path)
    assert codes(violations) == ["ML109"]
