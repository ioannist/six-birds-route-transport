PYTHON ?= python3
PIP := $(PYTHON) -m pip
PYTEST := $(PYTHON) -m pytest
RUFF := $(PYTHON) -m ruff

.PHONY: test test-legacy lint format benchmark-suite discovery-smoke lean-build repro-all

test:
	$(PYTEST) -q

test-legacy:
	$(PYTEST) -q tests/legacy/test_smoke.py

lint:
	$(RUFF) check .

format:
	$(RUFF) format .

benchmark-suite:
	$(PYTHON) -m holonomy_memory run-benchmark-suite --seed 0

discovery-smoke:
	$(PYTHON) -m holonomy_memory run-discovery-smoke --seed 0

lean-build:
	cd lean && lake build

repro-all: test benchmark-suite discovery-smoke lean-build
