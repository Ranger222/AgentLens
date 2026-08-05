.DEFAULT_GOAL := help
SHELL := /bin/bash
PY ?= python3
VENV := .venv

.PHONY: help venv install install-frontend lint type test test-cov fmt \
        frontend-test frontend-build demo serve verify build clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

venv: ## Create the Python virtualenv
	$(PY) -m venv $(VENV) || uv venv $(VENV)

install: ## Install the package (editable) with dev + server deps
	$(VENV)/bin/pip install -e ".[dev]" || uv pip install -e ".[dev]"

install-frontend: ## Install frontend npm deps
	cd frontend && npm install --no-audit --no-fund

lint: ## Ruff lint
	$(VENV)/bin/ruff check src tests

fmt: ## Ruff autoformat + fix
	$(VENV)/bin/ruff check src tests --fix
	$(VENV)/bin/ruff format src tests

type: ## mypy type-check
	$(VENV)/bin/mypy

test: ## Run Python tests
	$(VENV)/bin/pytest -q

test-cov: ## Run Python tests with coverage
	$(VENV)/bin/pytest -q --cov=lenstrace --cov-report=term-missing

frontend-test: ## Run frontend tests
	cd frontend && npm run test

frontend-build: ## Build the frontend
	cd frontend && npm run build

demo: ## Generate sample traces (no API keys)
	$(VENV)/bin/lenstrace demo -n 3

serve: ## Launch the dashboard
	$(VENV)/bin/lenstrace serve

verify: ## Run the full verify harness (the green-gate)
	./scripts/verify.sh

build: frontend-build ## Build a wheel with the UI vendored in
	rm -rf src/lenstrace/_webui && cp -r frontend/dist src/lenstrace/_webui
	$(VENV)/bin/python -m build --wheel --no-isolation
	rm -rf src/lenstrace/_webui

clean: ## Remove build/test artifacts
	rm -rf dist build .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage \
	       src/lenstrace/_webui src/*.egg-info frontend/dist
	find . -type d -name __pycache__ -not -path '*/node_modules/*' -exec rm -rf {} + 2>/dev/null || true
