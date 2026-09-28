# unga-speeches

Every speech from the UN General Assembly's annual general debate, 1946 to 2026. Each row gives who spoke, the rank of office they spoke in, the language they spoke, and the text in English and in the original language. Every text links to where it came from, with a checksum, so it can be checked.

The speeches are found, read and split by a deterministic Python pipeline. No AI model or web search is involved in the extraction. The [methodology](docs/methodology.md) covers each step.

**Read the 2026 analysis:** [jeremychia.github.io/unga-speeches](https://jeremychia.github.io/unga-speeches/). It covers topics, issues, readability, what stood out, and four international relations lenses, with every quote checked against its source.

## At a glance

<!-- numbers -->

## Get the data

**Download** `speeches.parquet` from the latest [data release](https://github.com/jeremychia/unga-speeches/releases). The release also has a CSV without the texts, the replies to other speeches, and a readable page per speech.

**Or build it** (about 1.5 GB of downloads, cached, so reruns are cheap):

```bash
make install
make verbatim SESSIONS="$(seq -s ' ' 48 79)"   # UN records, 1993–2024
make session SESSION=81                        # the UN debate site, one session at a time
make history                                   # the research corpus, 1946–2025
make dataset
```

The corpus files have to be downloaded by hand first; see [development](docs/development.md).

## Where it comes from

| Years | Source |
| --- | --- |
| 1993–2024 | The UN's official verbatim records, split into speeches by this pipeline |
| 2009–2026 | [gadebate.un.org](https://gadebate.un.org): speaker pages, the statements delegations filed, and transcripts |
| 1946–2025 | The [UN General Debate Corpus](https://doi.org/10.7910/DVN/0TJX8Y) (Jankin, Baturo and Dasandi; CC0) |

**Where the sources overlap, they are compared.** [`reports/sources.md`](reports/sources.md) shows, per session, how closely the UN records and the corpus agree.

## Who is included

- **All 193 member states.** Afghanistan and Myanmar have given no speech from 2021 onwards, because who holds their UN seat is disputed.
- **Observers who speak:** the Holy See, the State of Palestine and the European Union.
- **UN officials:** the Secretary-General and the President of the General Assembly.
- **Taiwan** is listed in [`reference/delegations.csv`](reference/delegations.csv) as `not_represented`. It has had no UN seat since 1971, so it gives no general debate speech.

## Rank of speaker

| role_group | role | Example titles |
| --- | --- | --- |
| head_of_state_or_government | head_of_state | President, King, Amir, Chairman of the Presidency |
| | head_of_government | Prime Minister, Taoiseach, President of the Government |
| deputy_head | deputy_head | Vice President, Deputy Prime Minister, Crown Prince |
| foreign_minister | foreign_minister | Minister for Foreign Affairs, Minister for External Affairs |
| other_minister | junior_minister, other_minister | Minister of State, Minister of Public Health |
| diplomat | diplomat | Permanent Representative, Chair of the Delegation |
| not_a_state | un_official, regional_organisation | Secretary-General, President of the European Council |

"President" counts as head of state even where the president also heads the government, as in the United States. The raw title is always kept alongside.

## Repository

| Path | Contents |
| --- | --- |
| [`src/unga_speeches/sources/`](src/unga_speeches/sources/) | One module per upstream: the debate site, the verbatim records, the corpus, delegations' own sites |
| [`src/unga_speeches/extract/`](src/unga_speeches/extract/) | Pdf text extraction and the cleaned copies for analysis |
| [`src/unga_speeches/enrich/`](src/unga_speeches/enrich/) | Speaker rank, country names, and the filed-against-delivered check |
| [`src/unga_speeches/build/`](src/unga_speeches/build/) | Speech pages, reports, the combined dataset and release packaging |
| [`src/unga_speeches/analysis/`](src/unga_speeches/analysis/) | The session analysis: topics, word lists, readability, and the page in `site/` (`make site SESSION=81`) |
| `site/` | The built analysis page, published to GitHub Pages on every push to `main` |
| [`reference/`](reference/) | The hand-maintained inputs: delegations, and sources for texts the UN lacks |
| [`reports/`](reports/) | Generated completeness and source-agreement reports |
| [`docs/`](docs/) | [Methodology](docs/methodology.md), [data dictionary](docs/data-dictionary.md), [sources and terms](docs/sources.md), [development](docs/development.md) |
| `data/` | Downloads and outputs; not committed |

## Licence and citation

The code is under [Apache 2.0](LICENSE). The texts belong to their publishers; [sources](docs/sources.md) gives the terms and the corpus citation.
