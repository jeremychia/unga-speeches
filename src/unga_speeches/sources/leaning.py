"""Each outlet's political leaning, as rated by Media Bias/Fact Check, written into the outlet registry with the page it came from."""

import csv
import html
import json
import logging
import re
from collections import Counter
from pathlib import Path

from unga_speeches.config import RAW_DIR, REFERENCE_DIR
from unga_speeches.http import Client

log = logging.getLogger(__name__)

MBFC = "https://mediabiasfactcheck.com"
NOT_FOUND = "-"  # in the registry's mbfc_url column: looked for, and no rating page names the outlet's site
NOT_RATED = "Not rated"
# MBFC's bias values, mapped to the labels the page uses; its categories without a left-right position are left as not rated
LABELS = {
    "extreme left": "Left",
    "left": "Left",
    "left-center": "Left-centre",
    "least biased": "Centre",
    "center": "Centre",
    "right-center": "Right-centre",
    "right": "Right",
    "extreme right": "Right",
}
LEANINGS = ["Left", "Left-centre", "Centre", "Right-centre", "Right", NOT_RATED]
BIAS = re.compile(r'"name":"Bias Rating","value":"([^"]+)"')
FACTUAL = re.compile(r'"name":"Factual Reporting","value":"([^"]+)"')
SOURCE = re.compile(r'Source:\s*<a[^>]+href="https?://([^"/]+)', re.I)
LINK = re.compile(r'<a[^>]+href="https?://([^"/:]+)')
# sites every rating page links to, which are never the site rated
NOT_RATED_SITES = {"mediabiasfactcheck.com", "facebook.com", "twitter.com", "x.com", "youtube.com", "instagram.com", "linkedin.com",
                   "pinterest.com", "reddit.com", "google.com", "wikipedia.org", "archive.org", "archive.ph", "patreon.com", "wordpress.org",
                   "gravatar.com", "w.org", "ko-fi.com", "tumblr.com", "tiktok.com", "threads.net", "bsky.app", "paypal.com"}  # fmt: skip
# second-level labels under which sites register, so "abc.net.au" and "news.com.au" are told apart
SHARED_SUFFIXES = {"co", "com", "net", "org", "gov", "ac", "go"}
REGISTRY_FIELDS = ["mbfc_url", "mbfc_bias", "factual_reporting", "leaning", "state_media"]


def _site(domain: str) -> str:
    """The registrable part of a domain: "english.news.cn" gives "news.cn", "www.abc.net.au" gives "abc.net.au"."""
    labels = domain.lower().removeprefix("www.").split(".")
    keep = 3 if len(labels) >= 3 and labels[-2] in SHARED_SUFFIXES else 2
    return ".".join(labels[-keep:])


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower().replace("&", "and")).strip("-")


def _candidates(outlet: str, domain: str) -> list[str]:
    """Rating pages worth trying for an outlet, from its name and its site."""
    name = re.sub(r"\s*\((.*?)\)", r" \1", outlet)
    bases = {_slug(name), _slug(name.removeprefix("The ")), _slug(_site(domain).split(".")[0]), _slug(domain.removeprefix("www."))}
    return [f"{MBFC}/{b}{suffix}/" for b in sorted(bases) if b for suffix in ("", "-bias")]


def rating(client: Client, url: str) -> dict | None:
    """The bias and factual-reporting values of a rating page, and the site it rates."""
    name = _slug(url.removeprefix(MBFC).strip("/")) or "index"
    fetched = client.fetch(url, RAW_DIR / "mbfc" / f"{name}.html")
    if not fetched:
        return None
    text = fetched.path.read_text(encoding="utf-8", errors="replace")
    bias, factual, source = BIAS.search(text), FACTUAL.search(text), SOURCE.search(text)
    return {
        "url": url,
        "bias": html.unescape(bias.group(1)) if bias else "",
        "factual": html.unescape(factual.group(1)) if factual else "",
        "site": _site(source.group(1)) if source else _most_linked(text),
    }


def _most_linked(text: str) -> str:
    """The outside site a rating page links to most: older pages have no "Source:" line but cite the rated site throughout."""
    sites = Counter(_site(d) for d in LINK.findall(text))
    for skip in NOT_RATED_SITES:
        sites.pop(skip, None)
    return sites.most_common(1)[0][0] if sites else ""


def find(client: Client, outlet: str, domain: str) -> dict | None:
    """The first candidate page that rates the outlet's own site."""
    for url in _candidates(outlet, domain):
        found = rating(client, url)
        if found and found["site"] == _site(domain):
            return found
    return None


def build(session: int, client: Client | None = None) -> Path:
    """Fill each sampled outlet's leaning in reference/outlets.csv; a url already recorded there is used as it stands."""
    client = client or Client()
    path = REFERENCE_DIR / "outlets.csv"
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    with (REFERENCE_DIR / f"news_{session}.csv").open(encoding="utf-8") as f:
        state = {r["outlet"] for r in csv.DictReader(f) if r["kind"] == "state_media"}
    for r in rows:
        r["state_media"] = "yes" if r["outlet"] in state or "state news agency" in r["note"] or "state media" in r["note"] else "no"
        if r["status"] != "in_sample" or r["country"] in ("United Nations", "—"):
            r.update(mbfc_url=r.get("mbfc_url", ""), mbfc_bias="", factual_reporting="", leaning=r.get("leaning") or "")
            continue
        recorded = r.get("mbfc_url", "")
        found = None
        if recorded and recorded != NOT_FOUND:
            found = rating(client, recorded)
            if found and found["site"] != _site(r["domain"]):
                # recorded by hand, as for a page that names the outlet's other site; kept, but said
                log.warning("%s: %s rates %s, not %s", r["outlet"], recorded, found["site"], _site(r["domain"]))
        elif not recorded:
            found = find(client, r["outlet"], r["domain"])
        r["mbfc_url"] = found["url"] if found else NOT_FOUND
        r["mbfc_bias"] = found["bias"] if found else ""
        r["factual_reporting"] = found["factual"] if found else ""
        r["leaning"] = LABELS.get(r["mbfc_bias"].lower(), NOT_RATED)
        log.info("%s: %s", r["outlet"], r["leaning"] if found else "no rating page")
    fields = list(rows[0].keys())
    fields = [f for f in fields if f not in REGISTRY_FIELDS and f != "note"] + REGISTRY_FIELDS + ["note"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(json.dumps({"wrote": str(build(81))}))
