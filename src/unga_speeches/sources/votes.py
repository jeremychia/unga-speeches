"""How each member state voted on the General Assembly's resolutions on the war in Ukraine.

The UN Digital Library's voting records block scripted downloads, so the vote tables are read from the Wikipedia articles that
transcribe them, and the counts are checked against the official totals before the file is written. The 2022 table also matches
the UN record country by country, checked by hand against the archived record page."""

import csv
import json
import logging
import re
from pathlib import Path

from unga_speeches.config import RAW_DIR, REFERENCE_DIR
from unga_speeches.http import Client

log = logging.getLogger(__name__)

API = "https://en.wikipedia.org/w/api.php?action=parse&page={page}&prop=wikitext&format=json&formatversion=2&redirects=1"
RESOLUTIONS = {
    "ES-11/1": {
        "page": "United_Nations_General_Assembly_Resolution_ES-11/1",
        "record": "https://digitallibrary.un.org/record/3959039",
        "totals": {"yes": 141, "no": 5, "abstain": 35, "absent": 12},
    },
    "ES-11/7": {
        "page": "United_Nations_General_Assembly_Resolution_ES-11/7",
        "record": "https://digitallibrary.un.org/record/4076672",
        "totals": {"yes": 93, "no": 18, "abstain": 65, "absent": 17},
    },
}
ROWS = {"yes|Approve": "yes", "no|Against": "no", "maybe|Abstain": "abstain", "tba|Absent": "absent"}
# Wikipedia's link targets for states whose name differs from reference/delegations.csv
ALIAS = {
    "bahamas": "BHS", "the bahamas": "BHS", "bolivia": "BOL", "brunei": "BRN", "cape verde": "CPV", "côte d'ivoire": "CIV", "ivory coast": "CIV",
    "czech republic": "CZE", "democratic republic of the congo": "COD", "republic of the congo": "COG", "congo": "COG", "gambia": "GMB",
    "the gambia": "GMB", "georgia (country)": "GEO", "georgia": "GEO", "iran": "IRN", "laos": "LAO", "micronesia": "FSM",
    "federated states of micronesia": "FSM", "moldova": "MDA", "myanmar": "MMR", "national unity government of myanmar": "MMR",
    "north korea": "PRK", "south korea": "KOR", "republic of korea": "KOR", "russia": "RUS", "syria": "SYR", "ba'athist syria": "SYR",
    "tanzania": "TZA", "turkey": "TUR", "united kingdom": "GBR", "united states": "USA", "venezuela": "VEN", "vietnam": "VNM",
    "east timor": "TLS", "são tomé and príncipe": "STP", "sao tome and principe": "STP", "eswatini": "SWZ", "netherlands": "NLD",
    "republic of ireland": "IRL", "bosnia-herzegovina": "BIH", "islamic republic of afghanistan": "AFG",
}  # fmt: skip
# links inside footnotes, not votes: Myanmar's seat is held by the government in exile, which a note explains
FOOTNOTE_LINKS = {"state administration council"}


def _codes() -> dict[str, str]:
    with (REFERENCE_DIR / "delegations.csv").open(encoding="utf-8") as f:
        return {r["name"].lower(): r["iso3"] for r in csv.DictReader(f) if r["iso3"]} | ALIAS


def parse(wikitext: str) -> dict[str, str]:
    """iso3 -> vote from the article's vote table, one row per vote with the states linked in it."""
    codes, votes = _codes(), {}
    for marker, vote in ROWS.items():
        block = wikitext[wikitext.index("{{" + marker + "}}") :]
        block = block[: block.index("|-", 5)]
        for link in re.findall(r"\[\[([^\]]+)\]\]", block):
            name = link.split("|")[-1].strip().lower()
            if name in FOOTNOTE_LINKS:
                continue
            if name not in codes:
                raise ValueError(f"no country code for {link!r}")
            votes.setdefault(codes[name], vote)
    return votes


def build(client: Client | None = None) -> Path:
    client = client or Client()
    rows = []
    for resolution, spec in RESOLUTIONS.items():
        dest = RAW_DIR / "votes" / f"{resolution.replace('/', '-')}.json"
        fetched = client.fetch(API.format(page=spec["page"]), dest)
        votes = parse(json.loads(fetched.path.read_text(encoding="utf-8"))["parse"]["wikitext"])
        counts = {v: sum(1 for x in votes.values() if x == v) for v in spec["totals"]}
        if counts != spec["totals"]:
            raise ValueError(f"{resolution}: the table gives {counts}, the official totals are {spec['totals']}")
        rows += [{"resolution": resolution, "iso3": iso3, "vote": vote, "source": spec["record"]} for iso3, vote in sorted(votes.items())]
        log.info("%s: %s", resolution, counts)
    out = REFERENCE_DIR / "ukraine_votes.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, ["resolution", "iso3", "vote", "source"])
        writer.writeheader()
        writer.writerows(rows)
    return out
