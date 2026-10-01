"""The same measures for every debate from 1946, so any year can be set against another."""

import csv
import hashlib
import json
import statistics
from collections import Counter

import pandas as pd

from unga_speeches.analysis import lexicons, mentions
from unga_speeches.config import OUTPUT_DIR, REFERENCE_DIR

REGIONS = ["Africa", "Americas", "Asia", "Europe", "Oceania"]
# states that no longer exist, by the region of their territory
FORMER_STATES = {"CSK": "Europe", "DDR": "Europe", "YUG": "Europe", "SCG": "Europe", "YMD": "Asia", "SUN": "Europe"}
TOP_NAMED = 10
KNOWN_RANK_SHARE = 0.5  # the share of leaders is reported only when at least this share of speakers' ranks is known


def _regions() -> dict[str, str]:
    with (REFERENCE_DIR / "delegations.csv").open(encoding="utf-8") as f:
        return {r["iso3"]: r["m49_region"] for r in csv.DictReader(f) if r["iso3"] and r["m49_region"]} | FORMER_STATES


def build() -> list[dict]:
    """One summary per debate: who spoke and at what rank, the issues raised, the states named, and each region's theory vocabulary."""
    frame = pd.read_parquet(OUTPUT_DIR / "speeches.parquet", columns=["session", "year", "iso3", "role_group", "english_text_clean"])
    frame = frame[frame.english_text_clean.notna() & (frame.english_text_clean.str.len() > 0)]
    region = _regions()
    out = []
    for (session, year), group in frame.groupby(["session", "year"]):
        texts = list(zip(group.iso3, group.english_text_clean, strict=True))
        states = group[group.iso3.isin(region)]
        issues = Counter()
        named, times = Counter(), Counter()
        taiwan = []
        frames: dict[str, list[dict]] = {r: [] for r in REGIONS}
        for iso3, text in texts:
            issues.update(k for k, hit in lexicons.issues(text).items() if hit)
            counts = mentions.named(text)
            counts.pop(iso3, None)
            named.update(counts.keys())
            times.update(counts)
            if counts.get("TWN"):
                taiwan.append(iso3)
            if region.get(iso3) in frames:
                frames[region[iso3]].append(lexicons.frame_rates(text))
        n = len(texts)
        out.append(
            {
                "session": int(session),
                "year": int(year),
                "speeches": n,
                "heads_share": round(float((states.role_group == "head_of_state_or_government").mean()), 3)
                if len(states) and (states.role_group != "unclassified").mean() >= KNOWN_RANK_SHARE
                else None,
                "words_median": int(statistics.median(len(t.split()) for _, t in texts)),
                "issues": {k: round(issues[k] / n, 3) for k in lexicons.ISSUES},
                "named": [{"iso3": c, "speeches": named[c], "times": times[c]} for c, _ in named.most_common(TOP_NAMED)],
                "taiwan": sorted(taiwan),
                "frames": {
                    r: {f: round(statistics.fmean(x[f] for x in rows), 2) for f in lexicons.FRAMES} for r, rows in frames.items() if rows
                },
            }
        )
    return out


def load() -> list[dict]:
    """build(), cached against a fingerprint of the dataset, since reading every speech since 1946 takes a few minutes."""
    source = OUTPUT_DIR / "speeches.parquet"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    cache = OUTPUT_DIR / "years.json"
    if cache.exists():
        saved = json.loads(cache.read_text(encoding="utf-8"))
        if saved.get("dataset_sha256") == digest:
            return saved["years"]
    years = build()
    cache.write_text(json.dumps({"dataset_sha256": digest, "years": years}, ensure_ascii=False), encoding="utf-8")
    return years
