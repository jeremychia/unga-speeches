"""Resolve the country names the UN records use, including formal and former names, to an iso3 code."""

import csv
import re
import unicodedata
from functools import lru_cache

from .config import REFERENCE_DIR

# names in the records that the delegation list's short names do not cover
ALIASES = {
    "turkey": "TUR", "czech republic": "CZE", "swaziland": "SWZ", "cape verde": "CPV", "ivory coast": "CIV",
    "netherlands": "NLD", "kingdom of the netherlands": "NLD", "the former yugoslav republic of macedonia": "MKD",
    "former yugoslav republic of macedonia": "MKD", "republic of north macedonia": "MKD", "libyan arab jamahiriya": "LBY",
    "zaire": "COD", "western samoa": "WSM", "burma": "MMR", "yugoslavia": "YUG", "federal republic of yugoslavia": "YUG",
    "serbia and montenegro": "SCG", "united kingdom": "GBR", "united states": "USA", "russia": "RUS",
    "republic of korea": "KOR", "democratic people's republic of korea": "PRK", "iran": "IRN", "syria": "SYR",
    "venezuela": "VEN", "bolivia": "BOL", "tanzania": "TZA", "moldova": "MDA", "laos": "LAO", "vietnam": "VNM",
    "palestine": "PSE", "state of palestine": "PSE", "holy see": "VAT", "european union": "EU", "european community": "EU", "european council": "EU", "european commission": "EU",
    "micronesia": "FSM", "brunei": "BRN", "gambia": "GMB", "the gambia": "GMB", "sao tome and principe": "STP",
    "cote d'ivoire": "CIV", "timor-leste": "TLS", "east timor": "TLS", "democratic republic of timor-leste": "TLS",
    "eswatini": "SWZ", "czechia": "CZE", "turkiye": "TUR", "sao tome et principe": "STP", "somali republic": "SOM", "pope": "VAT",
    # formal names that do not end in the short name
    "french republic": "FRA", "argentine republic": "ARG", "italian republic": "ITA", "portuguese republic": "PRT",
    "hellenic republic": "GRC", "lebanese republic": "LBN", "gabonese republic": "GAB", "togolese republic": "TGO",
    "slovak republic": "SVK", "kyrgyz republic": "KGZ", "swiss confederation": "CHE", "grand duchy of luxembourg": "LUX",
    "federal republic of germany": "DEU", "people's republic of china": "CHN", "union of the comoros": "COM",
    "republic of the union of myanmar": "MMR", "lao people's democratic republic": "LAO",
    "united kingdom of great britain and northern ireland": "GBR", "kingdom of saudi arabia": "SAU",
}


def normalise(name: str) -> str:
    name = name.replace("’", "'").replace("`", "'")
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z' -]", " ", name)).strip()


@lru_cache(maxsize=1)
def _names() -> dict[str, str]:
    names = dict(ALIASES)
    with (REFERENCE_DIR / "delegations.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row["iso3"]:
                continue
            short = normalise(row["name"])
            names[short] = row["iso3"]
            # "Bolivia (Plurinational State of)" is written "the Plurinational State of Bolivia" in the records
            match = re.match(r"(.+?) \((.+?) of\)$", row["name"])
            if match:
                names[normalise(f"{match.group(2)} of {match.group(1)}")] = row["iso3"]
                names[normalise(match.group(1))] = row["iso3"]
    return names


def resolve(text: str) -> str | None:
    """Iso3 for the longest country name that ends the text, e.g. 'President of the Plurinational State of Bolivia'."""
    text = normalise(text)
    best = None
    for name, iso3 in _names().items():
        if text == name or text.endswith(" " + name):
            if best is None or len(name) > len(best[0]):
                best = (name, iso3)
    return best[1] if best else None


def find(text: str) -> str | None:
    """Iso3 for the longest country name anywhere in the text, e.g. a title that runs on past the country."""
    text = " " + normalise(text) + " "
    best = None
    for name, iso3 in _names().items():
        if f" {name} " in text and (best is None or len(name) > len(best[0])):
            best = (name, iso3)
    return best[1] if best else None
