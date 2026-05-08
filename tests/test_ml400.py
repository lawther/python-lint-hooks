import textwrap
from pathlib import Path

from python_lint_hooks.checker import check_file


def _check(code: str, tmp_path: Path) -> list:
    path = tmp_path / "sample.py"
    path.write_text(code, encoding="utf-8")
    return check_file(path)


def _codes(violations: list) -> list[str]:
    return [v.code for v in violations]


def test_unvalidated_external_data_flagged(tmp_path: Path) -> None:
    code = """
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
    """
    violations = _check(textwrap.dedent(code), tmp_path)
    codes = _codes(violations)
    assert "ML400" in codes
    # Should be flagged once at the source
    ml400_violations = [v for v in violations if v.code == "ML400"]
    assert len(ml400_violations) == 1


def test_unvalidated_data_direct_access_flagged(tmp_path: Path) -> None:
    code = """
        import json
        def foo():
            data = json.loads('{"a": 1}')
            print(data["a"])
    """
    violations = _check(textwrap.dedent(code), tmp_path)
    assert "ML400" in _codes(violations)


def test_validated_data_no_violation(tmp_path: Path) -> None:
    code = """
        import json
        from pydantic import BaseModel
        class MyModel(BaseModel):
            a: int
        def foo():
            raw = json.loads('{"a": 1}')
            data = MyModel.model_validate(raw)
            print(data.a) # Not indexing 'raw', so no violation
    """
    violations = _check(textwrap.dedent(code), tmp_path)
    assert "ML400" not in _codes(violations)


def test_noqa_ml400_suppresses(tmp_path: Path) -> None:
    code = """
        import json
        def foo():
            data = json.loads('{"a": 1}')
            print(data["a"]) # noqa: ML400
    """
    violations = _check(textwrap.dedent(code), tmp_path)
    assert "ML400" not in _codes(violations)


def test_unvalidated_data_reassigned_ok(tmp_path: Path) -> None:
    code = """
        import json
        def foo():
            data = json.loads('{"a": 1}')
            data = {"safe": "data"}
            print(data["safe"])
    """
    violations = _check(textwrap.dedent(code), tmp_path)
    assert "ML400" not in _codes(violations)


def test_unvalidated_data_shadowed_ok(tmp_path: Path) -> None:
    code = """
        import json
        def outer():
            data = json.loads('{"a": 1}')
            def inner():
                data = {"safe": "data"}
                print(data["safe"]) # Should be OK
            print(data["a"]) # Should be violation
    """
    violations = _check(textwrap.dedent(code), tmp_path)
    codes = _codes(violations)
    assert "ML400" in codes
    assert len([v for v in violations if v.code == "ML400"]) == 1


def test_regression_user_snippet(tmp_path: Path) -> None:
    code = """
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
    """
    violations = _check(textwrap.dedent(code), tmp_path)
    ml400_violations = [v for v in violations if v.code == "ML400"]
    # Should be flagged 1 time at the source
    assert len(ml400_violations) == 1
    assert "v" in ml400_violations[0].message
