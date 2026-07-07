.PHONY: *

lint:
	uv run ruff check .

typecheck:
	uv run ty check

check: lint typecheck
