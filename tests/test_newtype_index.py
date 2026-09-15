"""Tests for the cross-file NewType index itself.

Rule-level behaviour lives in tests/rules/test_ml108.py and test_ml109.py; what is
tested here is the index's own resolution and lookup cost, which no single rule test
can observe.
"""

from __future__ import annotations

import ast
import textwrap

import pytest

from ml_lints.analyzers.newtype_index import NewTypeIndex


def _index_of(sources: dict[str, str]) -> NewTypeIndex:
    index = NewTypeIndex()
    for path, source in sources.items():
        index.ingest(path, ast.parse(source))
    index.finalise()
    return index


def _index_of_distinct_modules(count: int) -> NewTypeIndex:
    """An index of `count` modules, every one with a different name."""
    return _index_of({f"/repo/pkg/mod_{n}.py": "" for n in range(count)})


@pytest.mark.parametrize("size", [10, 2_000])
def test_resolution_consults_a_candidate_set_that_does_not_grow_with_the_index(size: int) -> None:
    # The whole point of the fix: resolving one dotted name must not walk the index.
    # _resolve_origin_module is called tens of times for every file checked, so a walk
    # makes checking a project cost the square of its file count — 8x the files took
    # 37x the time before this. Asserting the candidate count rather than the elapsed
    # time keeps the guard deterministic: a reintroduced scan fails this at 2,000
    # modules no matter how fast the machine is.
    index = _index_of_distinct_modules(size)
    assert len(index.candidates_for("pkg.mod_7")) == 1


def test_package_init_is_a_candidate_for_the_package_name() -> None:
    # A name re-exported from pkg/models/__init__.py must resolve exactly as one
    # imported from pkg/models.py, so the package's __init__ has to be filed under
    # the package's own name rather than under "__init__".
    index = _index_of({"/repo/pkg/models/__init__.py": ""})
    assert list(index.candidates_for("pkg.models")) == ["/repo/pkg/models/__init__.py"]


def test_a_package_init_is_not_a_candidate_for_every_import() -> None:
    # Filing __init__.py under "__init__" would put every package in the project into
    # one bucket that each lookup consults, leaving resolution linear in project size.
    index = _index_of({f"/repo/pkg_{n}/__init__.py": "" for n in range(100)})
    assert list(index.candidates_for("pkg_7")) == ["/repo/pkg_7/__init__.py"]


def test_name_matching_two_modules_resolves_to_nothing() -> None:
    # Two projects on the path can both offer `shared.ids`; with no import machinery to
    # adjudicate, the index must not guess. Silence is the conservative answer, and the
    # narrowed candidate set must not quietly turn the ambiguity into a pick.
    definition = textwrap.dedent("""\
        from typing import NewType

        EventId = NewType("EventId", str)
    """)
    index = _index_of(
        {
            "/repo/one/shared/ids.py": definition,
            "/repo/two/shared/ids.py": definition,
            "/repo/app.py": "from shared.ids import EventId\n",
        }
    )
    assert index.resolve_local_name("/repo/app.py", "EventId") is None


def test_name_matching_exactly_one_module_resolves_through_the_import() -> None:
    index = _index_of(
        {
            "/repo/one/shared/ids.py": textwrap.dedent("""\
            from typing import NewType

            EventId = NewType("EventId", str)
        """),
            "/repo/app.py": "from shared.ids import EventId\n",
        }
    )
    resolved = index.resolve_local_name("/repo/app.py", "EventId")
    assert resolved is not None
    assert resolved.module == "/repo/one/shared/ids.py"
    assert resolved.name == "EventId"
