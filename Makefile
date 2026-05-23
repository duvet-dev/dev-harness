# Dev Harness — Build, Test, Package
#
# Targets:
#   install       — Install package in editable mode with dev deps
#   test          — Run full test suite (unit + functional)
#   test-ci       — Run test suite with warnings-as-errors (CI mode)
#   test-e2e      — Run end-to-end tests only (requires live services)
#   lint          — Run linters (ruff)
#   build         — Build Python wheel
#   build-exe     — Build single-file executable (alpha, macOS/Linux)
#   download-temporal — Download Temporal CLI dev server binary
#   clean         — Remove build artifacts
#   publish       — Build and publish to internal registry

SHELL := /bin/bash
PYTHON := python3
PIP    := pip3

# Detect platform for Temporal download
UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)

ifeq ($(UNAME_S),Darwin)
	TEMPORAL_OS := darwin
else ifeq ($(UNAME_S),Linux)
	TEMPORAL_OS := linux
else
	$(error Unsupported OS: $(UNAME_S))
endif

ifeq ($(UNAME_M),arm64)
	TEMPORAL_ARCH := arm64
else ifeq ($(UNAME_M),x86_64)
	TEMPORAL_ARCH := amd64
else ifneq (,$(findstring $(UNAME_M),aarch64 amd64))
	TEMPORAL_ARCH := $(UNAME_M)
else
	$(error Unsupported architecture: $(UNAME_M) — only arm64 and amd64 are supported)
endif

# Temporal version pin — update this to use a newer release
TEMPORAL_VERSION := 0.12.0
TEMPORAL_DIR     := scripts/_temporal
TEMPORAL_BIN     := $(TEMPORAL_DIR)/temporal

# ── Installation ──────────────────────────────────────────────────────────

.PHONY: install
install: download-temporal
	$(PIP) install -e ".[dev]"
	@echo ""
	@echo "✓ Dev Harness installed. Run 'harness --help' to get started."

.PHONY: install-deps
install-deps:
	$(PIP) install -e ".[dev]"

# ── Testing ───────────────────────────────────────────────────────────────

.PHONY: test
test:
	python3 -m pytest tests/ -W error::RuntimeWarning --tb=short -q
	@echo ""
	@echo "✓ All functional tests passed."

# ── CI ────────────────────────────────────────────────────────────────────

.PHONY: ci
test-ci: lint test-coverage
	@echo "✓ CI checks passed."

.PHONY: ci
ci: test-ci
	@true

.PHONY: test-coverage
test-coverage:
	@python3 -m pytest \
		tests/ \
		-W error::RuntimeWarning \
		--tb=short \
		--cov=src/harness \
		--cov-report=term-missing:skip-covered \
		--quiet 2>&1
	@echo "Tests: OK"

.PHONY: test-e2e
test-e2e:
	python3 -m pytest -m e2e --tb=short -v
	@echo ""
	@echo "✓ E2E tests complete."

.PHONY: test-verbose
test-verbose:
	python3 -m pytest tests/ -W error::RuntimeWarning --tb=long -v --durations=10 2>&1

# ── Linting ───────────────────────────────────────────────────────────────

.PHONY: lint
lint:
	@python3 -m ruff check src/harness/ tests/ 2>&1
	@echo "Lint: OK"

.PHONY: check-types
check-types:
	# Type checking (if mypy is available)
	@which mypy > /dev/null 2>&1 && mypy src/harness/ || echo "mypy not installed — skipping type check"

# ── Build ─────────────────────────────────────────────────────────────────

.PHONY: build
build: clean download-temporal
	$(PYTHON) -m build
	@echo ""
	@echo "✓ Wheel built. See dist/"

.PHONY: build-exe
build-exe: download-temporal
	@echo "Building single executable (requires PyInstaller)..."
	@which pyinstaller > /dev/null 2>&1 || { \
		echo "PyInstaller not found. Install with: pip install pyinstaller"; \
		exit 1; \
	}
	pyinstaller \
		--onefile \
		--name harness \
		--add-binary "$(TEMPORAL_BIN):./_temporal" \
		--hidden-import harness \
		--hidden-import harness.cli \
		src/harness/entry.py
	@echo ""
	@echo "✓ Single executable built: dist/harness"

# ── Temporal CLI download ─────────────────────────────────────────────────

.PHONY: download-temporal
download-temporal: $(TEMPORAL_BIN)

$(TEMPORAL_BIN):
	@echo "Downloading Temporal CLI v$(TEMPORAL_VERSION) for $(TEMPORAL_OS)/$(TEMPORAL_ARCH)..."
	mkdir -p $(TEMPORAL_DIR)
	# Download archive
	curl -sL \
		"https://github.com/temporalio/cli/releases/download/v$(TEMPORAL_VERSION)/temporal_cli_$(TEMPORAL_VERSION)_$(TEMPORAL_OS)_$(TEMPORAL_ARCH).tar.gz" \
		-o /tmp/temporal.tar.gz
	# Extract just the temporal binary
	tar -xzf /tmp/temporal.tar.gz -C $(TEMPORAL_DIR) temporal 2>/dev/null || \
	tar -xzf /tmp/temporal.tar.gz -C $(TEMPORAL_DIR) temporal.exe 2>/dev/null || \
	(echo "Failed to extract temporal binary" && exit 1)
	chmod +x $(TEMPORAL_BIN)
	rm -f /tmp/temporal.tar.gz
	@echo "✓ Temporal CLI downloaded to $(TEMPORAL_BIN)"

# ── Clean ─────────────────────────────────────────────────────────────────

.PHONY: clean
clean:
	rm -rf dist/ build/ *.egg-info/ .pytest_cache/ .ruff_cache/
	rm -rf $(TEMPORAL_DIR)
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	@echo "✓ Cleaned build artifacts"

.PHONY: clean-all
clean-all: clean
	rm -rf .venv/

# ── Publish ───────────────────────────────────────────────────────────────

.PHONY: publish
publish: build
	@echo "Publishing to internal registry..."
	# TODO: configure your internal PyPI registry
	# twine upload --repository-url <internal-registry> dist/*
	@echo "✓ Published (stub — configure your registry URL in Makefile)"

# ── Help ──────────────────────────────────────────────────────────────────

.DEFAULT_GOAL := test

.PHONY: help
help:
	@echo "Dev Harness Make targets:"
	@echo ""
	@echo "  install           Install package with dev dependencies"
	@echo "  test              Run full test suite (unit + functional)"
	@echo "  test-ci           CI test suite (warnings-as-errors)"
	@echo "  test-e2e          End-to-end tests (on-demand only)"
	@echo "  coverage          Test with coverage report"
	@echo "  lint              Run linters"
	@echo "  build             Build Python wheel"
	@echo "  build-exe         Build single-file executable (alpha)"
	@echo "  clean             Remove build artifacts"
	@echo "  publish           Build and publish to registry"
