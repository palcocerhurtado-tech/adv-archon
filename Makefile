PYTHON ?= python3
UV ?= uv

.PHONY: setup dev test lint format install uninstall \
        bundle-macos bundle-macos-universal bundle-macos-signed

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

# ── macOS standalone .app (PyInstaller, free — no Apple account required) ─────
bundle-macos:
	@./scripts/build_macos.sh

bundle-macos-universal:
	@./scripts/build_macos.sh --universal

bundle-macos-signed:
	@./scripts/build_macos.sh --sign
