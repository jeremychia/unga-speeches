"""Texts published by a delegation's own government, listed by hand in data/reference/manual_sources.csv."""

import csv
import hashlib
import re
from pathlib import Path

from bs4 import BeautifulSoup

from .config import RAW_DIR, REFERENCE_DIR
from .http import Client
from .model import TextVersion

BLOCKS = ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote"]


def load(session: int, slug: str) -> list[dict]:
    path = REFERENCE_DIR / "manual_sources.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if int(r["session"]) == session and r["slug"] == slug]


def html_text(html: str, selector: str) -> str:
    root = BeautifulSoup(html, "lxml").select_one(selector)
    if root is None:
        raise ValueError(f"selector {selector!r} matched nothing")
    blocks = [b for b in root.find_all(BLOCKS) if not b.find_parent(BLOCKS)]
    parts = [re.sub(r"[ \t\r\f\v]+", " ", b.get_text(" ", strip=True)) for b in blocks] if blocks else [root.get_text("\n", strip=True)]
    return "\n\n".join(p for p in parts if p)


def fetch(client: Client, session: int, slug: str, source: dict) -> TextVersion | None:
    name = hashlib.sha1(source["url"].encode()).hexdigest()[:12]
    fetched = client.fetch(source["url"], RAW_DIR / "national" / str(session) / slug / f"{name}.html")
    if not fetched:
        return None
    text = html_text(fetched.path.read_text(encoding="utf-8", errors="replace"), source["css_selector"])
    return TextVersion(
        kind="national_source",
        language=source["language"],
        source_url=fetched.url,
        retrieved_at=fetched.retrieved_at,
        sha256=fetched.sha256,
        method="html",
        text=text,
        warnings=["published by the delegation's government; web pages can change after publication, so check the retrieval date and checksum"],
    )
