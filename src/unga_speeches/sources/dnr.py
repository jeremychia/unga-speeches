"""The biggest news brands in each market, from the Reuters Institute Digital News Report: the online brands most used for news in the last week."""

import csv
import io
import logging
import re
from pathlib import Path

from unga_speeches.config import RAW_DIR, REFERENCE_DIR
from unga_speeches.http import Client

log = logging.getLogger(__name__)

YEAR = 2026
BASE = f"https://reutersinstitute.politics.ox.ac.uk/digital-news-report/{YEAR}"
# the report's market pages, with the country name the outlet registry uses
MARKETS = {
    "united-states": "United States", "argentina": "Argentina", "brazil": "Brazil", "canada": "Canada", "chile": "Chile",
    "colombia": "Colombia", "mexico": "Mexico", "peru": "Peru", "austria": "Austria", "belgium": "Belgium", "bulgaria": "Bulgaria",
    "croatia": "Croatia", "czech-republic": "Czechia", "denmark": "Denmark", "finland": "Finland", "france": "France",
    "germany": "Germany", "greece": "Greece", "hungary": "Hungary", "ireland": "Ireland", "italy": "Italy",
    "netherlands": "Netherlands", "norway": "Norway", "poland": "Poland", "portugal": "Portugal", "romania": "Romania",
    "serbia": "Serbia", "slovakia": "Slovakia", "spain": "Spain", "sweden": "Sweden", "switzerland": "Switzerland",
    "turkey": "Türkiye", "united-kingdom": "United Kingdom", "australia": "Australia", "hong-kong": "Hong Kong", "india": "India",
    "indonesia": "Indonesia", "japan": "Japan", "malaysia": "Malaysia", "philippines": "Philippines", "singapore": "Singapore",
    "south-korea": "South Korea", "taiwan": "Taiwan", "thailand": "Thailand", "kenya": "Kenya", "morocco": "Morocco",
    "nigeria": "Nigeria", "south-africa": "South Africa",
}  # fmt: skip
CHART = re.compile(r'<iframe[^>]+src="(https://datawrapper\.dwcdn\.net/[A-Za-z0-9]+/\d+/)"')
REACH = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*%?\s*$")
# charts on a market page that are not brand-reach charts
OTHER_CHARTS = re.compile(r"trust|^year|^rank", re.I)
ONLINE_NAME = re.compile(
    r"online|\.(?:com|co|net|org|be|de|fr|es|it|nl|ch|at|ie|uk|au|jp|kr|in|sg|my|id|ph|th|tw|hk|ke|ng|za|ma|br|ar|cl|co|mx|pe|ca|cz|hu|pl|sk|ro|rs|gr|fi|no|se|dk|pt|tr|bg|hr|si|info|tv)\b",
    re.I,
)
ONLINE_SHARE = 0.5  # a chart is the online one when at least this share of its brands say "online" or give a web address


def _rows(text: str) -> list[list[str]]:
    delimiter = "\t" if text.split("\n", 1)[0].count("\t") > text.split("\n", 1)[0].count(",") else ","
    return [r for r in csv.reader(io.StringIO(text), delimiter=delimiter) if any(c.strip() for c in r)]


def _charts(client: Client, slug: str) -> list[tuple[str, list[list[str]]]]:
    page = client.fetch(f"{BASE}/{slug}", RAW_DIR / "dnr" / str(YEAR) / slug / "page.html")
    html = page.path.read_text(encoding="utf-8", errors="replace")
    out = []
    for url in CHART.findall(html):
        name = url.rstrip("/").split("/")[-2]
        data = client.fetch(url + "dataset.csv", RAW_DIR / "dnr" / str(YEAR) / slug / f"{name}.csv")
        if data:
            out.append((url, _rows(data.path.read_text(encoding="utf-8", errors="replace"))))
    return out


def _brands(rows: list[list[str]]) -> list[dict]:
    out = []
    for row in rows[1:]:
        if len(row) > 1 and row[0].strip() and (m := REACH.match(row[1])):
            out.append({"brand": row[0].strip(), "reach": float(m.group(1))})
    return out


def online_brands(client: Client, slug: str) -> tuple[list[str], list[dict]] | None:
    """The market's online top brands: every brand-reach chart whose brands are mostly online, merged, highest reach first.

    Markets with two language communities, such as Belgium and Canada, have one online chart each."""
    charts = [(url, _brands(rows)) for url, rows in _charts(client, slug) if rows and not OTHER_CHARTS.search(rows[0][0].strip())]
    online = [(url, b) for url, b in charts if b and sum(bool(ONLINE_NAME.search(x["brand"])) for x in b) >= ONLINE_SHARE * len(b)]
    if not online:
        return None
    best: dict[str, float] = {}
    for _, brands in online:
        for b in brands:
            best[b["brand"]] = max(best.get(b["brand"], 0), b["reach"])
    ranked = sorted(best.items(), key=lambda x: (-x[1], x[0]))
    return [url for url, _ in online], [{"rank": i, "brand": b, "reach": r} for i, (b, r) in enumerate(ranked, start=1)]


def build(client: Client | None = None) -> Path:
    """Every market's online top brands, written to reference/dnr_brands_<year>.csv with the chart each came from."""
    client = client or Client()
    out = REFERENCE_DIR / f"dnr_brands_{YEAR}.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["market", "country", "rank", "brand", "reach", "chart_url", "page_url"], lineterminator="\n")
        w.writeheader()
        for slug, country in MARKETS.items():
            found = online_brands(client, slug)
            if not found:
                log.warning("%s: no online brands chart", slug)
                continue
            urls, brands = found
            log.info("%s: %d online brands, top %s", slug, len(brands), brands[0]["brand"] if brands else "-")
            for b in brands:
                w.writerow({"market": slug, "country": country, **b, "chart_url": " ".join(urls), "page_url": f"{BASE}/{slug}"})
    return out
