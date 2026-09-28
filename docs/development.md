# Development

## Set up

```bash
make install   # uv sync
make test      # unit tests, no network
make lint      # ruff check and format check
```

Downloads and outputs go to `data/`, which git ignores. Set `UNGA_DATA_DIR` to keep them elsewhere; the full cache is about 1.5 GB.

## Build the dataset

```bash
make verbatim SESSIONS="$(seq -s ' ' 48 79)"   # UN records, 1993–2024
make session SESSION=81                        # one debate site session, 64 onwards
make history                                   # the corpus; needs its files in data/raw/ungdc/
make dataset                                   # combine into data/output/speeches.parquet
```

Every step is cached, so rerunning is cheap and resumes where a run stopped. Requests are spaced one second apart, and failed requests are retried.

## Each September

1. **During the debate**, run `make session SESSION=<n> ARGS=--refresh-pages` daily. It picks up newly published speeches and transcripts, and keeps the cached pdfs.
2. **When the debate closes**, check [`reports/completeness_<n>.md`](../reports/) for pending pages and gaps.
3. **When the UN publishes the records** (`A/<n>/PV.x`, usually months later), run `make verbatim SESSIONS=<n>`, then `make dataset`. The records settle the spoken language of every speech.
4. **When the corpus publishes a new version**, replace its files in `data/raw/ungdc/` and run `make history dataset`.

## Close a text gap by hand

Add a row to [`reference/manual_sources.csv`](../reference/manual_sources.csv) with the session, the delegation's slug, the language, the url and a CSS selector for the speech body, then rerun the session. The text is stored with its url and checksum like any other source.

## Publish a data release

`make release` packages `speeches.parquet`, `speeches.csv`, `rights_of_reply.parquet` and the speech pages into `dist/` with a checksum file. `make publish` uploads them as a GitHub release tagged `data-<date>`.

## Tests

Tests in [`tests/`](../tests/) run against saved pages in `tests/fixtures/`, never the network. Add a fixture when a new page layout appears, and a test for the rule that handles it.
