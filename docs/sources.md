# Sources

| Years | Source | What it gives |
| --- | --- | --- |
| 1993–2024 (sessions 48–79) | UN verbatim records, e.g. [A/78/PV.5](https://documents.un.org/api/symbol/access?s=A/78/PV.5&l=en&t=pdf) | The official English text of every speech, and the language it was spoken in |
| 1946–1992 (sessions 1–47) | UN verbatim records, scanned, e.g. [A/PV.35](https://documents.un.org/api/symbol/access?s=A/PV.35&l=en&t=pdf) and [A/40/PV.5](https://documents.un.org/api/symbol/access?s=A/40/PV.5&l=en&t=pdf) | The record of each debate meeting, read from the OCR text layer the UN published with the scan: a link to the official record, the spoken language, and an independent check on the corpus's text |
| 2009–2026 (sessions 64–81), except 2019–2020 | [gadebate.un.org](https://gadebate.un.org), the UN's general debate site | Speaker and title, the statement pdf the delegation filed, and AI transcripts of the audio in the six UN languages |
| 1946–2025 (sessions 1–80) | [UN General Debate Corpus](https://doi.org/10.7910/DVN/0TJX8Y) | English text of every speech, and each speaker's name and post |
| Where the UN copy is missing or unreadable | The delegation's government site, listed in [`reference/manual_sources.csv`](../reference/manual_sources.csv) | The published text |

## Press and context, 2026 only

| Source | What it gives |
| --- | --- |
| UN press office summaries, on each speaker's debate page | A headline and summary of every speech, the link to the day's meetings coverage, and links to UN News stories in other languages |
| News reports listed in [`reference/news_81.csv`](../reference/news_81.csv) | UN News daily takeaways, CNN, ABC News, NBC News, CNBC, PBS, PolitiFact, MS NOW and Al Jazeera, cut to their paragraphs |
| [Wikipedia on the 2026 Secretary-General selection](https://en.wikipedia.org/wiki/2026_United_Nations_Secretary-General_selection) | The candidates and the Security Council straw polls, in [`reference/sg_candidates_81.csv`](../reference/sg_candidates_81.csv) |
| [Reuters Institute Digital News Report 2026](https://reutersinstitute.politics.ox.ac.uk/digital-news-report/2026) | The biggest online news brands in each of 48 markets, with weekly reach, in [`reference/dnr_brands_2026.csv`](../reference/dnr_brands_2026.csv); used to decide which outlets stand for a country |
| [Media Bias/Fact Check](https://mediabiasfactcheck.com) | Each outlet's political leaning and factual-reporting rating, linked in `reference/outlets.csv`; outlets it has not reviewed are marked "Not rated" |
| [`reference/context_81.csv`](../reference/context_81.csv) | The week's events, each with a short quote the build finds in a downloaded report |

**Politico and TLDR News are not in the sample.** Politico returned no coverage of the debate, and TLDR News publishes video only. Two UN News takeaways are read from GlobalSecurity.org copies, and Business Standard was dropped because only a caption could be read. The page shows only short excerpts, each linked to its report.

**The 2025 records (A/80/PV.*) are not yet issued**; the server returns no document for them, so session 80 keeps the corpus's transcript and the debate site's texts until they appear.

**The UN Digital Library** asks visitors to pass a bot check, so the meeting lists come from the records themselves.

**The debate site has almost no pages for 2019–2020** (sessions 74 and 75). Those years come from the records and the corpus.

## Terms and citation

- **UN documents and the debate site** are published by the United Nations. Check the [UN's terms of use](https://www.un.org/en/about-us/terms-of-use) before redistributing their content.
- **The UN General Debate Corpus** is released under CC0. Cite it as: Jankin, S., Baturo, A., & Dasandi, N. (2025). Words to unite nations: The complete United Nations General Debate Corpus, 1946–present. *Journal of Peace Research*, 62(4), 1339–1351. Harvard Dataverse asks for a name and email before the download.
- **News reports** keep their publishers' terms. Downloads stay in `data/raw/`, which is not committed, and the page shows only short linked excerpts.
- **Delegations' own sites** keep their own terms. Only the link, checksum and extracted text are stored.
- **This repository's code** is under the Apache 2.0 [licence](../LICENSE).
