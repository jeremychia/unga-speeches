.PHONY: help install test lint format session verbatim history dataset release publish

SESSION ?= 81
SESSIONS ?= 79
ARGS ?=

help:
	@echo "make install                    - install dependencies with uv"
	@echo "make test                       - run the unit tests (no network)"
	@echo "make lint                       - check style and formatting with ruff"
	@echo "make session SESSION=81         - build one session from gadebate.un.org (64 onwards)"
	@echo "make verbatim SESSIONS='78 79'  - split the UN verbatim records of these sessions (48 onwards)"
	@echo "make history                    - load the UN General Debate Corpus; needs its files in data/raw/ungdc/"
	@echo "make dataset                    - combine everything into data/output/speeches.parquet"
	@echo "make release                    - package the data into dist/"
	@echo "make publish                    - upload dist/ as a GitHub release"

install:
	uv sync

test:
	uv run pytest -q

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

format:
	uv run ruff check --fix src tests
	uv run ruff format src tests

session:
	uv run unga session $(SESSION) $(ARGS)

verbatim:
	uv run unga verbatim $(SESSIONS)

history:
	uv run unga history

dataset:
	uv run unga dataset

release:
	uv run unga release

publish: release
	gh release create "$$(cat dist/TAG)" dist/*.parquet dist/*.csv dist/*.zip dist/SHA256SUMS \
		--title "Data $$(cat dist/TAG | cut -d- -f2-)" --notes-file reports/sources.md
