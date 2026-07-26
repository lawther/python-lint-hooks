"""Generate markdown documentation files for each rule from the code.

Usage: uv run python scripts/generate_rule_docs.py
"""

from __future__ import annotations

import argparse
import inspect
import sys
import textwrap
from pathlib import Path

# Ensure the src layout is on the path when run from the repo root.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import ml_lints.rules  # noqa: F401, E402 — triggers auto-import of all rule modules
from ml_lints.rules import all_rules  # noqa: E402


def generate_doc(cls: type[ml_lints.rules.Rule], out_dir: Path, check: bool = False) -> bool:
    docstring = inspect.getdoc(cls)
    if not docstring:
        print(f"ERROR: Rule {cls.code} is missing a rationale (class docstring).", file=sys.stderr)
        sys.exit(1)

    md_lines = [
        f"# {cls.code}: {cls.summary}",
        "",
        f"**Suggestion:** {cls.suggestion}",
        "",
        "## Rationale",
        "",
        docstring,
        "",
    ]

    exemptions = getattr(cls, "exemptions", None)
    if exemptions:
        md_lines.extend([
            "## Automatic Exemptions",
            "",
            exemptions,
            "",
        ])

    try:
        bad_example = cls.bad_example
        if bad_example:
            md_lines.extend([
                "## Bad Example",
                "",
                "```python",
                textwrap.dedent(bad_example).strip(),
                "```",
                "",
            ])
    except AttributeError:
        print(f"ERROR: Rule {cls.code} is missing mandatory 'bad_example' field.", file=sys.stderr)
        sys.exit(1)

    try:
        good_examples = cls.good_examples
        if good_examples:
            header = "Good Example" if len(good_examples) == 1 else "Good Examples"
            md_lines.extend([
                f"## {header}",
                "",
            ])
            for ex in good_examples:
                md_lines.extend([
                    "```python",
                    textwrap.dedent(ex).strip(),
                    "```",
                    "",
                ])
    except AttributeError:
        print(f"ERROR: Rule {cls.code} is missing mandatory 'good_examples' field.", file=sys.stderr)
        sys.exit(1)

    out_file = out_dir / f"{cls.code}.md"
    new_content = "\n".join(md_lines)

    if check:
        if not out_file.exists() or out_file.read_text(encoding="utf-8") != new_content:
            return False
        return True

    out_file.write_text(new_content, encoding="utf-8")
    print(f"Generated {out_file}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rule", help="Only generate docs for a specific rule code (e.g. ML100)")
    parser.add_argument("--check", action="store_true", help="Exit 1 if docs are out of date")
    args = parser.parse_args()

    docs_dir = Path(__file__).parent.parent / "docs" / "rules"
    docs_dir.mkdir(parents=True, exist_ok=True)

    any_out_of_date = False
    requested_rule = args.rule.upper() if args.rule else None
    for cls in all_rules():
        if requested_rule and cls.code != requested_rule:
            continue
        if not generate_doc(cls, docs_dir, check=args.check):
            print(f"ERROR: Documentation for {cls.code} is out of date.", file=sys.stderr)
            any_out_of_date = True

    if args.check and any_out_of_date:
        print("\nSome rule documentation is out of date. Run `just docs-rules` to update it.", file=sys.stderr)
        sys.exit(1)
    elif args.check:
        print("All rule documentation is up to date.")


if __name__ == "__main__":
    main()
