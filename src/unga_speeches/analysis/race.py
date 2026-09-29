"""The race for the next Secretary-General as it was talked about from the podium: who named which candidate, and who asked for what kind of Secretary-General."""

import csv
import json
import re

from unga_speeches.analysis import lexicons
from unga_speeches.analysis.corpus import Speech
from unga_speeches.config import OUTPUT_DIR, REFERENCE_DIR

# what speakers asked of the next Secretary-General, beyond naming a candidate
ASKS = {
    "A woman": r"(first|a) (woman|female)[^.]{0,80}secretary-general|secretary-general[^.]{0,80}\b(a woman|female|first woman)\b",
    "Latin America's turn": r"(latin america|grulac|caribbean)[^.]{0,120}secretary-general|secretary-general[^.]{0,120}(latin america|grulac)",
    "A transparent selection": r"(transparen|inclusive|merit)[^.]{0,80}(selection|appointment|process)[^.]{0,80}secretary-general"
    r"|secretary-general[^.]{0,80}(selection|appointment|process)[^.]{0,80}(transparen|inclusive|merit)",
}
_ASKS = {name: re.compile(p, re.I) for name, p in ASKS.items()}


def candidates(session: int) -> list[dict]:
    path = REFERENCE_DIR / f"sg_candidates_{session}.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _originals(session: int) -> list[dict]:
    """Every text in its original language, so a candidate is found even in a speech with no English text."""
    path = OUTPUT_DIR / f"texts_{session}.jsonl"
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            t = json.loads(line)
            if t["language"] != "en" and t["text"]:
                out.append({"slug": t["slug"], "language": t["language"], "verbatim": " ".join(t["text"].split())})
    return out


def _named(pattern: re.Pattern, speeches: list[Speech], originals: list[dict]) -> list[dict]:
    found = {
        s.slug: {"slug": s.slug, "language": "en", "evidence": lexicons.first_mention(s.verbatim, pattern)}
        for s in speeches
        if pattern.search(s.text)
    }
    for t in originals:
        if t["slug"] not in found and pattern.search(t["verbatim"]):
            found[t["slug"]] = {"slug": t["slug"], "language": t["language"], "evidence": lexicons.first_mention(t["verbatim"], pattern)}
    return list(found.values())


def build(session: int, speeches: list[Speech]) -> dict:
    originals = _originals(session)
    rows = []
    for c in candidates(session):
        named = _named(re.compile(c["pattern"]), speeches, originals)
        polled = int(c["encourage"]) + int(c["discourage"]) + int(c["no_opinion"])
        rows.append(
            {
                "name": c["name"],
                "nationality": c["nationality"],
                "nominated_by": c["nominated_by"],
                "nominated": c["nominated"],
                "withdrew": c["withdrew"] or None,
                "regional_group": c["regional_group"],
                "poll": {
                    "encourage": int(c["encourage"]),
                    "discourage": int(c["discourage"]),
                    "no_opinion": int(c["no_opinion"]),
                    "of": polled,
                },
                "named_by": named,
                "source_url": c["source_url"],
            }
        )
    selection = lexicons.issue_pattern("The next Secretary-General")
    asks = {
        name: [{"slug": s.slug, "evidence": lexicons.first_mention(s.verbatim, p)} for s in speeches if p.search(s.text)]
        for name, p in _ASKS.items()
    }
    return {
        "candidates": rows,
        "asks": asks,
        "mention_selection": [
            {"slug": s.slug, "evidence": lexicons.first_mention(s.verbatim, selection)} for s in speeches if selection.search(s.text)
        ],
        "poll_date": "2026-09-18",
    }
