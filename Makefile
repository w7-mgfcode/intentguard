.DEFAULT_GOAL := help

.PHONY: help setup data baseline train evaluate serve demo lint test

help: ## Show the developer command contract
	@awk 'BEGIN {FS = ":.*## "; printf "IntentGuard commands:\n"} /^[a-zA-Z_-]+:.*## / {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Install the Python 3.11 locked environment
	uv sync --locked --all-groups

data: ## Download, validate, and record pinned BANKING77 provenance (U02)
	uv run --locked python scripts/prepare_data.py

baseline: ## Train and evaluate the lexical baseline (U03)
	@printf '%s\n' 'Not implemented — tracked by U03' >&2
	@false

train: ## Fine-tune DistilBERT and persist the selected threshold (U04)
	@printf '%s\n' 'Not implemented — tracked by U04' >&2
	@false

evaluate: ## Evaluate the immutable artifact on test data (U05)
	@printf '%s\n' 'Not implemented — tracked by U05' >&2
	@false

serve: ## Serve the real immutable artifact through FastAPI (U06)
	@printf '%s\n' 'Not implemented — tracked by U06' >&2
	@false

demo: ## Run the strict real-artifact demonstration (U06)
	@printf '%s\n' 'Not implemented — tracked by U06' >&2
	@false

lint: ## Run Ruff, mypy, and repository-foundation validation
	uv run --locked ruff check .
	uv run --locked mypy src scripts tests
	uv run --locked python scripts/validate_foundation.py

test: ## Run the truthful foundation test suite
	uv run --locked pytest -q
