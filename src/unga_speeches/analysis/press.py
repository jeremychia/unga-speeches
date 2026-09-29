"""What was said about the debate: the UN press office's headline for each speaker, outside press coverage, and the UN's own summary checked against the texts."""

import csv
import json
import re
import statistics
from collections import Counter

import pandas as pd

from unga_speeches.analysis import lexicons, mentions, words
from unga_speeches.analysis.corpus import Speech
from unga_speeches.config import OUTPUT_DIR, REFERENCE_DIR

# the lead verb of a headline says how the UN press office framed the speech
TONES = [
    ("Alarm", r"warns?|raises? alarm|sounds? alarm|blasts?|slams?|denounces?|condemns?|rejects?|accuses?|calls? out|renounces?|confronts?"),
    ("Appeal", r"urges?|urging|calls? for|demands?|stresses|pushes|advocates?|proposes?"),
    (
        "Showcase",
        r"hails?|touts?|highlights?|spotlights?|champions?|pledges?|pledging|announces?|welcomes?|reaffirms?|defends?|prioritizes?|lays out|spells out"
        r"|credits?|backs?|casts itself|speaks up|joins?|stands firm|underlines?|cites?|anchors?|showing|rising|reaches|is back|poised|affirms",
    ),
]
_TONES = [(name, re.compile(rf"\b(?:{p})\b", re.I)) for name, p in TONES]
NO_VERB = "Statement, no verb"
SNIPPET_WORDS = 40
# a country's outlet votes on attention from others only with at least this many mentions of other countries' delegations
FOREIGN_MIN_MENTIONS = 10
# territories whose press counts under the state they belong to
SOVEREIGN = {"Hong Kong": "China", "Guam": "United States", "Northern Mariana Islands": "United States"}
SNIPPETS = 6
# a surname shorter than this is too often a first name or a word to count on its own
SURNAME_CHARS = 4
UN_OUTLETS = ("UN News",)
REFERENCE_OUTLETS = ("Wikipedia",)
WOMEN_AND_GIRLS = re.compile(r"\bwomen\b|\bgirls\b|\bgender\b", re.I)
HUMAN_RIGHTS = re.compile(r"human rights", re.I)
CLIMATE_CHANGE = re.compile(r"climate change", re.I)
# spellings of language names on the debate pages that are typos of one language
LANGUAGE_SPELLINGS = {"Kishahili": "Kiswahili", "Kiswhahili": "Kiswahili"}
TREND_SESSION_AI = 77  # "just four years ago" in the Assembly President's closing summary


def tone(headline: str) -> tuple[str, str | None]:
    """The tone family of a headline's lead verb, and the verb, by whichever family's verb comes first."""
    hits = [(m.start(), name, m.group()) for name, p in _TONES if (m := p.search(headline))]
    if not hits:
        return NO_VERB, None
    _, name, verb = min(hits)
    return name, verb.lower()


def _cut(text: str, start: int, end: int) -> dict:
    """About SNIPPET_WORDS words of the text around a match, widened to whole words, as an exact substring."""
    tokens = [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]
    first = next(i for i, (_, e) in enumerate(tokens) if e > start)
    last = next((i for i, (s, _) in enumerate(tokens) if s >= end), len(tokens)) - 1
    lo = max(0, first - SNIPPET_WORDS // 2)
    hi = min(len(tokens) - 1, max(last, lo + SNIPPET_WORDS - 1))
    return {"text": text[tokens[lo][0] : tokens[hi][1]], "cut_start": lo > 0, "cut_end": hi < len(tokens) - 1}


def load_news(session: int) -> list[dict]:
    path = OUTPUT_DIR / f"news_{session}.jsonl"
    return [json.loads(line) for line in path.open(encoding="utf-8")] if path.exists() else []


def load_coverage(session: int) -> dict[str, dict]:
    path = OUTPUT_DIR / f"coverage_{session}.jsonl"
    return {(r := json.loads(line))["slug"]: r for line in path.open(encoding="utf-8")} if path.exists() else {}


def _outside(news: list[dict]) -> list[dict]:
    return [n for n in news if not n["outlet"].startswith(UN_OUTLETS) and n["outlet"] not in REFERENCE_OUTLETS]


def _registry() -> list[dict]:
    with (REFERENCE_DIR / "outlets.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _reach() -> dict[tuple[str, str], float]:
    """Weekly online reach of each market's big brands, from the Digital News Report list."""
    path = REFERENCE_DIR / "dnr_brands_2026.csv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return {(r["country"], r["brand"]): float(r["reach"]) for r in csv.DictReader(f)}


def panel(
    news: list[dict], registry: list[dict] | None = None, reach: dict[tuple[str, str], float] | None = None
) -> tuple[list[dict], list[dict]]:
    """The outlets that stand for each country's press, so each country counts once however many of its outlets were sampled.

    In a country the Digital News Report covers, every sampled outlet on its list of big brands stands for it, weighted by weekly
    reach. Elsewhere, or where none of the sampled outlets is on the list, the outlet with the most debate-week words stands alone.
    Returns the members' reports, each tagged with its country and weight, and one row per country."""
    registry = _registry() if registry is None else registry
    reach = _reach() if reach is None else reach
    info = {r["outlet"]: r for r in registry}
    markets = {c for c, _ in reach}
    by_outlet: dict[str, list[dict]] = {}
    for a in _outside(news):
        by_outlet.setdefault(a["outlet"], []).append(a)
    by_country: dict[str, list[str]] = {}
    for outlet in by_outlet:
        c = info[outlet]["country"]
        by_country.setdefault(SOVEREIGN.get(c, c), []).append(outlet)
    articles, table = [], []
    for country, outlets in sorted(by_country.items()):
        ranked = sorted(outlets, key=lambda o: (-sum(a["words"] for a in by_outlet[o]), -len(by_outlet[o]), o))
        big = {
            o: reach[(info[o]["country"], info[o]["dnr_brand"])]
            for o in ranked
            if country in markets and (info[o]["country"], info[o].get("dnr_brand", "")) in reach
        }
        members = big or {ranked[0]: 1.0}
        total = sum(members.values())
        for o, w in members.items():
            articles += [{**a, "country": country, "weight": w / total} for a in by_outlet[o]]
        table.append(
            {
                "country": country,
                "region": by_outlet[ranked[0]][0].get("base_region", ""),
                "rule": "big brands" if big else "most words",
                "members": [
                    {
                        "outlet": o,
                        "weight": round(w / total, 3),
                        "reach": w if big else None,
                        "reports": len(by_outlet[o]),
                        "words": sum(a["words"] for a in by_outlet[o]),
                        "leaning": info[o].get("leaning") or "Not rated",
                        "state_media": info[o].get("state_media") == "yes",
                        "mbfc_url": info[o].get("mbfc_url", ""),
                    }
                    for o, w in sorted(members.items(), key=lambda x: -x[1])
                ],
                "outlet": ", ".join(members),
                "reports": sum(len(by_outlet[o]) for o in members),
                "words": sum(a["words"] for o in members for a in by_outlet[o]),
                "not_used": [o for o in ranked if o not in members],
            }
        )
    return articles, table


def attention(speeches: list[Speech], news: list[dict]) -> dict:
    """Paragraphs of the panel's outlets that name each delegation, by country or, within an article that names the country, its speaker.

    Each outlet's mentions are turned into shares first, then blended by the outlet's weight within its country, so a country's view
    does not depend on how much any one outlet wrote. A delegation's share of press attention averages those views, one per country."""
    articles, table = panel(news)
    total_words = sum(s.words for s in speeches)
    weight = {(a["country"], a["outlet"]): a["weight"] for a in articles}
    rows = []
    for s in speeches:
        if not s.iso3:
            continue
        country = mentions._Names(s.iso3)
        surname = s.speaker.split()[-1] if s.speaker else ""
        person = re.compile(rf"(?<![\w-]){re.escape(surname)}(?![\w-])") if len(surname) >= SURNAME_CHARS else None
        hits = []
        for a in articles:
            names_country = any(country.search(p) for p in a["paragraphs"])
            for p in a["paragraphs"]:
                m = country.search(p) or (person.search(p) if person and names_country else None)
                if m:
                    hits.append(
                        {
                            "outlet": a["outlet"],
                            "country": a["country"],
                            "base_region": a.get("base_region", ""),
                            "date": a["date"],
                            "title": a["title"],
                            "url": a["url"],
                            **_cut(p, m.start(), m.end()),
                        }
                    )
        if hits:
            rows.append(
                {
                    "slug": s.slug,
                    "region": s.region,
                    "paragraphs": len(hits),
                    "articles": len({h["url"] for h in hits}),
                    "share_of_words": round(s.words / total_words, 4),
                    "outlets": len({h["outlet"] for h in hits}),
                    "by_outlet": Counter((h["country"], h["outlet"]) for h in hits),
                    "by_country": dict(Counter(h["country"] for h in hits)),
                    "snippets": _spread(hits),
                }
            )
    outlet_totals = Counter()
    for r in rows:
        outlet_totals.update(r["by_outlet"])
    # each country's own delegation, found by matching the country's name
    own_of = {t["country"]: next((r["slug"] for r in rows if _same_country(r["slug"], t["country"], speeches)), None) for t in table}
    own_n = {k: next((r["by_outlet"].get(k, 0) for r in rows if r["slug"] == own_of[k[0]]), 0) for k in outlet_totals}

    def view(r: dict, country: str, foreign: bool) -> float:
        """The delegation's share of one country's press: each member outlet's share, blended by the outlet's weight."""
        if foreign and r["slug"] == own_of.get(country):
            return 0.0
        parts = [
            (w, outlet_totals[k] - (own_n[k] if foreign else 0), r["by_outlet"].get(k, 0)) for k, w in weight.items() if k[0] == country
        ]
        parts = [(w, n, x) for w, n, x in parts if n > 0]
        return sum(w * x / n for w, n, x in parts) / sum(w for w, _, _ in parts) if parts else 0.0

    voting = sorted({c for c, _ in outlet_totals})
    foreign_mentions = {c: sum(outlet_totals[k] - own_n[k] for k in outlet_totals if k[0] == c) for c in voting}
    foreign_voting = [c for c in voting if foreign_mentions[c] >= FOREIGN_MIN_MENTIONS]
    for r in rows:
        r["share_in"] = {c: round(v, 4) for c in voting if (v := view(r, c, False))}
        r["country_share"] = round(sum(r["share_in"].values()) / max(1, len(voting)), 4)
        r["countries"] = len(r["share_in"])
        r["foreign_share"] = round(sum(view(r, c, True) for c in foreign_voting) / max(1, len(foreign_voting)), 4)
        r["foreign_countries"] = sum(1 for c in r["share_in"] if own_of.get(c) != r["slug"])
    for t in table:
        t["mentions"] = sum(outlet_totals[k] for k in outlet_totals if k[0] == t["country"])
        t["own_slug"] = own_of.get(t["country"])
        own = next((r for r in rows if r["slug"] == t["own_slug"]), None)
        t["own_share"] = round(own["share_in"].get(t["country"], 0), 3) if own else 0.0
        t["top"] = max(rows, key=lambda r: r["share_in"].get(t["country"], 0))["slug"] if t["mentions"] else None
    rows.sort(key=lambda r: (-r["foreign_share"], r["slug"]))
    leanings = _by_leaning(rows, outlet_totals, table)
    for r in rows:
        del r["by_outlet"]
    shares = [r["foreign_share"] for r in rows]
    return {
        "rows": rows,
        "panel": table,
        "countries": len(voting),
        "foreign_countries": len(foreign_voting),
        "top5_share": round(sum(shares[:5]), 3),
        "by_base": _home_bias(speeches, table, rows),
        "articles": len(articles),
        "outlets_counted": sum(len(t["members"]) for t in table),
        "sample_articles": len(_outside(news)),
        "paragraphs": sum(len(a["paragraphs"]) for a in articles),
        "named": len(rows),
        "delegations": sum(1 for s in speeches if s.iso3),
        "own_share_median": round(statistics.median(t["own_share"] for t in table if t["mentions"]), 3) if table else None,
        "by_leaning": leanings,
    }


# the page's three groups of leaning; state media are left out, since a rating of a state outlet is not a party leaning
LEANING_GROUPS = {"Left of centre": ("Left", "Left-centre"), "Centre": ("Centre",), "Right of centre": ("Right-centre", "Right")}
LEANING_TOP = 6


def _by_leaning(rows: list[dict], outlet_totals: Counter, table: list[dict]) -> dict:
    """What outlets of each leaning covered: each outlet's share of its mentions per delegation, averaged over the group's outlets."""
    info = {r["outlet"]: r for r in _registry()}
    group_of = {label: g for g, labels in LEANING_GROUPS.items() for label in labels}
    outlets: dict[str, list[tuple[str, str]]] = {g: [] for g in LEANING_GROUPS}
    for k, n in outlet_totals.items():
        r = info.get(k[1], {})
        if n and r.get("state_media") != "yes" and (g := group_of.get(r.get("leaning", ""))):
            outlets[g].append(k)
    top = [r["slug"] for r in rows[:LEANING_TOP]]
    out = {"groups": [], "delegations": top}
    for g, keys in outlets.items():
        share = (
            {
                r["slug"]: round(sum(r["by_outlet"].get(k, 0) / outlet_totals[k] for k in keys) / len(keys), 3)
                for r in rows
                if r["slug"] in top
            }
            if keys
            else {}
        )
        out["groups"].append({"group": g, "outlets": sorted(k[1] for k in keys), "share": share})
    counted = [info.get(m["outlet"], {}) for t in table for m in t["members"]]
    out["mix"] = dict(Counter(("State media" if r.get("state_media") == "yes" else r.get("leaning") or "Not rated") for r in counted))
    return out


def _same_country(slug: str, country: str, speeches: list[Speech]) -> bool:
    """Whether a delegation is the country an outlet is based in, matching the registry's plain country name to the delegation's."""
    s = next(x for x in speeches if x.slug == slug)
    return mentions.named(country).get(s.iso3, 0) > 0


def _spread(hits: list[dict]) -> list[dict]:
    """Up to SNIPPETS excerpts, one per outlet before any outlet gets a second, so one live blog cannot fill the list."""
    by_outlet: dict[str, list[dict]] = {}
    for h in hits:
        by_outlet.setdefault(h["outlet"], []).append(h)
    out, depth = [], 0
    while len(out) < SNIPPETS and any(len(v) > depth for v in by_outlet.values()):
        out += [v[depth] for v in by_outlet.values() if len(v) > depth][: SNIPPETS - len(out)]
        depth += 1
    return out


def _home_bias(speeches: list[Speech], table: list[dict], rows: list[dict]) -> list[dict]:
    """For each region's panel outlets, the share of their mentions that go to their own region, against that region's share of speakers.

    Each country's outlet counts once, so a region's figure is the average over its countries."""
    region = {s.slug: s.region for s in speeches}
    speakers = Counter(s.region for s in speeches if s.iso3)
    out = []
    for base in sorted({t["region"] for t in table if t["region"] in speakers}):
        countries = [t for t in table if t["region"] == base and t["mentions"]]
        if not countries:
            continue
        home = [sum(r["share_in"].get(t["country"], 0) for r in rows if region.get(r["slug"]) == base) for t in countries]
        weight = Counter()
        for t in countries:
            for r in rows:
                if r["share_in"].get(t["country"]):
                    weight[r["slug"]] += r["share_in"][t["country"]] / len(countries)
        out.append(
            {
                "region": base,
                "countries": [t["country"] for t in countries],
                "outlets": [t["outlet"] for t in countries],
                "articles": sum(t["reports"] for t in countries),
                "words": sum(t["words"] for t in countries),
                "mentions": sum(t["mentions"] for t in countries),
                "home_share": round(sum(home) / len(home), 3),
                "home_speaker_share": round(speakers[base] / sum(speakers.values()), 3),
                "top": [{"slug": slug, "share": round(w, 3)} for slug, w in weight.most_common(5)],
                "outsider": next(
                    ({"slug": slug, "share": round(w, 3)} for slug, w in weight.most_common() if region.get(slug) != base), None
                ),
            }
        )
    return out


def issue_voices(speeches: list[Speech], news: list[dict], coverage: dict[str, dict]) -> list[dict]:
    """Each issue in three voices: how often speeches raise it, how often the UN's summary of the speech keeps it, and how much press text it gets."""
    press_text = " ".join(p for a in panel(news)[0] for p in a["paragraphs"])
    podium_text = " ".join(s.text for s in speeches)
    summarised = [s for s in speeches if coverage.get(s.slug, {}).get("summary")]
    press_counts, podium_counts = lexicons.issue_counts(press_text), lexicons.issue_counts(podium_text)
    press_words, podium_words = max(1, len(press_text.split())), max(1, len(podium_text.split()))
    out = []
    for issue in lexicons.ISSUES:
        pattern = lexicons.issue_pattern(issue)
        raised = [s for s in summarised if pattern.search(s.text)]
        kept = [s for s in raised if pattern.search(" ".join(coverage[s.slug]["summary"]))]
        podium_rate = 1000 * podium_counts[issue] / podium_words
        press_rate = 1000 * press_counts[issue] / press_words
        out.append(
            {
                "issue": issue,
                "speeches": len(raised),
                "share_of_speeches": round(len(raised) / len(summarised), 3) if summarised else 0,
                "summary_kept": len(kept),
                "kept_share": round(len(kept) / len(raised), 3) if raised else None,
                "podium_per_1000": round(podium_rate, 2),
                "press_per_1000": round(press_rate, 2),
                "press_ratio": round(press_rate / podium_rate, 2) if podium_rate else None,
                "dropped": [s.slug for s in raised if s not in kept],
            }
        )
    return out


def headlines(speeches: list[Speech], coverage: dict[str, dict]) -> dict:
    """The UN press office's headline for every speaker: its tone, and which issues and states it names."""
    rows = {}
    for s in speeches:
        c = coverage.get(s.slug)
        if not c or not c["headline"]:
            continue
        family, verb = tone(c["headline"])
        named = mentions.named(c["headline"])
        named.pop(s.iso3, None)
        rows[s.slug] = {
            "headline": c["headline"],
            "tone": family,
            "verb": verb,
            "issues": [i for i, hit in lexicons.issues(c["headline"]).items() if hit],
            "names": sorted(named),
            "quote": bool(re.search(r"[‘“'\"]", c["headline"])),
        }
    return {
        "rows": rows,
        "tones": Counter(r["tone"] for r in rows.values()).most_common(),
        "verbs": Counter(r["verb"] for r in rows.values() if r["verb"]).most_common(15),
        "issues": Counter(i for r in rows.values() for i in r["issues"]).most_common(),
        "naming_another_state": sorted(slug for slug, r in rows.items() if r["names"]),
        "quoted": sum(r["quote"] for r in rows.values()),
    }


def translations(coverage: dict[str, dict]) -> dict:
    """Which speeches UN News wrote up in other languages, from the links on each debate page."""
    for c in coverage.values():
        for link in c["un_news"]:
            name = link["language"].rstrip(".")
            link["language"] = LANGUAGE_SPELLINGS.get(name, name)
    by_language = Counter(link["language"] for c in coverage.values() for link in c["un_news"])
    return {
        "speeches": sum(1 for c in coverage.values() if c["un_news"]),
        "stories": sum(by_language.values()),
        "languages": by_language.most_common(),
        "rows": {slug: c["un_news"] for slug, c in coverage.items() if c["un_news"]},
    }


def women(speeches: list[Speech], coverage: dict[str, dict]) -> dict:
    """Speakers introduced as "Her Excellency" or another feminine honorific, by rank, and how often each group talks about women and girls."""
    feminine = {s.slug for s in speeches if coverage.get(s.slug, {}).get("honorific", "").startswith("Her")}
    groups = {"women": [s for s in speeches if s.slug in feminine], "men": [s for s in speeches if s.slug not in feminine]}
    return {
        "speakers": sorted(feminine),
        "count": len(feminine),
        "of": len(speeches),
        "by_role": Counter(s.role_group for s in groups["women"]).most_common(),
        "women_and_girls_per_1000": {
            k: round(1000 * sum(len(WOMEN_AND_GIRLS.findall(s.text)) for s in v) / max(1, sum(s.words for s in v)), 2)
            for k, v in groups.items()
        },
    }


def _find(news: list[dict], url: str, needle: str) -> dict | None:
    for a in news:
        if a["url"] == url:
            for p in a["paragraphs"]:
                i = p.find(needle)
                if i >= 0:
                    return {"outlet": a["outlet"], "date": a["date"], "title": a["title"], "url": url, "paragraph": p, "quote": needle}
    return None


def context(session: int, news: list[dict]) -> list[dict]:
    """The week's news events from reference/context_<session>.csv, each with a short quote found in the downloaded article."""
    path = REFERENCE_DIR / f"context_{session}.csv"
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            found = _find(news, row["url"], row["quote"])
            if not found:
                raise ValueError(f"context quote not in the downloaded article: {row['quote']!r} ({row['url']})")
            out.append({"date": row["date"], "event": row["event"], "quote": row["quote"], "outlet": found["outlet"], "url": row["url"]})
    return out


def claims(session: int, speeches: list[Speech], news: list[dict], role_counts: Counter) -> list[dict]:
    """The Assembly President's and the press's numbers about the debate, set against the same count taken from the texts."""
    ai = lexicons.issue_pattern("Artificial intelligence")
    climate = lexicons.issue_pattern("Climate change")
    ai_now = sum(bool(ai.search(s.text)) for s in speeches)
    climate_now = sum(bool(climate.search(s.text)) for s in speeches)
    rights_now = sum(bool(HUMAN_RIGHTS.search(s.text)) for s in speeches)
    climate_change_now = sum(bool(CLIMATE_CHANGE.search(s.text)) for s in speeches)
    ai_then = None
    history = OUTPUT_DIR / "history_ungdc.parquet"
    if history.exists():
        frame = pd.read_parquet(history, columns=["session", "text_en"])
        texts = frame[(frame.session == TREND_SESSION_AI) & frame.text_en.notna()].text_en
        ai_then = int(sum(bool(ai.search(t)) for t in texts))
    common = words.common(speeches)["words"]
    ranked = [w["word"] for w in common]
    peace_rank = ranked.index("peace") + 1 if "peace" in ranked else None
    top, peace = common[0], next((w for w in common if w["word"] == "peace"), None)
    day6 = "https://news.un.org/en/story/2026/09/1168478"
    heads = role_counts["head_of_state_or_government"]
    ministers = role_counts["foreign_minister"] + role_counts["other_minister"]

    def claim(topic, url, needle, ours, verdict, detail):
        found = _find(news, url, needle)
        if not found:
            raise ValueError(f"claim quote not in the downloaded article: {needle!r}")
        return {"topic": topic, "source": found["outlet"], "url": url, "quote": needle, "ours": ours, "verdict": verdict, "detail": detail}

    out = [
        claim(
            "Who spoke",
            day6,
            "194 speakers took the floor during the 2026 General Debate, including 113 Heads of State and Government, one crown prince, 11 Vice Presidents, seven Deputy Prime Ministers and 48 Ministers",
            f"{sum(role_counts.values())} delegations; {heads} heads of state or government, {role_counts['deputy_head']} deputies, {ministers} ministers, "
            f"{role_counts['diplomat']} ambassadors",
            "Matches" if sum(role_counts.values()) == 194 else "Differs",
            f"The totals agree. The UN's ranks add to 180 of 194; the other 14 are mostly ambassadors. Our {heads} heads include the crown prince (UN: 113 + 1), "
            f"our {role_counts['deputy_head']} deputies compare with its 18 vice presidents and deputy prime ministers, and our {ministers} ministers with its 48.",
        ),
        claim(
            "AI's rise",
            day6,
            "Just four years ago, only five delegations raised artificial intelligence in the Assembly Hall, he said. This year, 128 did",
            f"{ai_now} speeches name AI this year; {ai_then if ai_then is not None else 'n/a'} did in 2022",
            "Matches" if ai_then == 5 and abs(ai_now - 128) <= 5 else "Close" if abs(ai_now - 128) <= 12 else "Differs",
            f"Counting any mention of “artificial intelligence” or “AI”, the 2022 texts give {ai_then} and this year's {ai_now}; "
            "the few extra this year are speeches that name AI only in passing.",
        ),
        claim(
            "AI over climate",
            day6,
            "AI was discussed by more delegations this year than climate change or human rights",
            f"AI {ai_now}; \u201cclimate change\u201d {climate_change_now}, any climate wording {climate_now}; human rights {rights_now} speeches",
            "Holds"
            if ai_now > climate_now and ai_now > rights_now
            else ("Depends on wording" if ai_now > climate_change_now else "Does not hold"),
            "AI beats the exact phrase \u201cclimate change\u201d but not climate language as a whole: many speeches talk of the climate crisis, "
            "climate finance or sea-level rise without the phrase.",
        ),
        claim(
            "The word of the week",
            day6,
            "one word rose above all others: peace",
            f"“peace” is the #{peace_rank} word after stop words" if peace_rank else "not among the most common words",
            "Holds" if peace_rank == 1 else "Close second",
            f"\u201c{top['word']}\u201d is used {top['count']:,} times against {peace['count']:,} for \u201cpeace\u201d"
            f"; both appear in {peace['speeches']} speeches. Counted across every English text, with function words removed."
            if peace and peace_rank != 1
            else "Counted across every English text, with function words removed.",
        ),
        claim(
            "Leaders in the room",
            "https://www.cnn.com/2026/09/21/world/unga-2026-what-to-expect-latam-intl",
            "it seems like we have over 130 heads of state or government coming",
            f"{heads} heads of state or government spoke",
            "Fewer came" if heads < 130 else "As expected",
            "Previews counted leaders expected in New York; some sent a deputy or a minister to the podium in the end.",
        ),
    ]
    return out
