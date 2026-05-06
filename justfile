# Run all lints and formatting
lint:
    @uv run ruff format src/ tests/
    @uv run ruff check --fix src/ tests/
    @uv run ty check src/ tests/

# Run tests
test:
    @uv run pytest

# Run all pre-commit checks
precommit:
    just lint
    just test
