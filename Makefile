.PHONY: help install test session history

SESSION ?= 81

help:
	@echo "make install              - install dependencies with uv"
	@echo "make test                 - run the unit tests"
	@echo "make session SESSION=81   - scrape, extract and render one session (64 onwards)"
	@echo "make history              - merge the UN General Debate Corpus (1946 onwards); needs its files in data/raw/ungdc/"

install:
	uv sync

test:
	uv run pytest -q

session:
	uv run unga session $(SESSION)

history:
	uv run unga history
