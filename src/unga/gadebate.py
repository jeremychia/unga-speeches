"""Discover, download and parse speaker pages on gadebate.un.org, the UN's general debate site (sessions 64 onwards)."""

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from .config import GADEBATE_BASE, RAW_DIR, UN_LANGUAGES
from .http import Client

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
SPEAKER_URL = re.compile(rf"^{re.escape(GADEBATE_BASE)}/en/(\d+)/([a-z0-9-]+)$")

# the site labels each statement pdf by the language it is written in
STATEMENT_FIELD_LANGUAGE = {
    "arabic": "ar",
    "chinese": "zh",
    "english": "en",
    "french": "fr",
    "russian": "ru",
    "spanish": "es",
}
# file suffixes seen on "Statement, other" that name a language; "fl" (floor version) does not
FILE_SUFFIX_LANGUAGE = {"bd": "bn", "cs": "cs", "lv": "lv", "pt": "pt", "ua": "uk", "fr": "fr", "en": "en", "es": "es"}


@dataclass
class Statement:
    label: str
    language: str | None
    url: str
    floor_version: bool = False  # the "_fl" file: the text as delivered from the floor


@dataclass
class SpeakerPage:
    session: int
    slug: str
    url: str
    node_id: str | None
    delegation: str
    honorific: str | None
    speaker_name: str | None
    speaker_title: str | None
    date: str | None
    statements: list[Statement] = field(default_factory=list)
    has_video: bool = False
    has_transcript: bool = False
    daily_summary_url: str | None = None


def discover(client: Client, sessions: set[int] | None = None, force: bool = False) -> list[tuple[int, str, str]]:
    """Return (session, slug, lastmod) for every English speaker page in the sitemap."""
    index = client.fetch(f"{GADEBATE_BASE}/sitemap.xml", RAW_DIR / "gadebate" / "sitemap" / "index.xml", force=force)
    pages = [loc.text for loc in ElementTree.parse(index.path).getroot().findall("sm:sitemap/sm:loc", SITEMAP_NS)]
    found = {}
    for i, page_url in enumerate(pages, start=1):
        page = client.fetch(page_url, RAW_DIR / "gadebate" / "sitemap" / f"page_{i}.xml", force=force)
        found.update(parse_sitemap(page.path.read_bytes(), sessions))
    return sorted((s, slug, lastmod) for (s, slug), lastmod in found.items())


def parse_sitemap(xml: bytes, sessions: set[int] | None = None) -> dict[tuple[int, str], str]:
    found = {}
    for url in ElementTree.fromstring(xml).findall("sm:url", SITEMAP_NS):
        match = SPEAKER_URL.match(url.findtext("sm:loc", default="", namespaces=SITEMAP_NS))
        if not match:
            continue
        session, slug = int(match.group(1)), match.group(2)
        if sessions is None or session in sessions:
            found[(session, slug)] = url.findtext("sm:lastmod", default="", namespaces=SITEMAP_NS)
    return found


def page_path(session: int, slug: str) -> Path:
    return RAW_DIR / "gadebate" / str(session) / slug / "page.en.html"


def fetch_page(client: Client, session: int, slug: str, attempts: int = 4, force: bool = False) -> Path | None:
    """None when the page is listed but not yet published, which the site signals by redirecting to its home page.

    The site also redirects published pages now and then, so only a redirect on every attempt counts.
    """
    for attempt in range(attempts):
        fetched = client.fetch(f"{GADEBATE_BASE}/en/{session}/{slug}", page_path(session, slug), follow_redirects=False, force=force)
        if fetched:
            return fetched.path
        time.sleep(2 * (attempt + 1))
    return None


def _field_text(soup: BeautifulSoup, name: str) -> str | None:
    node = soup.select_one(f".field--name-field-{name}")
    return node.get_text(" ", strip=True) if node else None


def parse_page(html: str, session: int, slug: str) -> SpeakerPage:
    soup = BeautifulSoup(html, "lxml")
    shortlink = soup.find("link", rel="shortlink")
    node_id = shortlink["href"].rsplit("/", 1)[-1] if shortlink else None
    title = soup.title.get_text(strip=True) if soup.title else slug
    time_tag = soup.select_one(".field--name-field-release-date time")

    statements = []
    for block in soup.select('[class*="field--name-field-"][class*="-statement"]'):
        link = block.select_one("a[href$='.pdf']")
        if not link:
            continue
        field_name = next(c for c in block["class"] if c.startswith("field--name-field-"))
        kind = field_name.removeprefix("field--name-field-").removesuffix("-statement")
        # "Statement, other" is named by a suffix that is only sometimes a language code (br_pt, ua_ua, kh_fl), so pdftext detects it
        suffix = re.search(r"_([a-z]{2,4})(?:_\d+)?\.pdf$", link["href"])
        language = STATEMENT_FIELD_LANGUAGE.get(kind) or FILE_SUFFIX_LANGUAGE.get(suffix.group(1) if suffix else "")
        label_node = block.select_one(".custom-statement-file-label")
        statements.append(
            Statement(
                label=label_node.get_text(strip=True) if label_node else kind,
                language=language,
                url=GADEBATE_BASE + link["href"] if link["href"].startswith("/") else link["href"],
                floor_version=bool(suffix and suffix.group(1) == "fl"),
            )
        )

    summary = soup.find("a", string=re.compile("Daily summary"))
    return SpeakerPage(
        session=session,
        slug=slug,
        url=f"{GADEBATE_BASE}/en/{session}/{slug}",
        node_id=node_id,
        delegation=title.split("|")[0].strip(),
        honorific=_field_text(soup, "speaker-title"),
        speaker_name=_field_text(soup, "speaker-name"),
        speaker_title=_field_text(soup, "speaker-function-2"),
        date=time_tag["datetime"][:10] if time_tag else None,
        statements=statements,
        has_video=soup.select_one("[data-entryid]") is not None,
        has_transcript=soup.select_one("[data-un-gad-transcript-download]") is not None,
        daily_summary_url=summary["href"] if summary else None,
    )


def statement_path(session: int, slug: str, url: str) -> Path:
    return RAW_DIR / "gadebate" / str(session) / slug / "statements" / url.rsplit("/", 1)[-1]


def fetch_statement(client: Client, page: SpeakerPage, statement: Statement):
    return client.fetch(statement.url, statement_path(page.session, page.slug, statement.url))


def transcript_path(session: int, slug: str, language: str) -> Path:
    return RAW_DIR / "gadebate" / str(session) / slug / "transcripts" / f"{language}.txt"


def fetch_transcript(client: Client, page: SpeakerPage, language: str):
    """Download the site's AI transcript of one audio channel; the download link is signed, so the page is the provenance."""
    if language not in UN_LANGUAGES or not page.node_id:
        return None
    dest = transcript_path(page.session, page.slug, language)
    if client.is_cached(dest):
        return client.fetch("", dest)
    prepare = client.request("POST", f"{GADEBATE_BASE}/en/node/{page.node_id}/transcript/{language}/prepare-download")
    if prepare.status_code != 200 or "json" not in prepare.headers.get("content-type", ""):
        return None
    signed = GADEBATE_BASE + prepare.json()["url"]
    return client.fetch(signed, dest, source_url=f"{GADEBATE_BASE}/{language}/{page.session}/{page.slug}")
