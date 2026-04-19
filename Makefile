PYTHON ?= python3
UV ?= uv

.PHONY: setup dev test lint format install uninstall

setup:
	$(UV) sync --dev

dev:
	$(UV) run adv-archon

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check .
	$(UV) run mypy

format:
	$(UV) run ruff format .

install:
	./scripts/install.sh

uninstall:
	./scripts/uninstall.sh

