"""Violation dataclass — a single rule violation found in a source file."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Violation:
    """A single rule violation found in a source file."""

    code: str
    message: str
    path: Path
    line: int
    col: int

    def format(self) -> str:
        return f"{self.path}:{self.line}:{self.col}: {self.code} {self.message}"
