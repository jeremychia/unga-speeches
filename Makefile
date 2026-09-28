.PHONY: help install test session verbatim history dataset

SESSION ?= 81
SESSIONS ?= 79
ARGS ?=

help:
	@echo "make install                    - install dependencies with uv"
	@echo "make test                       - run the unit tests"
	@echo "make session SESSION=81         - scrape, extract and render one session from gadebate.un.org (64 onwards)"
	@echo "make verbatim SESSIONS='78 79'  - split the UN verbatim records of these sessions (48 onwards)"
	@echo "make history                    - load the UN General Debate Corpus (1946 onwards); needs its files in data/raw/ungdc/"
	@echo "make dataset                    - combine everything into data/output/speeches.parquet"

install:
	uv sync

test:
	uv run pytest -q

session:
	uv run unga session $(SESSION) $(ARGS)

verbatim:
	uv run unga verbatim $(SESSIONS)

history:
	uv run unga history

dataset:
	uv run unga dataset
