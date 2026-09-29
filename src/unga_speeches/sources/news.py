"""News coverage of a session, listed by hand in reference/news_<session>.csv: downloaded, cached and cut to its paragraphs."""

import csv
import hashlib
import json
import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup

from unga_speeches.config import GADEBATE_BASE, OUTPUT_DIR, RAW_DIR, REFERENCE_DIR
from unga_speeches.http import Client
from unga_speeches.sources import gadebate

log = logging.getLogger(__name__)

MIN_PARAGRAPH_CHARS = 60  # shorter blocks are captions, bylines and buttons
FURNITURE_CHARS = 1000  # a nav, header, footer or aside with less paragraph text than this is page furniture
# boilerplate that sits in paragraph tags on news sites
NOISE = re.compile(
    r"^(sign up|subscribe|advertisement|related:|read more|watch:|copyright|©|this story has been|follow us|share this|get full access|join |copy url"
    r"|everything ms now|ms now’s|the rachel maddow|the blueprint|don't miss)",
    re.I,
)


def sources(session: int) -> list[dict]:
    path = REFERENCE_DIR / f"news_{session}.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def extract(html: str) -> tuple[str, list[str]]:
    """The article's title and its body paragraphs, in order, without repeats."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "figcaption", "form"]):
        tag.decompose()
    # some sites wrap the whole page in a nav or header, so only furniture without story text goes
    for tag in soup(["nav", "header", "footer", "aside"]):
        if not tag.decomposed and _paragraph_chars(tag) < FURNITURE_CHARS:
            tag.decompose()
    title_tag = soup.find("meta", property="og:title") or soup.find("title")
    title = (title_tag.get("content") if title_tag.name == "meta" else title_tag.get_text()) if title_tag else ""
    root = _story_container(soup)
    seen, paragraphs = set(), []
    for p in root.find_all(["p", "li"]):
        text = " ".join(p.get_text(" ", strip=True).split())
        if len(text) < MIN_PARAGRAPH_CHARS or NOISE.search(text) or text in seen:
            continue
        seen.add(text)
        paragraphs.append(text)
    return " ".join(title.split()), paragraphs


def _paragraph_chars(node) -> int:
    return sum(len(t) for p in node.find_all("p") if len(t := p.get_text(" ", strip=True)) >= MIN_PARAGRAPH_CHARS)


def _story_container(soup: BeautifulSoup):
    """The article or main element holding the most paragraph text; the first article tag is often a teaser, not the story."""
    body = soup.body or soup
    candidates = soup.find_all(["article", "main"])
    best = max(candidates, key=_paragraph_chars, default=None)
    # when no container holds most of the page's text, the story sits outside them
    if best is None or _paragraph_chars(best) < 0.5 * _paragraph_chars(body):
        return body
    return best


def build(session: int, client: Client | None = None) -> Path:
    client = client or Client()
    out = OUTPUT_DIR / f"news_{session}.jsonl"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for source in sources(session):
            name = hashlib.sha1(source["url"].encode()).hexdigest()[:12]
            fetched = client.fetch(source["url"], RAW_DIR / "news" / str(session) / f"{name}.html")
            if not fetched:
                log.warning("%s: not found", source["url"])
                continue
            title, paragraphs = extract(fetched.path.read_text(encoding="utf-8", errors="replace"))
            words = sum(len(p.split()) for p in paragraphs)
            log.info("%s %s: %d paragraphs, %d words", source["outlet"], source["date"], len(paragraphs), words)
            record = {
                **source,
                "title": title,
                "paragraphs": paragraphs,
                "words": words,
                "retrieved_at": fetched.retrieved_at,
                "sha256": fetched.sha256,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return out


def _text(node) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


def page_coverage(html: str) -> dict:
    """What a speaker's debate page says about them beyond the speech: the UN press office's headline and summary, and UN News stories."""
    soup = BeautifulSoup(html, "lxml")
    summary = soup.select_one(".field--name-field-no-summary-text")
    headline = summary.find("h4") if summary else None
    paragraphs = [t for p in summary.find_all("p") if (t := _text(p))] if summary else []
    daily = soup.find("a", string=re.compile("Daily summary"))
    news_links = soup.select(".field--name-field-news-text a[href]")
    return {
        "honorific": _text(soup.select_one(".field--name-field-speaker-title")),
        "headline": _text(headline),
        "summary": paragraphs,
        "summary_words": sum(len(p.split()) for p in paragraphs),
        "press_release_url": daily["href"] if daily else None,
        "un_news": [{"language": _text(a), "url": a["href"]} for a in news_links if "news.un.org" in a["href"]],
    }


def coverage(session: int) -> Path:
    """page_coverage for every speaker whose debate page is cached, written to data/output/coverage_<session>.jsonl."""
    out = OUTPUT_DIR / f"coverage_{session}.jsonl"
    with (OUTPUT_DIR / f"speeches_{session}.csv").open(encoding="utf-8") as f:
        slugs = [row["slug"] for row in csv.DictReader(f)]
    with out.open("w", encoding="utf-8") as f:
        for slug in slugs:
            path = gadebate.page_path(session, slug)
            if not path.exists():
                continue
            record = {"slug": slug, "page_url": f"{GADEBATE_BASE}/en/{session}/{slug}", **page_coverage(path.read_text(encoding="utf-8"))}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    log.info("coverage for %d of %d speakers", sum(1 for _ in out.open()), len(slugs))
    return out
