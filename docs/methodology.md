# Methodology

How the speeches are found, read, split and combined, and what each text in the dataset is.

## A deterministic pipeline

**No AI model and no web search is used to find, read or split the speeches.** Every step is a fixed rule in Python applied to downloaded files, so the same inputs always give the same outputs. Every download is cached with its url, retrieval time and SHA-256 checksum in `data/raw/manifest.jsonl`.

**Machine processing enters only through the sources, and every row says so.** The UN debate site's transcripts are AI transcriptions of the meeting audio. The corpus made its 2024 English with GPT-4o and its 2025 English with Whisper. The `english_source` and `original_source` columns name the source of each text.

## The steps

1. **Find the speeches.** [`sources/gadebate.py`](../src/unga_speeches/sources/gadebate.py) reads the UN debate site's sitemap, which lists every speaker page from 2009. A page the site redirects on every retry is not yet published. [`sources/verbatim.py`](../src/unga_speeches/sources/verbatim.py) requests the UN's meeting records by symbol (`A/78/PV.1`, `A/78/PV.2`, …) until the debate's meetings end.
2. **Read who spoke.** On the debate site, the speaker's name, honorific, title and date are fixed fields on each page. In the meeting records they come from the "Address by …" heading, the speaker label (`Mr. Lavrov (Russian Federation) (spoke in Russian):`) and the chair's introduction.
3. **Split the meeting records into speeches.**
   - A turn starts at a bold speaker label. The chair's turns are dropped.
   - Turns under a "General debate" agenda heading are kept. Summits and other agenda items are skipped.
   - A delegation's debate speech is its longest turn. Shorter turns, such as introducing a video or a point of order, become `other_intervention`.
   - A turn that exercises the right of reply is kept apart, in `rights_of_reply.parquet`.
4. **Take the text from each pdf.** [`extract/pdf.py`](../src/unga_speeches/extract/pdf.py) reads the text layer and changes nothing except the known faults below.
5. **Name the country.** [`enrich/countries.py`](../src/unga_speeches/enrich/countries.py) matches the longest country name in the heading, label or introduction. The list is [`reference/delegations.csv`](../reference/delegations.csv) plus formal and former names, such as Zaire, Swaziland and "the French Republic".
6. **Sort the title into a rank.** [`enrich/roles.py`](../src/unga_speeches/enrich/roles.py) applies an ordered list of patterns. For example, "Deputy Prime Minister" is checked before "Prime Minister".
7. **Compare the filed text with what was said.** [`enrich/delivery.py`](../src/unga_speeches/enrich/delivery.py) aligns the statement with the transcript in the spoken language. Arabic is compared letter by letter, and Chinese by character.
8. **Combine the sources.** [`build/dataset.py`](../src/unga_speeches/build/dataset.py) builds one row per delegation per session. Each field comes from the most authoritative source that has it.

| Field | First choice | Then | Then |
| --- | --- | --- | --- |
| Speaker and title | UN debate site | Corpus speaker list | Record heading |
| Spoken language | The record's "(spoke in …)" note | The language of the delegation's statement | |
| English text | UN verbatim record | Corpus | The site's statement, then its interpretation transcript |
| Original text | The site's text in the spoken language | The English text, when the speech was in English | |

## Beyond the speeches (2026)

- **Who names whom.** [`analysis/mentions.py`](../src/unga_speeches/analysis/mentions.py) finds every state a speech names, by its name, a formal or former name, or a common adjective ("Russian", "Israeli"). The longest name wins, so "South Sudan" is not also counted as "Sudan". Places such as the Gulf of Guinea are skipped, and so is a bare "Congo", which speakers use for both Congos.
- **The press.** [`sources/news.py`](../src/unga_speeches/sources/news.py) downloads each listed report and keeps the paragraphs of the element holding the most story text. When those paragraphs come to under 250 words, it reads the story from the page's schema.org data instead, which sites that draw text by script still publish. A site that refuses the download is logged and left out, and so is a report whose page says it was published outside the debate week. The sample and every search behind it are logged in [news-sourcing.md](news-sourcing.md). [`analysis/press.py`](../src/unga_speeches/analysis/press.py) counts the paragraphs that name each delegation, compares issue rates in press and speeches per 1,000 words, measures how much of each region's press goes to its own region, and counts each country's press once. Where the Reuters Institute Digital News Report lists a country's biggest online news brands, every sampled outlet on that list stands for the country, weighted by weekly reach; elsewhere the outlet with the most debate-week words stands alone. Territories count under their state. Each outlet's mentions become shares before they are blended, so a long live blog cannot outweigh a bigger outlet. A delegation's headline share is its share of each country's outlet's mentions of other countries, averaged over the countries whose outlet has at least 10 such mentions, and checks what each UN summary kept from its speech.
- **The naming network.** [`analysis/network.py`](../src/unga_speeches/analysis/network.py) treats each speech naming another state as a link. It asks whether links stay within a region, a bloc or a theory lean more often than chance. Chance is the share left after reconnecting the links at random 1,000 times, with every state keeping how many it names and is named by. The layout is a force layout with a fixed seed, and the few states beyond the 3rd and 97th percentiles are drawn on the edge.
- **Taiwan.** The states that recognise Taiwan are listed in [`reference/taiwan_allies.csv`](../reference/taiwan_allies.csv), each with its source. A mention of the Taiwan Strait alone is geography and does not count as naming Taiwan.
- **Year by year.** [`analysis/years.py`](../src/unga_speeches/analysis/years.py) applies the same issue lists, name matching and theory vocabulary to every debate since 1946. The issue lists were written for 2026, so older years can miss issues phrased differently. The share of leaders is left blank where fewer than half of the speakers' ranks are known. States that no longer exist count under the region of their territory. The result is cached against a hash of the dataset.
- **UN headlines.** A headline's tone is set by its first reporting verb: alarm, appeal or showcase. Headlines with no reporting verb are counted apart.
- **The Secretary-General race.** [`analysis/race.py`](../src/unga_speeches/analysis/race.py) searches the English and original texts for each candidate's surname, so a speech with no English text is still covered.
- **Leaning.** [`sources/leaning.py`](../src/unga_speeches/sources/leaning.py) reads each outlet's Media Bias/Fact Check rating from the structured data on its rating page, and accepts a page only if it rates the outlet's own site. The ratings map to Left, Left-centre, Centre, Right-centre and Right; state media are flagged separately and left out of comparisons by leaning, since a rating of a state outlet is not a party leaning.
- **Claims.** The Assembly President's closing numbers are counted again from the texts, with the same word lists.

## The scanned records, 1946–1992

[`sources/scanned.py`](../src/unga_speeches/sources/scanned.py) reads the UN's scanned records of sessions 1 to 47. The text is the OCR layer the UN published with each scan, read as it stands; nothing is re-recognised.

- **Finding the meetings.** Until 1976 meetings are numbered across sessions (A/PV.<n>), so each session's opening is found by binary search on the date each record gives, and its debate meetings by walking forward: every meeting from the first to the last that lists "General debate" as an agenda item. From 1976 (A/31/PV.<n>) the walk starts at meeting 1.
- **Reading order.** Pages are read top to bottom when their text runs full width (typescript, 1980s), and left column then right when they are set in two columns. French columns of the bilingual records of the 1940s and 1950s are dropped. Each meeting is read both by OCR line and by OCR block, and the reading that finds more speech is kept.
- **Speakers.** A turn starts at a label such as "Mr. ARCE (Argentina) (translated from Spanish):". Surnames are printed in capitals, which lets a label survive a mangled title ("Hr.", "Nr."). Heads of state labelled by office alone take their country from the address heading just before the turn. Former states resolve to the corpus's codes: Czechoslovakia CSK, the German Democratic Republic DDR, Democratic Yemen YMD, the USSR RUS.
- **Which turns count.** Only turns under the general debate's agenda item, whose number is learnt once per session, or under a head of state's address. Tributes and commemorations are left out, and a delegation's speech is its longest such turn of at least 600 words.
- **Summary records.** The plenary records of the third and fourth sessions (1948 and 1949) are summaries in the third person ("Mr. BLANCO (Venezuela) asked to be excused"), not verbatim, so they yield no speech text; those years keep the corpus's text alone.
- **Special sessions** that meet inside a regular session, such as the emergency sessions of 1956, 1958 and 1967, are recognised by their capitalised heading and stepped over.
- **OCR quality.** Each speech's `ocr_quality` is the share of its words found in the vocabulary of the born-digital records from 1993 on.
- **Checked against the corpus.** A scanned speech joins the dataset only if at least half its five-word runs match the corpus's text for the same delegation, or the corpus has no speech for it. The corpus's cleaned text stays the English text; the scan adds the official record's link, the spoken language, and `records_vs_ungdc`.

### Coverage of the scanned records

A speech counts as linked when its scanned record was found and matches the corpus's text for the same delegation. Agreement is the median share of five-word runs the two texts share. The records of 1948 and 1949 are summaries, and the records of 1988 to 1991 set their OCR text one word to a line, which breaks many speaker labels. Running the step twice over the same downloads gives byte-identical files.

| Year | Session | Speeches | Linked to the record | Share | Agreement | Only in the records |
| --- | --- | --- | --- | --- | --- | --- |
| 1946 | 1 | 39.0 | 29.0 | 74% | 0.91 |  |
| 1947 | 2 | 39.0 | 11.0 | 28% | 0.87 |  |
| 1948 | 3 | 39.0 | 0.0 | 0% |  |  |
| 1949 | 4 | 35.0 | 0.0 | 0% |  |  |
| 1950 | 5 | 46.0 | 36.0 | 78% | 0.87 | 2.0 |
| 1951 | 6 | 51.0 | 31.0 | 61% | 0.68 |  |
| 1952 | 7 | 43.0 | 7.0 | 16% | 0.64 |  |
| 1953 | 8 | 44.0 | 31.0 | 70% | 0.83 |  |
| 1954 | 9 | 42.0 | 26.0 | 62% | 0.89 |  |
| 1955 | 10 | 45.0 | 15.0 | 33% | 0.70 |  |
| 1956 | 11 | 67.0 | 19.0 | 28% | 0.86 | 1.0 |
| 1957 | 12 | 71.0 | 42.0 | 59% | 0.77 |  |
| 1958 | 13 | 72.0 | 40.0 | 56% | 0.66 |  |
| 1959 | 14 | 79.0 | 25.0 | 32% | 0.65 |  |
| 1960 | 15 | 80.0 | 29.0 | 36% | 0.66 | 1.0 |
| 1961 | 16 | 83.0 | 41.0 | 49% | 0.65 | 2.0 |
| 1962 | 17 | 94.0 | 32.0 | 34% | 0.90 | 1.0 |
| 1963 | 18 | 99.0 | 89.0 | 90% | 0.90 | 2.0 |
| 1964 | 19 | 100.0 | 84.0 | 84% | 0.79 | 5.0 |
| 1965 | 20 | 101.0 | 83.0 | 82% | 0.77 |  |
| 1966 | 21 | 110.0 | 83.0 | 75% | 0.88 | 2.0 |
| 1967 | 22 | 112.0 | 93.0 | 83% | 0.88 | 2.0 |
| 1968 | 23 | 113.0 | 100.0 | 88% | 0.89 | 1.0 |
| 1969 | 24 | 117.0 | 98.0 | 84% | 0.78 | 1.0 |
| 1970 | 25 | 74.0 | 62.0 | 84% | 0.86 | 4.0 |
| 1971 | 26 | 118.0 | 79.0 | 67% | 0.74 | 2.0 |
| 1972 | 27 | 125.0 | 97.0 | 78% | 0.89 |  |
| 1973 | 28 | 122.0 | 69.0 | 57% | 0.85 | 2.0 |
| 1974 | 29 | 130.0 | 93.0 | 72% | 0.85 | 1.0 |
| 1975 | 30 | 126.0 | 62.0 | 49% | 0.77 |  |
| 1976 | 31 | 134.0 | 105.0 | 78% | 0.80 |  |
| 1977 | 32 | 142.0 | 99.0 | 70% | 0.84 |  |
| 1978 | 33 | 141.0 | 95.0 | 67% | 0.84 |  |
| 1979 | 34 | 145.0 | 120.0 | 83% | 0.80 | 1.0 |
| 1980 | 35 | 149.0 | 96.0 | 64% | 0.84 |  |
| 1981 | 36 | 147.0 | 100.0 | 68% | 0.82 | 1.0 |
| 1982 | 37 | 147.0 | 83.0 | 56% | 0.72 |  |
| 1983 | 38 | 150.0 | 105.0 | 70% | 0.82 |  |
| 1984 | 39 | 150.0 | 96.0 | 64% | 0.76 | 1.0 |
| 1985 | 40 | 138.0 | 111.0 | 80% | 0.87 | 1.0 |
| 1986 | 41 | 149.0 | 107.0 | 72% | 0.79 |  |
| 1987 | 42 | 153.0 | 109.0 | 71% | 0.87 |  |
| 1988 | 43 | 154.0 | 64.0 | 42% | 0.80 |  |
| 1989 | 44 | 155.0 | 45.0 | 29% | 0.67 |  |
| 1990 | 45 | 157.0 | 23.0 | 15% | 0.71 | 1.0 |
| 1991 | 46 | 162.0 | 31.0 | 19% | 0.78 |  |
| 1992 | 47 | 167.0 | 166.0 | 99% | 0.98 |  |

## What each text is

- **UN verbatim record.** The official record of the meeting. A non-English speech appears in the UN's English translation, and the record notes the spoken language, e.g. "(spoke in Japanese; English interpretation provided by the delegation)".
- **Statement pdf.** The text the delegation filed with the UN. It is often the prepared text, so it can differ from what was said.
- **AI transcript.** What was said in the room, machine-transcribed by the UN. The English transcript of a non-English speech is the interpreters' live English.
- **National source.** The text on the delegation's government site, listed by hand in [`reference/manual_sources.csv`](../reference/manual_sources.csv). The checksum records the version that was read.

## Known faults, and how each is handled

- **Arabic ligatures.** Some pdfs store لا and ﷲ as zero-width letters in reverse order. The pipeline restores them from the glyph positions. Punctuation at an Arabic line end can still sit on the wrong side, so each Arabic text carries a note to check against the pdf.
- **Broken text layers are refused, not kept.** A pdf yields no text in any of these cases, and the speech page names the gap:
  - it is a scan, or page images with little text beside them
  - its font maps glyphs to symbols (Singapore 2026)
  - its Indic vowel signs are scrambled (Bangladesh 2026)
  - its non-Latin words carry ASCII junk (Syria 2026)
- **OCR is optional.** With [tesseract](https://github.com/tesseract-ocr/tesseract) installed, the pipeline OCRs refused pdfs instead and labels the text as OCR.
- **Missing word spaces.** Some 1990s records place each word separately with no space characters. Spaces are rebuilt from the gaps between glyphs.
- **An unreliable site.** The UN debate site sometimes redirects a published page, times out or refuses a transcript link. Pages are retried before being called pending, and one failed speech never stops a session.

## Limits

- **The records match 98.9% of the corpus's speeches for 1993–2024.** The largest gap is 2001, whose meeting record A/56/PV.45 is missing from the UN's document system. Its speeches still take their English from the corpus. [`reports/sources.md`](../reports/sources.md) gives the figures per session.
- **Before 1993 the corpus is the only source.** The UN's records for those years are scans, and the corpus was built from the same records.
- **2026 has no verbatim records yet.** The UN publishes them months after the debate. Until then the spoken language comes from the statement files, and it is unknown when a delegation filed only English.
- **Interpreters read from the text a delegation supplies.** So when only an English text exists, neither the pdf nor the audio shows whether the leader spoke English. Only the verbatim record settles it.
- **Speaker posts are sparse before 1994** in the corpus, so `role` is often `unclassified` for early years.
- **The corpus's speaker list does not pair with every text.** After mapping its code typos (`DKN` for Denmark, `ZFA` for South Africa), 22 speaker rows and 46 texts still have no partner. The rest are errors in the list itself, such as a `CHE` row named "Sweden", so they are left unpaired rather than guessed.
