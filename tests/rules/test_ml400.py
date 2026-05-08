"""Tests for ML400 — unvalidated external data used without Pydantic validation."""

from __future__ import annotations

import textwrap
from pathlib import Path

from tests.conftest import check, codes


def test_unvalidated_external_data_flagged(tmp_path: Path) -> None:
    code = textwrap.dedent("""
        import json
        import subprocess

        def get_versions():
            result = subprocess.run(["cmd"], capture_output=True, text=True)
            raw_versions = json.loads(result.stdout)

            versions = [
                SecretVersion(
                    name=v["name"],
                    state=v.get("state", "UNKNOWN"),
                )
                for v in raw_versions
            ]
            return versions
    """)
    violations = check(code, tmp_path)
    all_codes = codes(violations)
    assert "ML400" in all_codes
    # Should be flagged once at the source, not once per usage
    ml400_violations = [v for v in violations if v.code == "ML400"]
    assert len(ml400_violations) == 1


def test_unvalidated_data_direct_access_flagged(tmp_path: Path) -> None:
    code = textwrap.dedent("""
        import json
        def foo():
            data = json.loads('{"a": 1}')
            print(data["a"])
    """)
    violations = check(code, tmp_path)
    assert "ML400" in codes(violations)


def test_validated_data_no_violation(tmp_path: Path) -> None:
    # Accessing data.a on the validated model is fine; only raw is tainted.
    code = textwrap.dedent("""
        import json
        from pydantic import BaseModel
        class MyModel(BaseModel):
            a: int
        def foo():
            raw = json.loads('{"a": 1}')
            data = MyModel.model_validate(raw)
            print(data.a)
    """)
    violations = check(code, tmp_path)
    assert "ML400" not in codes(violations)


def test_noqa_ml400_suppresses(tmp_path: Path) -> None:
    code = textwrap.dedent("""
        import json
        def foo():
            data = json.loads('{"a": 1}')
            print(data["a"]) # noqa: ML400
    """)
    violations = check(code, tmp_path)
    assert "ML400" not in codes(violations)


def test_unvalidated_data_reassigned_ok(tmp_path: Path) -> None:
    # Reassigning the variable clears taint.
    code = textwrap.dedent("""
        import json
        def foo():
            data = json.loads('{"a": 1}')
            data = {"safe": "data"}
            print(data["safe"])
    """)
    violations = check(code, tmp_path)
    assert "ML400" not in codes(violations)


def test_unvalidated_data_shadowed_ok(tmp_path: Path) -> None:
    # Inner scope reassignment shadows the outer tainted variable; outer use still flags.
    code = textwrap.dedent("""
        import json
        def outer():
            data = json.loads('{"a": 1}')
            def inner():
                data = {"safe": "data"}
                print(data["safe"])
            print(data["a"])
    """)
    violations = check(code, tmp_path)
    all_codes = codes(violations)
    assert "ML400" in all_codes
    assert len([v for v in violations if v.code == "ML400"]) == 1


def test_for_loop_over_tainted_variable_flagged(tmp_path: Path) -> None:
    # A regular for loop is semantically equivalent to the list-comp in
    # test_regression_user_snippet, but exercises enter_For instead of
    # enter_ListComp → _handle_comprehension. Both paths must propagate taint to the
    # loop variable so that subscript access on it is flagged.
    code = textwrap.dedent("""
        import json
        import subprocess

        def process():
            result = subprocess.run(["cmd"], capture_output=True, text=True, check=True)
            raw_versions = json.loads(result.stdout)

            versions = []
            for v in raw_versions:
                versions.append(
                    SecretVersion(
                        name=v["name"],
                        state=v.get("state", "UNKNOWN"),
                    )
                )
            return versions
    """)
    violations = check(code, tmp_path)
    ml400_violations = [v for v in violations if v.code == "ML400"]
    # Flagged once at the source, not once per access
    assert len(ml400_violations) == 1
    assert "v" in ml400_violations[0].message


def test_annotated_assignment_from_untrusted_source_flagged(tmp_path: Path) -> None:
    # Type-annotated assignments (`data: dict = json.loads(...)`) are ubiquitous in
    # modern typed Python. enter_AnnAssign is a separate AST visitor from enter_Assign,
    # so a missing implementation there would silently let every annotated assignment
    # bypass ML400 — a genuine security gap.
    code = textwrap.dedent("""
        import json
        def foo():
            data: dict = json.loads('{"a": 1}')
            print(data["a"])
    """)
    violations = check(code, tmp_path)
    assert "ML400" in codes(violations)


def test_list_comprehension_directly_over_untrusted_call_flagged(tmp_path: Path) -> None:
    # When the comprehension iter IS the untrusted call (no intermediate variable),
    # _handle_comprehension must use gen.iter (an ast.expr with lineno) as the
    # source_node rather than gen itself (an ast.comprehension, which has no lineno).
    code = textwrap.dedent("""
        import json
        def foo():
            names = [v["name"] for v in json.loads('[{"name": "a"}]')]
    """)
    violations = check(code, tmp_path)
    assert "ML400" in codes(violations)


def test_starred_unpack_from_untrusted_source_flagged(tmp_path: Path) -> None:
    # _get_names must recurse into ast.Starred so that `*rest` in
    # `_first, *rest = json.loads(...)` is tainted. Without the Starred branch it
    # would fall through to `return []` and rest would silently escape validation.
    code = textwrap.dedent("""
        import json
        def foo():
            _first, *rest = json.loads('[{"a": 1}, {"b": 2}]')
            print(rest[0]["b"])
    """)
    violations = check(code, tmp_path)
    assert "ML400" in codes(violations)


def test_multi_generator_comprehension_only_tainted_iter_flagged(tmp_path: Path) -> None:
    # A list comprehension with two generators: one tainted, one safe.
    # _handle_comprehension must leave the safe loop variable clean so that
    # only access via the tainted variable triggers a violation.
    code = textwrap.dedent("""
        import json
        def foo():
            raw = json.loads('[{"name": "a"}]')
            suffixes = ["x", "y"]
            result = [v["name"] + s for v in raw for s in suffixes]
    """)
    violations = check(code, tmp_path)
    ml400_violations = [v for v in violations if v.code == "ML400"]
    assert len(ml400_violations) == 1
    assert "v" in ml400_violations[0].message


def test_for_loop_over_safe_iterable_clears_previously_tainted_variable(tmp_path: Path) -> None:
    # enter_For must always call _set_taint for the loop target, not only when
    # the iterable is tainted. If it skips the untainted case, a previously-tainted
    # variable reused as the loop target is never cleared, producing a false positive.
    code = textwrap.dedent("""
        import json
        def foo():
            data = json.loads('{"a": 1}')
            for data in [{"a": "safe"}]:
                print(data["a"])
    """)
    violations = check(code, tmp_path)
    assert "ML400" not in codes(violations)


def test_set_comprehension_loop_variable_does_not_produce_false_positive(tmp_path: Path) -> None:
    # Comprehensions push a fresh taint scope, so a loop variable that shadows a
    # tainted outer name must be treated as clean inside the comprehension body.
    # If the scope push is missing, the outer taint leaks in and every subscript
    # access on the loop variable fires a false positive.
    code = textwrap.dedent("""
        import json
        def foo():
            v = json.loads('[{"a": 1}]')
            safe = [{"a": "safe"}]
            names = {v["a"] for v in safe}
    """)
    violations = check(code, tmp_path)
    assert "ML400" not in codes(violations)


def test_attribute_assignment_target_does_not_taint(tmp_path: Path) -> None:
    # _get_names falls through to `return []` when the assignment target is an
    # ast.Attribute node (e.g. `self.data = json.loads(...)`). The attribute path
    # is not a trackable name in the local scope, so no taint is set and no
    # violation should fire when the same attribute is accessed later.
    code = textwrap.dedent("""
        import json
        class Processor:
            def load(self):
                self.data = json.loads('{"a": 1}')
            def use(self):
                print(self.data["a"])
    """)
    violations = check(code, tmp_path)
    assert "ML400" not in codes(violations)


def test_regression_user_snippet(tmp_path: Path) -> None:
    code = textwrap.dedent("""
        import json
        import subprocess

        def process():
            result = subprocess.run(["cmd"], capture_output=True, text=True, check=True)
            raw_versions = json.loads(result.stdout)

            versions = [
                SecretVersion(
                    name=v["name"],
                    state=v.get("state", "UNKNOWN"),
                    create_time=v.get("createTime", ""),
                )
                for v in raw_versions
            ]
            return versions
    """)
    violations = check(code, tmp_path)
    ml400_violations = [v for v in violations if v.code == "ML400"]
    # Flagged once at the source, not once per access
    assert len(ml400_violations) == 1
    assert "v" in ml400_violations[0].message
