"""How each member state voted on the General Assembly's resolutions on the wars in Ukraine and Gaza.

The UN Digital Library's voting records block scripted downloads, so the vote tables are read from the Wikipedia articles that
transcribe them, and the counts are checked against the official totals before the file is written. The ES-11/1 table also matches
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
        "war": "ukraine",
        "adopted": "2022-03-02",
        "page": "United_Nations_General_Assembly_Resolution_ES-11/1",
        "source": "https://digitallibrary.un.org/record/3959039",
        "totals": {"yes": 141, "no": 5, "abstain": 35, "absent": 12},
    },
    "ES-11/7": {
        "war": "ukraine",
        "adopted": "2025-02-24",
        "page": "United_Nations_General_Assembly_Resolution_ES-11/7",
        "source": "https://digitallibrary.un.org/record/4076672",
        "totals": {"yes": 93, "no": 18, "abstain": 65, "absent": 17},
    },
    "ES-10/22": {
        "war": "gaza",
        "adopted": "2023-12-12",
        "page": "United_Nations_General_Assembly_Resolution_ES-10/22",
        "source": "https://undocs.org/A/RES/ES-10/22",
        "totals": {"yes": 153, "no": 10, "abstain": 23, "absent": 7},
    },
    "ES-10/23": {
        "war": "gaza",
        "adopted": "2024-05-10",
        "page": "United_Nations_General_Assembly_Resolution_ES-10/23",
        "source": "https://undocs.org/A/RES/ES-10/23",
        "totals": {"yes": 143, "no": 9, "abstain": 25, "absent": 16},
    },
}
# the two layouts Wikipedia uses: a row per vote with the states linked, or a column per vote with a flag per state
ROWS = {"yes|Approve": "yes", "no|Against": "no", "maybe|Abstain": "abstain", "tba|Absent": "absent"}
COLUMN = [(re.compile(r"favou?r|agree", re.I), "yes"), (re.compile(r"abstain|abstention", re.I), "abstain"),
          (re.compile(r"against|oppose", re.I), "no"), (re.compile(r"absent|no vote|non-voting|did not vote", re.I), "absent")]  # fmt: skip
# Wikipedia's names for states whose name differs from reference/delegations.csv
ALIAS = {
    "bahamas": "BHS", "the bahamas": "BHS", "bolivia": "BOL", "brunei": "BRN", "cape verde": "CPV", "côte d'ivoire": "CIV", "ivory coast": "CIV",
    "cote d'ivoire": "CIV", "czech republic": "CZE", "democratic republic of the congo": "COD", "republic of the congo": "COG", "congo": "COG",
    "gambia": "GMB", "the gambia": "GMB", "georgia (country)": "GEO", "georgia": "GEO", "iran": "IRN", "laos": "LAO", "micronesia": "FSM",
    "federated states of micronesia": "FSM", "moldova": "MDA", "myanmar": "MMR", "national unity government of myanmar": "MMR",
    "north korea": "PRK", "south korea": "KOR", "republic of korea": "KOR", "russia": "RUS", "syria": "SYR", "ba'athist syria": "SYR",
    "tanzania": "TZA", "turkey": "TUR", "united kingdom": "GBR", "united states": "USA", "venezuela": "VEN", "vietnam": "VNM",
    "east timor": "TLS", "são tomé and príncipe": "STP", "sao tome and principe": "STP", "eswatini": "SWZ", "netherlands": "NLD",
    "republic of ireland": "IRL", "bosnia-herzegovina": "BIH", "islamic republic of afghanistan": "AFG", "guinea bissau": "GNB",
}  # fmt: skip
# links inside footnotes, not votes: Myanmar's seat is held by the government in exile, which a note explains
FOOTNOTE_LINKS = {"state administration council"}


def _codes() -> dict[str, str]:
    with (REFERENCE_DIR / "delegations.csv").open(encoding="utf-8") as f:
        return {r["name"].lower(): r["iso3"] for r in csv.DictReader(f) if r["iso3"]} | ALIAS


def _code(name: str, codes: dict[str, str]) -> str | None:
    name = name.strip().lower()
    if name in FOOTNOTE_LINKS:
        return None
    if name not in codes:
        raise ValueError(f"no country code for {name!r}")
    return codes[name]


def parse(wikitext: str) -> dict[str, str]:
    """iso3 -> vote from the article's vote table, in whichever of Wikipedia's two layouts it uses."""
    return _parse_columns(wikitext) if "{{flag|" in wikitext and "{{yes|Approve}}" not in wikitext else _parse_rows(wikitext)


def _parse_rows(wikitext: str) -> dict[str, str]:
    """A row per vote, with the states linked in it."""
    codes, votes = _codes(), {}
    for marker, vote in ROWS.items():
        block = wikitext[wikitext.index("{{" + marker + "}}") :]
        block = block[: block.index("|-", 5)]
        for link in re.findall(r"\[\[([^\]]+)\]\]", block):
            if code := _code(link.split("|")[-1], codes):
                votes.setdefault(code, vote)
    return votes


def _parse_columns(wikitext: str) -> dict[str, str]:
    """A column per vote, headed "In favour (153)" or "Agree (143)", with a flag per state; the first such table in the article."""
    codes, votes = _codes(), {}
    header = re.search(r"\n!([^\n]*\(\d+\)[^\n]*)\n(?:![^\n]*\n)?", wikitext)
    headings = re.findall(r"([^!|]*?)\((\d+)\)", wikitext[header.start() : header.end()])
    order = [next(vote for pattern, vote in COLUMN if pattern.search(label)) for label, _ in headings]
    # a column can hold its own nested table (a long "in favour" list split in two), so cells are read by depth: a cell of the outer
    # table starts a column, and anything inside a nested table belongs to the column it sits in; the next outer row (observers) ends it
    cells, depth = [], 1
    for line in wikitext[header.end() :].split("\n"):
        if line.startswith("{|"):
            depth += 1
        elif line.startswith("|}"):
            depth -= 1
            if depth == 0:
                break
        elif line.startswith("|-"):
            if depth == 1 and any("{{flag|" in c for c in cells):
                break
        elif line.startswith("|") and depth == 1:
            cells.append(line)
        elif cells:
            cells[-1] += "\n" + line
    cells = [c for c in cells if "{{flag|" in c]
    if len(cells) != len(order):
        raise ValueError(f"found {len(cells)} columns of flags for {len(order)} headings")
    for vote, cell in zip(order, cells, strict=True):
        # a state is a flag template, or a decorative flag followed by a link ("{{flagdeco|DPRK}} [[North Korea|...]]")
        for flag in re.findall(r"\{\{flag\|([^}|]+)|\{\{flagdeco\|[^}]*\}\}\s*\[\[([^\]|]+)", cell):
            if code := _code(flag[0] or flag[1], codes):
                votes.setdefault(code, vote)
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
        rows += [
            {"resolution": resolution, "war": spec["war"], "adopted": spec["adopted"], "iso3": iso3, "vote": vote, "source": spec["source"]}
            for iso3, vote in sorted(votes.items())
        ]
        log.info("%s: %s", resolution, counts)
    out = REFERENCE_DIR / "un_votes.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, ["resolution", "war", "adopted", "iso3", "vote", "source"])
        writer.writeheader()
        writer.writerows(rows)
    return out
