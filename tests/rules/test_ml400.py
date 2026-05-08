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
