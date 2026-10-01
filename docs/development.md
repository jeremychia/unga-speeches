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

**Download the corpus by hand first.** Put `Speakers_by_session.xlsx` and `UNGDC_1946-2025.tar.gz` from the [corpus page](https://doi.org/10.7910/DVN/0TJX8Y) into `data/raw/ungdc/`. Harvard Dataverse asks for a name, email, institution and purpose before the download.

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

## Rerunning and checking the results

**Deterministic, given the same downloads.** Every step after the download is fixed code with no randomness: extracting the PDFs and pages, splitting the records, matching countries and outlets, the topic model (fixed seed), the clustering, and every figure on the page. `make reproducible SESSION=81` builds the page twice and fails if any file differs. The one line that changes from day to day is the build date in the footer.

**Not deterministic: the web.** Pages can change or disappear after they are downloaded. Each download is cached under `data/raw/` with its URL, time and SHA-256 in `data/raw/manifest.jsonl`, so a rerun reads the same bytes; `--refresh` downloads again, and the news and leanings histories record what changed.

**Not reproducible: how the source lists were found.** The news reports and the rating pages were found with a search tool, partly by assistant agents, and search results change. What was found is committed (`reference/news_<session>.csv`, `reference/outlets.csv`, `reference/dnr_brands_2026.csv`), and `docs/news-sourcing.md` logs each search, so the lists can be checked and rerun, but not re-derived.

**To rerun from scratch:** `make session`, `make verbatim`, `make scanned`, `make history`, `make dataset`, `make news`, `make brands`, `make leanings` and `make site`, with the sessions wanted. The downloads are not committed; a published release carries the tables.
