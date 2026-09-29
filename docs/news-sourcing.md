# How the 2026 news sample was built

The page's press figures come from the reports listed in [`reference/news_81.csv`](../reference/news_81.csv). This log records how that list was found, so the sample can be checked and extended.

## The maintained list

[`reference/outlets.csv`](../reference/outlets.csv) lists every outlet considered, whether or not it is in the sample. Each row gives the outlet's domain, home country and region, what happened when it was checked, how many reports it has in the sample, and the date it was checked.

| Status | Meaning |
| --- | --- |
| `in_sample` | Reports from it are in `news_81.csv` |
| `no_coverage_found` | Searched; no report from the debate week turned up |
| `search_blocked` | The search tool is refused by the domain |
| `download_refused` | A report was found but the site refused the download |
| `download_failed` | The download could not complete, such as a certificate that fails verification |
| `no_text` | The page draws its text by script and publishes none in its data |
| `outside_window` | The report found was published outside the debate week |
| `not_english` | Only reports in other languages were found |
| `video_only` | The outlet publishes video only |
| `excluded` | Left out by rule, such as a digest bundling unrelated stories |

**To add an outlet:**

- [ ] Search its domain for the debate week and add each report to `reference/news_81.csv` with its home region.
- [ ] Add or update its row in `reference/outlets.csv`, with the report count and the date checked.
- [ ] Run `make news SESSION=81`. The run skips refused downloads and reports published outside the debate week, and says so.
- [ ] Move any report it skipped out of `news_81.csv`, and set the outlet's status to match.
- [ ] Run `make test`. It fails if a sampled outlet is missing from the registry or its count is wrong.

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
| Oceania | postcourier.com.pg |

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

## Pacific round, 29 September

The Pacific was the thinnest region, with 2 reports. A second round searched 28 Pacific outlets, from Fiji, Samoa, Tonga, Palau, Papua New Guinea, the Solomon Islands, Vanuatu, the Cook Islands, Micronesia, the Marshall Islands, Guam, the Northern Mariana Islands, New Zealand and Australia.

| Result | Reports |
| --- | --- |
| **Kept** | Fiji Village; Matangi Tonga; Samoa Observer ×3; Island Times ×3; PINA ×2; Pacific Media Network; RNZ; Asia Pacific Report; SBS News ×2 |
| **Published outside the debate week** (found by the new date check) | Island Times on Palau and Taiwan (2018); Pacific Island Times (October 2025); Lowy Interpreter (March 2026) |
| **Refused the download** | Solomon Star; The National (PNG) ×2; Marianas Variety (rate limited, worth retrying) |
| **Excluded** | Islands Business PACNEWS digests, which bundle unrelated stories; an Asia Pacific Report piece that republishes an RNZ story already in the sample |

**Date check.** The run now reads each page's publication date from its metadata and skips reports published outside 18–30 September. Samoa Observer and Pacific Media Network give no machine-readable date, and their visible dates were read by hand: all fall in the debate week. The dates in `news_81.csv` are now the pages' own, which differ from the first listing by a day for most reports because of time zones.

The Pacific now has 17 reports from 10 outlets.

| Figure | 52 reports | 67 reports, with the Pacific round |
| --- | --- | --- |
| Pacific reports and words | 2 and 970 | 17 and 10,031 |
| Delegations named at all | 98 of 191 | 103 of 191 |
| United States' share of press mentions | 26% | 24% |
| Five most-named delegations' share | 56% | 52% |
| Climate change, press share against podium share | 0.7× | 1.4× |
| Pacific press's most-named delegation outside the Pacific | Iran | Indonesia, over West Papua |

## African round, 29 September

Africa had 4 reports, from 2 outlets. A third round searched 63 African outlets in 28 countries, from Nigeria, Kenya, South Africa, Ghana, Ethiopia and Egypt to Libya, Somalia, Sudan, Liberia and Namibia.

| Result | Reports |
| --- | --- |
| **Kept** | 68 new reports from 31 outlets, for 72 African reports from 34 outlets in all. The largest sets: Morocco World News ×5, MyJoyOnline ×6, The Star (Kenya) ×5, The Namibian ×4, Daily News Egypt ×3, Vanguard ×3 |
| **Published outside the debate week** | Daily Trust (2024); eNCA ×2 (2024, 2025); The Citizen, Tanzania (2024); Garowe Online (2020); Libya Observer ×2 (2021, 2025); The Namibian and Morocco World News previews (17 September) |
| **Dates read by hand** | ENA ×2 give no machine-readable date; their pages say September 2025, so both are left out |
| **Refused the download** | Sudan Tribune ×3; The Reporter (Ethiopia) ×2; Ahram Online |
| **No text in the page** | GhanaWeb ×2; APS (Algeria), which yields 14 words |
| **Download failed** | TAP (Tunisia), whose certificate fails verification; the check was not switched off |
| **Excluded** | Full speech texts from Channels TV, Graphic Online and MyJoyOnline; allAfrica, whose items republish UN News and outlets already sampled; Egypt's State Information Service, a government press office |

French-language outlets, which cover much of West and Central Africa, are out by the English-only rule. That leaves Senegal, Côte d'Ivoire, Cameroon and the Democratic Republic of the Congo without home press in the sample.

**New context.** The US withheld a visa from Sudan's General al-Burhan, and Sudan's foreign minister spoke instead. It is the second visa refusal of the week, after Mahmoud Abbas, and is now on the page's timeline.

### A change of method: region-balanced shares

Africa now supplies the most words in the sample (45,552, against 33,623 from the Americas). A share pooled across all reports would therefore rank African delegations high because African outlets were sampled most. The page's headline press share now averages each delegation's share across the regions with at least 10 reports (Africa, the Americas, Asia and the Pacific), so each region's press counts equally. The pooled share is still shown beside it.

| Figure | 67 reports, pooled | 135 reports, pooled | 135 reports, regions balanced |
| --- | --- | --- | --- |
| United States' share of press attention | 24% | 18% | 15% |
| Five most-named delegations' share | 52% | 42% | 39% |
| Delegations named at all | 103 of 191 | 124 of 191 | 124 of 191 |
| African press's share to African delegations | 93% (4 reports) | 67% (72 reports) | |
| Debt, press share against podium share | 0.3× | 1.7× | |

## One outlet per country, 29 September

Countries were unevenly represented: the United States by 9 outlets, Nigeria by 5, Kenya and China by 4 or 5. The press figures now use a panel with exactly one outlet per country, so each country's press counts once.

- **Rule.** For each country, the outlet with the most debate-week words in the sample stands for it; ties go to more reports, then name. Territories count under their state, so the SCMP stands for China. UN News and Wikipedia are not national press and are left out.
- **Kept, not counted.** The other outlets stay downloaded and listed in `reference/news_81.csv`, so the panel can change as the sample grows. The page's panel table names every outlet not counted.
- **Headline measure.** Most of a country's press is about itself, so a plain average rewards self-coverage: Malawi's only paper writes about Malawi. The headline share therefore drops each outlet's mentions of its own country, then averages the rest over the countries whose outlet has at least 10 such mentions (26 of 38). The number of countries whose press named a delegation is shown beside it.
- **Known quirk.** Equal weights let a small outlet move a figure. Jamaica's outlet is a wire story about island states, so Palau is the most-named outsider in the Americas' press.

| Figure | 135 reports, regions balanced | One outlet per country (38 countries) |
| --- | --- | --- |
| United States' share of press attention | 15% | 13% of attention from other countries; named by 20 of 38 countries' press |
| Next four | Iran, Israel, China, Palau | Israel, Palestine, Sudan, Iran |
| Five most-named delegations' share | 39% | 44% |
| Median outlet's share on its own country | | 55% |

## Big outlets, from the Digital News Report, 29 September

One outlet per country dropped big outlets whenever a smaller one had written more. The panel now carries every big outlet the sample has, using a published list of what "big" means.

- **The list.** The [Reuters Institute Digital News Report 2026](https://reutersinstitute.politics.ox.ac.uk/digital-news-report/2026) surveys news use in 48 markets and ranks the online news brands most used in the last week. `make brands` downloads each market's online top-brands chart (a Datawrapper table on each market page) into [`reference/dnr_brands_2026.csv`](../reference/dnr_brands_2026.csv): 784 brands with their weekly reach. A chart counts as the online one when at least half its brands say "online" or give a web address; Belgium, Canada and Switzerland have one per language community, merged.
- **The rule.** In a country the report covers, every sampled outlet whose brand is on its list stands for the country, weighted by weekly reach. Elsewhere, or where no sampled outlet is on the list, the outlet with the most debate-week words stands alone. Each country's press still counts once.
- **Matching.** Each outlet's brand in the report is recorded in the `dnr_brand` column of `reference/outlets.csv`. Most match by name; the rest were matched by hand, such as ABC Australia to "ABC News online" and Citizen Digital to "Citizen TV online". A test checks every recorded brand exists in the list.
- **Only English.** The counting works on English text, so big brands could be added only in markets with English-language press: the United States, Canada, Ireland, Australia, India, Malaysia, the Philippines, Kenya, Nigeria and South Africa. The UK's and Singapore's big brands all refused the search or the download.

**Searched in this round:** Fox News, CBS News, the Washington Post, USA Today; CTV, CBC, the Globe and Mail, Global News; Sky News, MailOnline, the Telegraph, ITV, GB News; RTÉ, the Irish Times, TheJournal.ie, the Irish Independent; news.com.au, Nine, 7News, Sky News Australia, the Sydney Morning Herald, the Australian; NDTV, Hindustan Times, India Today, Firstpost, Republic World, ThePrint; Mothership, RTHK, the Standard (Hong Kong); Malaysiakini, Free Malaysia Today, Astro Awani; GMA, ABS-CBN, Rappler, Philstar; Tuko, Kenyans.co.ke; Legit.ng, Pulse, Arise, Sahara Reporters, Daily Post, TVC; News24, the Citizen, the South African, TimesLive. Each outlet's result is in `reference/outlets.csv`.

**Countries now counted through their big brands:**

| Country | Outlets counted, by weight | Sampled but not on the list |
| --- | --- | --- |
| Australia | ABC Australia 75%; SBS News 25% | – |
| Canada | CBC News 43%; CTV News 37%; The Globe and Mail 20% | – |
| India | Republic World 62%; ThePrint 38% | – |
| Ireland | RTÉ News 43%; TheJournal.ie 34%; The Irish Times 23% | – |
| Kenya | Citizen Digital 29%; Kenyans.co.ke 21%; Daily Nation 21%; The Standard (Kenya) 17%; The Star (Kenya) 11% | – |
| Malaysia | The Star 46%; Free Malaysia Today 35%; Malay Mail 19% | – |
| Morocco | Hespress English 100% | Morocco World News |
| Nigeria | Legit.ng 21%; Vanguard 18%; Daily Trust 16%; Arise News 16%; Channels Television 14%; Sahara Reporters 14% | Premium Times, The Guardian (Nigeria) |
| Philippines | GMA News 53%; Rappler 26%; Philstar 22% | – |
| South Africa | SABC News 51%; The Citizen (South Africa) 19%; Daily Maverick 18%; IOL 13% | – |
| United States | Fox News 27%; CNN 22%; ABC News 14%; CBS News 12%; NPR 12%; NBC News 12% | MS NOW, Foreign Policy, PBS News, CNBC, PolitiFact |

**Known quirk.** In Morocco the only listed brand in the sample is Hespress's English edition, which is weighted as Hespress. It displaces Morocco World News, which is not on the list, and Morocco's own-country share falls to 0.

| Figure | One outlet per country | Big brands, by reach |
| --- | --- | --- |
| Countries, and outlets counted | 38 and 38 | 42 and 69 |
| United States, attention from other countries | 13%, named by 20 countries' press | 17%, named by 24 |
| Next four | Israel, Palestine, Sudan, Iran | Israel, Iran, Palestine, Russia |
| Five most-named delegations' share | 44% | 50% |
| Median country's share on itself | 55% | 50% |

## Political leaning, 29 September

Each sampled outlet's leaning is in `reference/outlets.csv`, kept by [`sources/leaning.py`](../src/unga_speeches/sources/leaning.py) (`python -m unga_speeches.sources.leaning`).

- **Source.** [Media Bias/Fact Check](https://mediabiasfactcheck.com) (MBFC), the only rating that covers many outlets outside the United States. Its scale is drawn on US politics, and its ratings are contested, so every label links to the rating page it comes from.
- **Labels.** Left, Left-centre, Centre, Right-centre, Right, or Not rated. MBFC's "Least Biased" is Centre; "Extreme" ratings fold into Left and Right. The `mbfc_bias` and `factual_reporting` columns keep MBFC's own words.
- **State media** are flagged in their own column (`state_media`), from the report kind and the registry notes. MBFC rates Xinhua, China Daily and Global Times Left and TASS Right-centre; those are its judgements, and the page leaves state media out of comparisons by leaning.
- **Finding the page.** The code tries rating pages named after the outlet and its site, and accepts one only if it rates the outlet's own site: by its "Source:" link, or on older pages by the outside site it links to most. Pages found by searching MBFC are recorded by hand in the `mbfc_url` column (MS NOW under MSNBC, SCMP, CGTN, ABC Australia, SBS, the Daily Nation, Vanguard, The Star Malaysia, Malay Mail, Philstar, GMA, TASS, IOL). A `-` means the outlet was looked for and has no rating page.
- **Coverage.** 53 of 92 sampled national outlets are rated. MBFC has reviewed few Pacific and African outlets, so most of those are Not rated.
