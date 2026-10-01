.PHONY: help install test lint format reproducible session verbatim scanned history dataset news brands leanings site release publish

SESSION ?= 81
SESSIONS ?= 79
ARGS ?=

help:
	@echo "make install                    - install dependencies with uv"
	@echo "make test                       - run the unit tests (no network)"
	@echo "make reproducible SESSION=81    - build the page twice from the cached downloads and fail if any file differs"
	@echo "make lint                       - check style and formatting with ruff"
	@echo "make session SESSION=81         - build one session from gadebate.un.org (64 onwards)"
	@echo "make verbatim SESSIONS='78 79'  - split the UN verbatim records of these sessions (48 onwards)"
	@echo "make scanned SESSIONS='1 2'     - split the UN's scanned records of these sessions (1 to 47, 1946-1992) into speeches"
	@echo "make history                    - load the UN General Debate Corpus; needs its files in data/raw/ungdc/"
	@echo "make dataset                    - combine everything into data/output/speeches.parquet"
	@echo "make news SESSION=81            - download the session's news reports and the UN coverage of each speaker"
	@echo "make brands                     - download the Digital News Report's biggest online news brands per market"
	@echo "make leanings SESSION=81        - refresh outlet leanings and record any change in reference/leanings_history.json"
	@echo "make site SESSION=81            - write the session's analysis page to site/"
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

scanned:
	uv run unga scanned $(SESSIONS)

history:
	uv run unga history

dataset:
	uv run unga dataset

news:
	uv run unga news $(SESSION) $(ARGS)

brands:
	uv run unga brands

leanings:
	uv run unga leanings $(SESSION)

site:
	uv run --group analysis unga site $(SESSION)

release:
	uv run unga release

publish: release
	gh release create "$$(cat dist/TAG)" dist/*.parquet dist/*.csv dist/*.zip dist/SHA256SUMS \
		--title "Data $$(cat dist/TAG | cut -d- -f2-)" --notes-file reports/sources.md

reproducible:
	uv run --group analysis unga site $(SESSION) && shasum -a 256 site/data.json site/index.html site/figures/*.svg > /tmp/unga-build-1.sha
	uv run --group analysis unga site $(SESSION) && shasum -a 256 site/data.json site/index.html site/figures/*.svg > /tmp/unga-build-2.sha
	diff /tmp/unga-build-1.sha /tmp/unga-build-2.sha && echo "the two builds are identical"
