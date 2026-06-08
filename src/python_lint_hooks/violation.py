"""Violation dataclass — a single rule violation found in a source file."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique
from pathlib import Path


@unique
class RuleCode(StrEnum):
    ML100 = "ML100"
    ML101 = "ML101"
    ML102 = "ML102"
    ML103 = "ML103"
    ML104 = "ML104"
    ML105 = "ML105"
    ML106 = "ML106"
    ML107 = "ML107"
    ML108 = "ML108"
    ML109 = "ML109"
    ML200 = "ML200"
    ML201 = "ML201"
    ML202 = "ML202"
    ML300 = "ML300"
    ML400 = "ML400"
    ML500 = "ML500"
    ML501 = "ML501"
    ML110 = "ML110"
    # -- add new codes above this line --


@dataclass(frozen=True)
class Violation:
    """A single rule violation found in a source file."""

    code: RuleCode
    message: str
    path: Path
    line: int
    col: int

    def format(self) -> str:
        return f"{self.path}:{self.line}:{self.col}: {self.code} {self.message}"
