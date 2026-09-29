# How the 2026 news sample was built

The page's press figures come from the reports listed in [`reference/news_81.csv`](../reference/news_81.csv). This log records how that list was found, so the sample can be checked and extended.

## Method

- **Find.** Search each outlet's own domain for its coverage of the general debate, 21–29 September 2026. Search runs region by region: Asia, Europe, the Middle East, Africa, the Americas and the Pacific.
- **Keep** a report when it is written coverage of the debate week in English.
- **Drop** video pages, full texts of speeches, reports from outside the debate week, and reports in other languages. A full speech text would count as press attention to its own speaker. The word lists and country names only match English.
- **Download** each kept report with the pipeline's own client (`make news SESSION=81`), which caches the page and records its checksum. Reports that yield no text are listed below.
- **Home region.** Each outlet carries the region of the country it is based in (`base_region`), so the page can compare what each region's press covered.

## Outlets the search tool cannot reach

The search tool is refused by these domains, so no report from them could be found. The pipeline's downloader is a different client and may still reach them if a url is added by hand.

| Region | Domains refused |
| --- | --- |
| Asia | channelnewsasia.com, straitstimes.com, thehindu.com, indianexpress.com, timesofindia.indiatimes.com, nhk.or.jp |
| Europe | bbc.com, bbc.co.uk, theguardian.com, reuters.com, lemonde.fr, rfi.fr, dw.com, politico.eu |
| Americas | apnews.com, nytimes.com, latimes.com, elpais.com, clarin.com |
| Africa | punchng.com |

Politico (US) returned no coverage of the debate. TLDR News publishes video only.

## Searches and what they found

| Region | Outlets searched | Kept | Dropped, and why |
| --- | --- | --- | --- |
| Asia | SCMP | Why Xi skipped the UN | Han Zheng "hegemonism" piece: 2023 |
| Asia | Dawn | 4 reports: Trump on Shehbaz, Shehbaz's speech, Pakistan's diplomacy, Guterres' address | |
| Asia | Japan Times, Kyodo, Korea Herald, Yonhap, Korea Times | Japan Times: Takaichi arrives, Carney and Lula; Korea Times: Netanyahu | Japan Times Nepal commentary: 13 September, before the debate |
| Asia | Xinhua, CGTN, China Daily, Global Times | CGTN on Han Zheng; Xinhua "China supports UN"; China Daily debate close; Global Times debate opens | Xinhua full text of Han Zheng's speech: a speech, not coverage; 2023 Xinhua pieces |
| Asia | Inquirer, Jakarta Post, Bangkok Post, VnExpress, Malay Mail, The Star | Inquirer; Jakarta Post ×3; Malay Mail ×3; The Star | |
| Middle East | Arab News, The National, Times of Israel, Tehran Times, Anadolu, Daily Sabah | Arab News; The National ×2; Times of Israel ×2; Tehran Times ×2; Anadolu live blog | Times of Israel liveblog one-liners: too short |
| Europe | France 24, Euronews | France 24 ×3 articles; Euronews article | France 24 replays and the Euronews video page: video |
| Europe | TASS, Moscow Times, Kyiv Independent, Ukrinform | TASS ×3; Kyiv Independent; Ukrinform | Kyiv Independent full speech: a speech, not coverage |
| Africa | Africanews, Daily Nation, The EastAfrican, News24, Premium Times | Africanews ×2; Daily Nation ×2; The EastAfrican; Premium Times ×3 | Premium Times full text: a speech; News24 and Daily Maverick: nothing found |
| Americas | Infobae, MercoPress, El Universal, Buenos Aires Times | Buenos Aires Times | Infobae ×5, MercoPress (Spanish edition), El Universal: Spanish |
| Americas | Nation News (Barbados), Jamaica Observer, Stabroek News | Nation News ×2 | Reparations pieces from July, August and 20 September: outside the week or not about the debate |
| Americas | NPR, Washington Post, Axios, Foreign Policy, PassBlue | NPR ×2; Foreign Policy ×3 | PassBlue: 12 and 17 September, before the debate |
| Oceania | RNZ, ABC Australia, Jamaica Gleaner | ABC Australia; RNZ; Jamaica Gleaner (Americas) | Older RNZ and ABC Pacific pieces: earlier sessions |

## Download results

The first list had 74 reports. 59 were kept after downloading.

| Result | Reports |
| --- | --- |
| **Refused the download** (403 or 406) | Inquirer; Arab News; Times of Israel ×2; France 24 ×3; Euronews; Africanews ×2; Daily Nation analysis; The EastAfrican |
| **No text in the page** (live pages drawn by script, with no story in their structured data) | The National ×2; Anadolu Agency live blog |
| **Recovered from structured data** | SCMP (168 → 1,074 words); MS NOW live blog (201 → 5,891 words) |
| **Short but complete** | TASS ×3 are two- and three-paragraph news briefs; PolitiFact's live fact-check page keeps 86 words |

The refused and empty reports are removed from `reference/news_81.csv` and listed here instead, so a later run can try them again by adding the url back.

## The sample that remains

| Outlet's home region | Reports | Words |
| --- | --- | --- |
| Americas | 19 | 33,724 |
| Asia | 22 | 15,897 |
| Africa | 4 | 4,742 |
| Europe | 5 | 1,450 |
| Oceania | 2 | 970 |
| UN News | 6 | 3,637 |

The Americas still supply over half the outside press words, mostly from CNN and MS NOW live blogs. Europe's five reports are from TASS, Kyiv Independent and Ukrinform, so its figures show the war as each side reports it rather than European coverage in general.

## Effect on the figures

Widening the sample from 12 mostly US reports to 52 reports across five regions changed these figures.

| Figure | 12 reports | 52 reports |
| --- | --- | --- |
| Delegations named at all | 51 of 191 | 98 of 191 |
| United States' share of press mentions | 28% | 26% |
| Five most-named delegations' share | 64% | 56% |
| Issues with no press at all | Sudan, Haiti, debt, migration, the next Secretary-General, Taiwan | Taiwan only |
| Iran and the Gulf war, press share against podium share | 13× | 10× |

The United States stays first. Outside the Americas' press it takes 13% of mentions. Issues that had no press now have a tenth to a third of their podium share.

## Extraction fixes found while building the sample

- **Page menus.** Premium Times and the Jakarta Post carry section menus in list items, and one Premium Times menu entry, "Panama Papers", counted as a mention of Panama. Blocks with no sentence punctuation and mostly capitalised words, and list items that are nothing but a link, are now skipped.
- **Structured data.** SCMP and MS NOW draw their stories by script. Their text is read from the page's schema.org data when the page paragraphs come to under 250 words. A first version used it whenever it was longer, which replaced CNN's live blogs with the full blog (18,553 words) and was narrowed.
