"""The speeches of one session, with the best English text for each and the metadata the analysis groups by."""

import csv
import json
from dataclasses import dataclass

from unga_speeches.config import OUTPUT_DIR, REFERENCE_DIR
from unga_speeches.extract.clean import clean

# the delegation's own english first; a ministry page last, since it can wrap the speech in a press summary
ENGLISH_PREFERENCE = {"statement": 0, "transcript": 1, "national_source": 2}


@dataclass
class Speech:
    slug: str
    delegation: str
    iso3: str
    region: str
    status: str
    speaker: str
    title: str
    role: str
    role_group: str
    date: str
    original_language: str
    english_kind: str  # statement, national_source or transcript
    english_url: str
    page_url: str
    delivered_share: float | None
    text: str  # cleaned, for counting
    verbatim: str  # the source text with whitespace collapsed, for quoting

    @property
    def words(self) -> int:
        return len(self.text.split())


def load(session: int) -> list[Speech]:
    with (REFERENCE_DIR / "delegations.csv").open(encoding="utf-8") as f:
        delegations = {row["slug"]: row for row in csv.DictReader(f) if row["slug"]}
    texts: dict[str, list[dict]] = {}
    with (OUTPUT_DIR / f"texts_{session}.jsonl").open(encoding="utf-8") as f:
        for line in f:
            t = json.loads(line)
            if t["language"] == "en" and t["text"]:
                texts.setdefault(t["slug"], []).append(t)

    speeches = []
    with (OUTPUT_DIR / f"speeches_{session}.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            english = sorted(texts.get(row["slug"], []), key=lambda t: ENGLISH_PREFERENCE[t["kind"]])
            if not english:
                continue
            best = english[0]
            delegation = delegations.get(row["slug"], {})
            speeches.append(
                Speech(
                    slug=row["slug"],
                    delegation=row["delegation"],
                    iso3=row["iso3"],
                    region=delegation.get("m49_region") or ("UN" if row["status"] == "un_official" else "Other"),
                    status=row["status"],
                    speaker=row["speaker_name"],
                    title=row["speaker_title"],
                    role=row["role"],
                    role_group=row["role_group"],
                    date=row["date"],
                    original_language=row["original_language"],
                    english_kind=best["kind"],
                    english_url=best["source_url"],
                    page_url=row["page_url"],
                    delivered_share=float(row["delivered_share"]) if row["delivered_share"] else None,
                    text=clean(best["text"], best["kind"]),
                    verbatim=" ".join(best["text"].split()),
                )
            )
    return speeches
