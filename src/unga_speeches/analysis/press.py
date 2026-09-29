"""What was said about the debate: the UN press office's headline for each speaker, outside press coverage, and the UN's own summary checked against the texts."""

import csv
import json
import re
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


def attention(speeches: list[Speech], news: list[dict]) -> dict:
    """Paragraphs of outside press that name each delegation, by country or, within an article that names the country, its speaker."""
    articles = _outside(news)
    total_words = sum(s.words for s in speeches)
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
                        {"outlet": a["outlet"], "date": a["date"], "title": a["title"], "url": a["url"], **_cut(p, m.start(), m.end())}
                    )
        if hits:
            rows.append(
                {
                    "slug": s.slug,
                    "paragraphs": len(hits),
                    "articles": len({h["url"] for h in hits}),
                    "share_of_words": round(s.words / total_words, 4),
                    "snippets": hits[:SNIPPETS],
                }
            )
    total = sum(r["paragraphs"] for r in rows)
    for r in rows:
        r["share_of_press"] = round(r["paragraphs"] / total, 4)
    rows.sort(key=lambda r: -r["paragraphs"])
    shares = [r["share_of_press"] for r in rows]
    return {
        "rows": rows,
        "articles": len(articles),
        "paragraphs": sum(len(a["paragraphs"]) for a in articles),
        "named": len(rows),
        "delegations": sum(1 for s in speeches if s.iso3),
        "top1_share": shares[0] if shares else 0,
        "top5_share": round(sum(shares[:5]), 3),
    }


def issue_voices(speeches: list[Speech], news: list[dict], coverage: dict[str, dict]) -> list[dict]:
    """Each issue in three voices: how often speeches raise it, how often the UN's summary of the speech keeps it, and how much press text it gets."""
    press_text = " ".join(p for a in _outside(news) for p in a["paragraphs"])
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
