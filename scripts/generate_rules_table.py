"""Generate the rules table in README.md from the registered rule metadata.

Usage: uv run python scripts/generate_rules_table.py [--check]

With --check: exits 1 if README.md is out of date (for CI/pre-commit enforcement).
Without --check: rewrites README.md in place.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the src layout is on the path when run from the repo root.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import ml_lints.rules  # noqa: F401 — triggers auto-import of all rule modules
from ml_lints.rules import all_rules

_START = "<!-- rules-table-start -->"
_END = "<!-- rules-table-end -->"


def _build_table() -> str:
    rules = sorted(all_rules(), key=lambda cls: cls.code)
    lines = [
        _START,
        "| Code | Description | Suggestion |",
        "|------|-------------|------------|",
    ]
    for cls in rules:
        code_link = f"[`{cls.code}`](docs/rules/{cls.code}.md)"
        lines.append(f"| {code_link} | {cls.summary} | {cls.suggestion} |")
    lines.append(_END)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Exit 1 if README is out of date")
    args = parser.parse_args()

    readme = Path(__file__).parent.parent / "README.md"
    content = readme.read_text(encoding="utf-8")

    start_idx = content.find(_START)
    end_idx = content.find(_END)

    if start_idx == -1 or end_idx == -1:
        print("ERROR: rules-table markers not found in README.md", file=sys.stderr)
        sys.exit(1)

    new_table = _build_table()
    new_content = content[:start_idx] + new_table + content[end_idx + len(_END) :]

    if args.check:
        if new_content != content:
            print("README.md rules table is out of date. Run `just docs-rules` to update it.", file=sys.stderr)
            sys.exit(1)
        print("README.md rules table is up to date.")
    else:
        readme.write_text(new_content, encoding="utf-8")
        print("README.md rules table updated.")


if __name__ == "__main__":
    main()
