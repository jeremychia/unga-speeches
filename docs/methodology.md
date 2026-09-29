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
- **The press.** [`sources/news.py`](../src/unga_speeches/sources/news.py) downloads each listed report and keeps the paragraphs of the element holding the most story text. When those paragraphs come to under 250 words, it reads the story from the page's schema.org data instead, which sites that draw text by script still publish. A site that refuses the download is logged and left out. The sample and every search behind it are logged in [news-sourcing.md](news-sourcing.md). [`analysis/press.py`](../src/unga_speeches/analysis/press.py) counts the paragraphs that name each delegation, compares issue rates in press and speeches per 1,000 words, measures how much of each region's press goes to its own region, and checks what each UN summary kept from its speech.
- **UN headlines.** A headline's tone is set by its first reporting verb: alarm, appeal or showcase. Headlines with no reporting verb are counted apart.
- **The Secretary-General race.** [`analysis/race.py`](../src/unga_speeches/analysis/race.py) searches the English and original texts for each candidate's surname, so a speech with no English text is still covered.
- **Claims.** The Assembly President's closing numbers are counted again from the texts, with the same word lists.

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
