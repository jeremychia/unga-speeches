"""Combine the three sources into one table: a row per delegation per session, 1946 onwards.

Each field comes from the most authoritative source that has it, and names that source.
"""

import csv
import json
import logging
import re
from pathlib import Path

import pandas as pd

from unga_speeches.build.report import write_sources_report
from unga_speeches.config import OUTPUT_DIR, REFERENCE_DIR, session_year
from unga_speeches.enrich import roles
from unga_speeches.extract.clean import clean
from unga_speeches.sources.ungdc import DATASET_URL

log = logging.getLogger(__name__)

# how the corpus made its english text changed in its last two sessions (see its README)
UNGDC_ENGLISH_BASIS = {79: "ungdc_machine_translation", 80: "ungdc_whisper_transcript"}
SCAN_MATCH = 0.5  # share of five-word runs a scanned speech must share with the corpus's text to count as the same speech
UN_OFFICIAL_CODES = {
    "secretary-general-united-nations": "UN-SG",
    "president-general-assembly-opening": "UN-PGA",
    "president-general-assembly-closing": "UN-PGA-CLOSING",
}
HONORIFIC = re.compile(
    r"^(His|Her|Their)( Royal| Serene| Majesty| Highness| Excellency| Eminence| Beatitude)*\s+|^(Mr|Mrs|Ms|Miss|Dr|Sir|Dame)\.?\s+"
)


def _delegations() -> tuple[dict[str, str], dict[str, str]]:
    """(slug -> code, code -> name) for every delegation, with codes for the EU and UN officials."""
    slug_code, names = {}, {}
    with (REFERENCE_DIR / "delegations.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = row["iso3"] or ("EU" if row["slug"] == "european-union" else UN_OFFICIAL_CODES.get(row["slug"]))
            if row["slug"] and code:
                slug_code[row["slug"]] = code
            if code:
                names.setdefault(code, row["name"])
    return slug_code, names


def _corpus() -> pd.DataFrame:
    path = OUTPUT_DIR / "history_ungdc.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame(columns=["iso3", "session", "year", "text_en"])


def _verbatim() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = [json.loads(line) for p in sorted(OUTPUT_DIR.glob("verbatim_*.jsonl")) for line in p.open(encoding="utf-8")]
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame, frame
    frame.loc[frame.iso3.isna() & frame.label.str.contains("Secretary-General", na=False), "iso3"] = "UN-SG"
    debate = frame[(frame.kind == "general_debate") & frame.iso3.notna()].drop_duplicates(["session", "iso3"])
    return debate, frame[frame.kind == "right_of_reply"]


def _scanned() -> pd.DataFrame:
    """The general debate speeches read from the UN's scanned records, 1946 to 1992."""
    rows = [json.loads(line) for p in sorted(OUTPUT_DIR.glob("scanned_*.jsonl")) for line in p.open(encoding="utf-8")]
    frame = pd.DataFrame(rows)
    return frame[frame.iso3.notna()].drop_duplicates(["session", "iso3"]) if not frame.empty else frame


def _gadebate(slug_code: dict[str, str]) -> tuple[pd.DataFrame, dict]:
    speeches, texts = [], {}
    for path in sorted(OUTPUT_DIR.glob("speeches_*.csv")):
        speeches.append(pd.read_csv(path, dtype=str, keep_default_na=False))
    for path in sorted(OUTPUT_DIR.glob("texts_*.jsonl")):
        for line in path.open(encoding="utf-8"):
            t = json.loads(line)
            texts.setdefault((int(t["session"]), t["slug"]), []).append(t)
    frame = pd.concat(speeches) if speeches else pd.DataFrame()
    if not frame.empty:
        frame["session"] = frame["session"].astype(int)
        frame["iso3"] = frame["slug"].map(slug_code)
    return frame, texts


def _shingles(text: str, n: int = 5) -> set:
    words = re.findall(r"\w+", text.lower())
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def agreement(a: str, b: str) -> float | None:
    """Share of the shorter text's five-word runs found in the other; 1.0 means one text contains the other."""
    x, y = _shingles(a or ""), _shingles(b or "")
    if not x or not y:
        return None
    return round(len(x & y) / min(len(x), len(y)), 3)


def _text(value) -> str | None:
    """A field's value when it is text; pandas gives a missing one as NaN, which is truthy."""
    return value if isinstance(value, str) and value else None


def _index(frame: pd.DataFrame) -> dict:
    return {(int(r["session"]), r["iso3"]): r for r in frame.to_dict("records")} if not frame.empty else {}


def _best_original(candidates: list[dict], language: str | None) -> dict | None:
    kinds = {"statement": 0, "national_source": 1, "transcript": 2}
    usable = [t for t in candidates if t.get("text") and t.get("language") == language]
    usable.sort(key=lambda t: (not t.get("floor_version"), kinds.get(t["kind"], 9)))
    return usable[0] if usable else None


def build() -> Path:
    slug_code, names = _delegations()
    corpus, (records, replies), (site, site_texts) = _corpus(), _verbatim(), _gadebate(slug_code)
    scans = _scanned()

    keys = set()
    for frame in (corpus, records, site, scans):
        if not frame.empty:
            keys |= {(int(s), c) for s, c in zip(frame["session"], frame["iso3"], strict=True) if isinstance(c, str)}
    by_corpus, by_record, by_site = (
        _index(corpus[corpus.iso3.notna()]),
        _index(records),
        _index(site[site.iso3.notna()] if not site.empty else site),
    )
    by_scan = _index(scans)

    rows = []
    for session, code in sorted(keys):
        c, v, g = by_corpus.get((session, code)), by_record.get((session, code)), by_site.get((session, code))
        # a scanned record plays the part of the born-digital record before 1993, except where the corpus's cleaned text exists;
        # it is kept only when it is the same speech as the corpus's, or the corpus has none
        s = by_scan.get((session, code))
        if s and c is not None and isinstance(c.get("text_en"), str) and (agreement(s["text"], c["text_en"]) or 0) < SCAN_MATCH:
            s = None
        row = {
            "session": session,
            "year": session_year(session),
            "iso3": code,
            "delegation": names.get(code) or (c or {}).get("country") or code,
        }

        if g:
            row.update(speaker_name=g["speaker_name"], speaker_title=g["speaker_title"], speaker_source="gadebate")
        elif c is not None and isinstance(c.get("speaker_name"), str):
            row.update(
                speaker_name=c["speaker_name"],
                speaker_title=c.get("speaker_title") if isinstance(c.get("speaker_title"), str) else None,
                speaker_source="ungdc",
            )
        elif v:
            row.update(
                speaker_name=HONORIFIC.sub("", _text(v["heading_speaker"]) or v["label"]),
                speaker_title=_text(v["heading_title"]),
                speaker_source="un_verbatim_record",
            )
        elif s:
            row.update(
                speaker_name=HONORIFIC.sub("", _text(s["heading_speaker"]) or s["label"].split("(")[0]).strip(" :"),
                speaker_title=_text(s["heading_title"]),
                speaker_source="un_scanned_record",
            )
        row["role"] = roles.classify(row.get("speaker_title"), g["slug"] if g else ("holy-see" if code == "VAT" else None))
        row["role_group"] = roles.ROLE_GROUP[row["role"]]

        if v:
            row.update(
                spoken_language=v["spoken_language"],
                spoken_language_source="un_verbatim_record",
                interpretation_note=v["interpretation_note"],
            )
        elif g and g["original_language"]:
            row.update(spoken_language=g["original_language"], spoken_language_source="gadebate_statement_language")
        elif s and isinstance(s["spoken_language"], str):
            row.update(
                spoken_language=s["spoken_language"],
                spoken_language_source="un_scanned_record",
                interpretation_note=s["spoken_language_note"],
            )

        if v:
            row.update(english_text=v["text"], english_source="un_verbatim_record", english_url=v["meeting_url"], english_kind="verbatim")
        elif c is not None and isinstance(c.get("text_en"), str):
            row.update(
                english_text=c["text_en"],
                english_source=UNGDC_ENGLISH_BASIS.get(session, "ungdc_verbatim_record"),
                english_url=DATASET_URL,
                english_kind="verbatim",
            )
        elif s:
            row.update(english_text=s["text"], english_source="un_scanned_record", english_url=s["meeting_url"], english_kind="verbatim")
        elif g:
            english = [t for t in site_texts.get((session, g["slug"]), []) if t["language"] == "en" and t["text"]]
            english.sort(key=lambda t: t["kind"] == "transcript")
            if english:
                row.update(
                    english_text=english[0]["text"],
                    english_source=f"gadebate_{english[0]['kind']}",
                    english_url=english[0]["source_url"],
                    english_kind=english[0]["kind"],
                )

        spoken = row.get("spoken_language")
        original = _best_original(site_texts.get((session, g["slug"]), []), spoken) if g else None
        if original:
            row.update(
                original_language=spoken,
                original_text=original["text"],
                original_source=f"gadebate_{original['kind']}",
                original_url=original["source_url"],
                original_kind=original["kind"],
            )
        elif spoken == "en" and row.get("english_text"):
            row.update(
                original_language="en",
                original_text=row["english_text"],
                original_source=row["english_source"],
                original_url=row["english_url"],
                original_kind=row["english_kind"],
            )
        elif spoken:
            row["original_language"] = spoken

        row["english_text_clean"] = clean(row.get("english_text") or "", row.get("english_kind") or "")
        row["original_text_clean"] = clean(row.get("original_text") or "", row.get("original_kind") or "")
        row["gadebate_page"] = g["page_url"] if g else None
        row["verbatim_meeting"] = v["meeting"] if v else (s["meeting"] if s else None)
        row["record_url"] = v["meeting_url"] if v else (s["meeting_url"] if s else None)
        row["record_ocr_quality"] = s["ocr_quality"] if s and not v else None
        row["in_ungdc"] = c is not None and isinstance(c.get("text_en"), str)
        record_text = v["text"] if v else (s["text"] if s else None)
        row["records_vs_ungdc"] = agreement(record_text, c["text_en"]) if record_text and row["in_ungdc"] else None
        row["delivered_share"] = float(g["delivered_share"]) if g and g.get("delivered_share") else None
        rows.append(row)

    out = pd.DataFrame(rows).drop(columns=["english_kind", "original_kind"], errors="ignore")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUTPUT_DIR / "speeches.parquet", index=False)
    out.drop(columns=[c for c in out.columns if "text" in c]).to_csv(OUTPUT_DIR / "speeches.csv", index=False)
    if not replies.empty:
        replies.to_parquet(OUTPUT_DIR / "rights_of_reply.parquet", index=False)
    write_sources_report(out)
    log.info("%d speeches across %d sessions", len(out), out.session.nunique())
    return OUTPUT_DIR / "speeches.parquet"
