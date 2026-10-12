"""The blind check of the war-wording rules: the passages a reader labels, and the rules scored against those labels.

The labels are in tests/fixtures/wording_blind_labels.csv, one row per speech and war, with the sample each came from:
  review      40 + 40 speeches labelled after the first version; used to find and fix errors, so its score flatters the rules.
  holdout     30 + 30 speeches drawn afterwards from speeches not yet labelled, seed 11.
  full 2026   every 2026 speech that names either war (81 Ukraine, 109 Gaza); used to fix the rules after it was scored.
  final       40 + 40 speeches from 2022-2025 drawn after the last fix from speeches never labelled, seed 23: the fair measure.
Each reader was a separate AI model that saw only the passages written by `passages`, never the rules or their output."""

import re

import pandas as pd

from unga_speeches.analysis import wording

# the sentences a reader sees: those naming the war or its parties, with one sentence either side
TOPIC = {
    "ukraine": r"ukrain|kyiv|kiev|russia|putin|kremlin|moscow|crimea|donbas",
    "gaza": r"gaza|palestin|israel|hamas|west bank|hostage|netanyahu|october|zionis",
}
MENTIONS = {"ukraine": r"\bukrain|\bkyiv|\bkiev", "gaza": r"\bgaza|palestin|west bank"}
STRONG = {"ukraine": [wording.UKRAINE_CLASSES[0]], "gaza": wording.GAZA_CLASSES[:2]}


def passage(text: str, war: str) -> str:
    """The extract a blind reader labels: each sentence on the topic marked ">>", its neighbours, and "..." where sentences are skipped."""
    sents = wording._sentences(text)
    idx = [i for i, s in enumerate(sents) if re.search(TOPIC[war], s, re.I)]
    out, prev = [], -2
    for j in wording._around_index(sents, idx):
        if j != prev + 1:
            out.append("  ...")
        out.append(("  >> " if j in idx else "     ") + " ".join(sents[j].split()))
        prev = j
    return "\n".join(out)


def draw(speeches: pd.DataFrame, war: str, years: list[int], n: int, seed: int, labelled: pd.DataFrame) -> pd.DataFrame:
    """n speeches from these years that name the war and have not been labelled before, drawn with a fixed seed."""
    seen = set(map(tuple, labelled.loc[labelled.war == war, ["year", "iso3"]].values))
    pool = speeches[speeches.year.isin(years) & speeches.english_text_clean.str.contains(MENTIONS[war], case=False, regex=True)]
    pool = pool[[(y, i) not in seen for y, i in zip(pool.year, pool.iso3, strict=True)]]
    return pool.sample(n, random_state=seed).reset_index(drop=True)


def score(labels: pd.DataFrame, classified: pd.DataFrame) -> pd.DataFrame:
    """Agreement between each sample's blind labels and the rules, and for the strong framings the share of the rules' calls the reader
    shares (precision) and the share of the reader's calls the rules catch (recall)."""
    rows = []
    for (sample, war), d in labels.groupby(["sample", "war"], sort=False):
        d = d.merge(classified[["year", "iso3", war]], on=["year", "iso3"])
        said, real = d[war].isin(STRONG[war]), d.label.isin(STRONG[war])
        rows.append(
            {
                "sample": sample,
                "war": war,
                "speeches": len(d),
                "agree": int((d[war] == d.label).sum()),
                "strong, rules right": f"{int((said & real).sum())} of {int(said.sum())}",
                "strong, rules caught": f"{int((said & real).sum())} of {int(real.sum())}",
            }
        )
    return pd.DataFrame(rows)
