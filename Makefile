.DEFAULT_GOAL := help

.PHONY: help setup data baseline train evaluate serve demo lint test

help: ## Show the developer command contract
	@awk 'BEGIN {FS = ":.*## "; printf "IntentGuard commands:\n"} /^[a-zA-Z_-]+:.*## / {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Install the Python 3.11 locked environment
	uv sync --locked --all-groups

data: ## Download, validate, and record pinned BANKING77 provenance (U02)
	uv run --locked python scripts/prepare_data.py

baseline: ## Train, persist, reload, and measure the lexical baseline (U03)
	uv run --locked python scripts/train_baseline.py

train: ## Fine-tune DistilBERT and persist the selected threshold (U04)
	uv run --locked python scripts/train_transformer.py

evaluate: ## Compare both immutable artifacts on the untouched test split (U05)
	uv run --locked python scripts/evaluate.py

serve: ## Serve the real immutable artifact through FastAPI (U06)
	uv run --locked python -m intentguard.app

demo: ## Run the strict real-artifact demonstration (U06)
	uv run --locked python scripts/demo.py

lint: ## Run Ruff, mypy, and repository-foundation validation
	uv run --locked ruff check .
	uv run --locked mypy src scripts tests
	uv run --locked python scripts/validate_foundation.py

test: ## Run the truthful foundation test suite
	uv run --locked pytest -q
