# Data dictionary

## For text analysis

- **Use `english_text_clean` and `original_text_clean`.** The verbatim columns keep the source's line breaks and page furniture, for quoting and checking.
- **Filter on `english_source`** when the kind of text matters. `un_verbatim_record` and `ungdc_verbatim_record` are official translations; the others are filed statements or transcripts.
- **A cleaned statement can open with a line of site navigation**, because some delegations filed a printout of their ministry's web page.

## `speeches.parquet`

One row per delegation per session, 1946 onwards. `speeches.csv` holds the same rows without the text columns.

| Column | Meaning |
| --- | --- |
| `session`, `year` | The General Assembly session and the year its debate opened; session 1 is 1946 |
| `iso3` | ISO 3166-1 alpha-3 code; `EU` for the European Union, `UN-SG` and `UN-PGA` for UN officials, former states under the corpus's codes (`CSK`, `DDR`, `YMD`, `YUG`) |
| `delegation` | The delegation's name |
| `speaker_name`, `speaker_title` | Who spoke, and the office they spoke in, as the source gives them |
| `speaker_source` | `gadebate`, `ungdc` or `un_verbatim_record` |
| `role`, `role_group` | The rank of office, from [`enrich/roles.py`](../src/unga_speeches/enrich/roles.py); see the table in the README |
| `spoken_language` | ISO 639-1 code of the language the speech was delivered in, where known |
| `spoken_language_source` | `un_verbatim_record` (the record's note) or `gadebate_statement_language` (the language of the delegation's statement) |
| `interpretation_note` | The record's note on who provided the English, e.g. "English interpretation provided by the delegation" |
| `english_text` | The verbatim English text |
| `english_source` | See the table below |
| `english_url` | Where the English text came from |
| `original_language`, `original_text` | The text in the spoken language, verbatim |
| `original_source`, `original_url` | Where the original text came from |
| `english_text_clean`, `original_text_clean` | Copies for text analysis: lines rejoined into paragraphs, and page numbers, repeated headers and the chair's words around a transcript removed |
| `gadebate_page` | The speaker's page on gadebate.un.org |
| `verbatim_meeting` | The UN record the speech is in, e.g. `A/78/PV.5` |
| `in_ungdc` | Whether the corpus holds the speech |
| `records_vs_ungdc` | Share of five-word runs the UN record and the corpus share for this speech; 1 means identical |
| `delivered_share` | Share of the filed statement that the transcript shows was said, in the spoken language |

### `english_source` and `original_source`

| Value | The text is |
| --- | --- |
| `un_verbatim_record` | The UN's official record, parsed by this pipeline |
| `ungdc_verbatim_record` | The corpus's copy of the UN record (up to 2023) |
| `ungdc_machine_translation` | The corpus's GPT-4o translation of the delegation's statement (2024) |
| `ungdc_whisper_transcript` | The corpus's Whisper transcript of the English interpretation (2025) |
| `gadebate_statement` | The statement pdf the delegation filed |
| `gadebate_national_source` | The text on the delegation's government site |
| `gadebate_transcript` | The UN's AI transcript of the audio in that language |

## `rights_of_reply.parquet`

Replies to other speeches and other short turns from the verbatim records, one row per turn. It has the verbatim record columns below, and `kind` is `right_of_reply` or `other_intervention`.

## Verbatim record files: `verbatim_<session>.jsonl`

One row per turn in the debate meetings: `meeting`, `meeting_url`, `order_in_meeting`, `page`, `iso3`, `label` (the speaker label), `heading_speaker`, `heading_title`, `spoken_language`, `spoken_language_note`, `interpretation_note`, `kind` and `text`.

## Debate site files

| File | Contents |
| --- | --- |
| `speeches_<session>.csv` | One row per speaker page: speaker, title, role, date, languages, `delivered_share`, `unscripted_share`, gaps |
| `texts_<session>.jsonl` | One row per text version: kind, language, source url, retrieval time, checksum, extraction method, warnings, verbatim text |
| `speeches/<session>/<delegation>/README.md` | A readable page per speech with its sources table |
| `speeches/<session>/<delegation>/*.txt` | The exact texts, one file per source |
