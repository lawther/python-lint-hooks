"""Verification tests for rule examples.

This test suite iterates over all registered rules and ensures that:
1. The `bad_example` actually triggers the rule.
2. Every `good_example` does NOT trigger ANY rule (ML or Ruff).

This ensures the documentation remains accurate and synchronized with the code.
"""

from __future__ import annotations

import subprocess
import textwrap
from typing import TYPE_CHECKING

import pytest

from python_lint_hooks.rules import Rule, all_rules
from tests.conftest import check

if TYPE_CHECKING:
    from pathlib import Path


# Standard imports to ensure examples are valid Python and focus on the rule logic.
# We include
PRELUDE = textwrap.dedent("""\
    # ruff: noqa: F401, I001
    from __future__ import annotations

    import collections.abc
    import json
    import typing
    from collections.abc import Mapping, MutableMapping
    from dataclasses import dataclass
    from datetime import datetime
    from pathlib import Path
    from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple, NewType, Optional, Union

    from pydantic import BaseModel
""").strip()


@pytest.mark.parametrize("rule_cls", all_rules(), ids=lambda cls: cls.code)
def test_rule_metadata_is_complete(rule_cls: type[Rule]) -> None:
    """Verify that every rule subclass has its own unique rationale and examples."""
    # Ensure docstring is not inherited from the base class (Rule)
    doc = rule_cls.__dict__.get("__doc__")
    assert doc and doc.strip(), f"Rule {rule_cls.code} is missing a unique rationale (class docstring)."

    assert rule_cls.bad_example.strip(), f"Rule {rule_cls.code} is missing a 'bad_example'."
    assert len(rule_cls.good_examples) > 0, f"Rule {rule_cls.code} is missing 'good_examples'."


@pytest.mark.parametrize("rule_cls", all_rules(), ids=lambda cls: cls.code)
def test_rule_examples_are_valid_and_accurate(rule_cls: type[Rule], tmp_path: Path) -> None:
    """Verify that the rule's examples behave as documented."""
    # Test Bad Example: must trigger at least one violation of THIS rule code.
    if rule_cls.bad_example:
        code = PRELUDE + "\n\n" + textwrap.dedent(rule_cls.bad_example).strip()
        violations = check(code, tmp_path)
        relevant_violations = [v for v in violations if v.code == rule_cls.code]

        assert len(relevant_violations) >= 1, (
            f"Rule {rule_cls.code} 'bad_example' did not trigger any {rule_cls.code} violations.\n\n"
            f"Example code tested:\n{code}"
        )

    # Test Good Examples: must trigger zero violations of ANY rule.
    for i, example_code in enumerate(rule_cls.good_examples):
        code = PRELUDE + "\n\n" + textwrap.dedent(example_code).strip()
        violations = check(code, tmp_path)
        # Check against our own ML rules (ALL of them)
        assert len(violations) == 0, (
            f"Rule {rule_cls.code} 'good_example' (index {i}) triggered violations.\n\n"
            f"Example code tested:\n{code}\n\n"
            f"Violations found: {[(v.code, v.message) for v in violations]}"
        )

        # Check against ruff
        path = tmp_path / f"example_{rule_cls.code}_{i}.py"
        path.write_text(code + "\n", encoding="utf-8")
        result = subprocess.run(  # noqa: S603
            ["uv", "run", "ruff", "check", "--ignore", "ANN201,RUF100", str(path)],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"Rule {rule_cls.code} 'good_example' (index {i}) failed ruff check.\n\n"
            f"Ruff output:\n{result.stdout}\n{result.stderr}"
        )
