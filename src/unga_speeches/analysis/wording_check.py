"""The blind check of the war-wording rules: the passages a reader labels, and the rules scored against those labels.

The labels are in tests/fixtures/wording_blind_labels.csv, one row per speech and war, with the sample each came from:
  review      40 + 40 speeches labelled after the first version; used to find and fix errors, so its score flatters the rules.
  holdout     30 + 30 speeches drawn afterwards from speeches not yet labelled, seed 11.
  full 2026   every 2026 speech that names either war (81 Ukraine, 109 Gaza); used to fix the rules after it was scored.
  final       40 + 40 speeches from 2022-2025 drawn after the last fix from speeches never labelled, seed 23: the fair measure.
Each reader was a separate AI model that saw only the passages written by `passage`, never the rules or their output.

Gaza is read on two questions, scored apart: how hard a speech criticises Israel (`label`: genocide, conduct or no criticism), and
whether it blames Hamas or defends Israel (`israels_side`, labelled for the full 2026 and final samples, after that rule was written).
`human_sheet` writes 40 more unseen speeches for a person to label, so the rules can be checked by someone other than an AI model."""

import re
from pathlib import Path

import pandas as pd

from unga_speeches.analysis import wording

# the sentences a reader sees: those naming the war or its parties, with one sentence either side
TOPIC = {
    "ukraine": r"ukrain|kyiv|kiev|russia|putin|kremlin|moscow|crimea|donbas",
    "gaza": r"gaza|palestin|israel|hamas|west bank|hostage|netanyahu|october|zionis",
}
MENTIONS = {"ukraine": r"\bukrain|\bkyiv|\bkiev", "gaza": r"\bgaza|palestin|west bank"}
GENOCIDE, CONDUCT, BOTH, ISRAELS_SIDE, NEITHER, NO_GAZA = wording.GAZA_CLASSES
# the rules' gaza classes on the first question, criticism of israel, which is what the readers labelled
CRITICISM = {GENOCIDE: GENOCIDE, CONDUCT: CONDUCT, BOTH: CONDUCT, ISRAELS_SIDE: "no criticism of Israel", NEITHER: "no criticism of Israel"}
STRONG = {"ukraine": [wording.UKRAINE_CLASSES[0]], "gaza": [GENOCIDE, CONDUCT]}


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


def _row(sample: str, question: str, said: pd.Series, real: pd.Series, agree: pd.Series) -> dict:
    return {
        "sample": sample,
        "question": question,
        "speeches": len(agree),
        "agree": int(agree.sum()),
        "rules say yes, reader agrees": f"{int((said & real).sum())} of {int(said.sum())}",
        "reader says yes, rules catch": f"{int((said & real).sum())} of {int(real.sum())}",
    }


def score(labels: pd.DataFrame, classified: pd.DataFrame) -> pd.DataFrame:
    """Agreement between each sample's blind labels and the rules, and for each question how often the rules' yes is right (precision)
    and how many of the reader's yes the rules catch (recall)."""
    rows = []
    for (sample, war), d in labels.groupby(["sample", "war"], sort=False):
        side_read = war == "gaza" and "israels_side" in d.columns and d["israels_side"].notna().any()
        cols = ["year", "iso3", war] + (["israels_side"] if side_read else [])
        d = d.merge(classified[cols], on=["year", "iso3"], suffixes=("_reader", ""))
        rules = d[war].map(CRITICISM) if war == "gaza" else d[war]
        question = "blames Russia" if war == "ukraine" else "criticises Israel"
        rows.append(_row(sample, question, rules.isin(STRONG[war]), d.label.isin(STRONG[war]), rules == d.label))
        if side_read:
            s = d[d["israels_side_reader"].notna()]
            said, real = s["israels_side"].astype(bool), s["israels_side_reader"].astype(bool)
            rows.append(_row(sample, "blames Hamas or defends Israel", said, real, said == real))
    return pd.DataFrame(rows)


def human_sheet(speeches: pd.DataFrame, labelled: pd.DataFrame, out_dir: Path, n: int = 20, seed: int = 31) -> pd.DataFrame:
    """n unseen speeches per war for a person to label, as a page of passages and an empty label sheet in out_dir."""
    rows, text = [], ["# Human check of the war-wording rules", ""]
    text.append(
        "Label each passage from the text alone, without looking at the rules or the published labels. Write your labels in `labels.csv`."
    )
    text += ["", "**Ukraine**: B = blames Russia or calls it aggression · R = uses Russia's framing · N = names Ukraine but blames no one.",
             "**Gaza, question 1**: G = calls it genocide · C = criticises Israel's conduct · N = no criticism of Israel.",
             "**Gaza, question 2**: S = blames Hamas or defends Israel · N = does not.", ""]  # fmt: skip
    for war, years in [("ukraine", [2022, 2023, 2024, 2025, 2026]), ("gaza", [2024, 2025, 2026])]:
        d = draw(speeches, war, years, n, seed, labelled)
        for k, r in d.iterrows():
            key = f"{war[0].upper()}{k}"
            text += [f"## {key} · {r.delegation}, {r.year}", "", "```", passage(r.english_text_clean, war), "```", ""]
            rows.append(
                {"id": key, "war": war, "year": r.year, "iso3": r.iso3, "delegation": r.delegation, "label": "", "israels_side": ""}
            )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "passages.md").write_text("\n".join(text), encoding="utf-8")
    sheet = pd.DataFrame(rows)
    sheet.to_csv(out_dir / "labels.csv", index=False)
    return sheet


def read_human(path: Path) -> pd.DataFrame:
    """The filled-in human sheet as labels `score` can use, in a sample called "human"; rows not yet labelled are left out."""
    sheet = pd.read_csv(path, dtype=str).fillna("")
    sheet = sheet[sheet.label.str.strip() != ""]
    codes = {
        "ukraine": {"B": wording.UKRAINE_CLASSES[0], "R": wording.UKRAINE_CLASSES[2], "N": wording.UKRAINE_CLASSES[1]},
        "gaza": {"G": GENOCIDE, "C": CONDUCT, "N": "no criticism of Israel"},
    }
    sheet["label"] = [codes[w][x.strip().upper()] for w, x in zip(sheet.war, sheet.label, strict=True)]
    sheet["israels_side"] = sheet.israels_side.str.strip().str.upper().map({"S": True, "N": False})
    return sheet.assign(sample="human", year=sheet.year.astype(int))[
        ["sample", "war", "year", "iso3", "delegation", "label", "israels_side"]
    ]
