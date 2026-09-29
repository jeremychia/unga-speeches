"""Who named whom: every state a speech names, by country name or a common adjective, with the sentence where it first does."""

import re
from collections import Counter

from unga_speeches.analysis import lexicons
from unga_speeches.analysis.corpus import Speech
from unga_speeches.enrich import countries

# names and adjectives speeches use that the record aliases do not cover
EXTRA = {
    "russian federation": "RUS",
    "russian": "RUS",
    "ukrainian": "UKR",
    "israeli": "ISR",
    "palestinian": "PSE",
    "iranian": "IRN",
    "syrian": "SYR",
    "south sudanese": "SSD",
    "sudanese": "SDN",
    "lebanese": "LBN",
    "venezuelan": "VEN",
    "cuban": "CUB",
    "haitian": "HTI",
    "afghan": "AFG",
    "yemeni": "YEM",
    "libyan": "LBY",
    "somali": "SOM",
    "armenian": "ARM",
    "azerbaijani": "AZE",
    "iraqi": "IRQ",
    "qatari": "QAT",
    "emirati": "ARE",
    "united arab emirates": "ARE",
    "uae": "ARE",
    "saudi": "SAU",
    "pakistani": "PAK",
    "ethiopian": "ETH",
    "eritrean": "ERI",
    "egyptian": "EGY",
    "chinese": "CHN",
    "japanese": "JPN",
    "north korea": "PRK",
    "dprk": "PRK",
    "south korea": "KOR",
    "rwandan": "RWA",
    "malian": "MLI",
    "nigerian": "NGA",
    "colombian": "COL",
    "cambodian": "KHM",
    "thai": "THA",
    "philippine": "PHL",
    "democratic republic of congo": "COD",
    "drc": "COD",
    "eastern congo": "COD",
    "republic of the congo": "COG",
    "republic of congo": "COG",
    "cote d'ivoire": "CIV",
    "côte d'ivoire": "CIV",
    "türkiye": "TUR",
    "turkish": "TUR",
    "cypriot": "CYP",
    "u.s.": "USA",
    "usa": "USA",
}
# a bare "Congo" is used for both Congos, and the pope is a person rather than the state
AMBIGUOUS = {"congo", "pope"}
# places named after a state that are not the state; matched so the state inside them is not counted
GEOGRAPHY = {
    "gulf of guinea",
    "upper guinea",
    "lake chad",
    "south china sea",
    "east china sea",
    "gulf of mexico",
    "sea of japan",
    "taiwan strait",
}


def _pattern() -> tuple[re.Pattern, dict[str, str]]:
    names = {name: iso3 for name, iso3 in countries._names().items() if name not in AMBIGUOUS and len(iso3) == 3}
    names.update(EXTRA)
    names.update(dict.fromkeys(GEOGRAPHY, ""))
    # longest first, so "Papua New Guinea" and "South Sudan" win over "Guinea" and "Sudan" at the same place
    alternatives = sorted(names, key=len, reverse=True)
    body = "|".join(re.escape(n).replace(r"\ ", r"\s+").replace("'", "['’]") for n in alternatives)
    lookup = {re.sub(r"[’]", "'", n): iso3 for n, iso3 in names.items()}
    return re.compile(rf"(?<![\w-])(?:{body})(?![\w-])", re.I), lookup


PATTERN, LOOKUP = _pattern()


def _iso3(match: str) -> str | None:
    return LOOKUP.get(re.sub(r"\s+", " ", match.replace("’", "'")).lower())


def named(text: str) -> Counter:
    """How many times the text names each state, by iso3."""
    return Counter(iso3 for m in PATTERN.finditer(text) if (iso3 := _iso3(m.group())))


class _Names:
    """Searches for one state the way the counts do, so the evidence sentence is one that was counted."""

    def __init__(self, iso3: str):
        self.iso3 = iso3

    def search(self, text: str):
        return next((m for m in PATTERN.finditer(text) if _iso3(m.group()) == self.iso3), None)


def build(speeches: list[Speech]) -> dict:
    by_iso3 = {s.iso3: s for s in speeches if s.iso3}
    edges = []
    for s in speeches:
        counts = named(s.text)
        counts.pop(s.iso3, None)
        for iso3, n in counts.items():
            if iso3 not in by_iso3 and iso3 != "TWN":
                continue
            target = by_iso3[iso3].slug if iso3 in by_iso3 else iso3
            edges.append({"from": s.slug, "to": target, "times": n, "evidence": lexicons.first_mention(s.verbatim, _Names(iso3))})

    named_by = Counter(e["to"] for e in edges)
    times = Counter()
    for e in edges:
        times[e["to"]] += e["times"]
    region = {s.slug: s.region for s in speeches}
    pairs = {(e["from"], e["to"]) for e in edges}
    mutual = sorted({tuple(sorted(p)) for p in pairs if (p[1], p[0]) in pairs})
    same_region = sum(1 for e in edges if region.get(e["from"]) == region.get(e["to"]))
    return {
        "edges": edges,
        "most_named": [{"slug": slug, "speeches": n, "times": times[slug]} for slug, n in named_by.most_common()],
        "names_most": [{"slug": slug, "states": n} for slug, n in Counter(e["from"] for e in edges).most_common()],
        "mutual": [list(p) for p in mutual],
        "same_region_share": round(same_region / len(edges), 3) if edges else None,
        "named_nobody": sorted(s.slug for s in speeches if s.slug not in {e["from"] for e in edges}),
    }
