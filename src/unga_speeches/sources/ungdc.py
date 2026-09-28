"""Load the UN General Debate Corpus (Jankin, Baturo and Dasandi; CC0): English texts and speakers for 1946 onwards.

Harvard Dataverse gates the download behind a form, so fetch the files by hand into data/raw/ungdc/:
https://doi.org/10.7910/DVN/0TJX8Y
"""

import re
import tarfile
from pathlib import Path

import pandas as pd

from unga_speeches.config import OUTPUT_DIR, RAW_DIR
from unga_speeches.enrich import roles

UNGDC_DIR = RAW_DIR / "ungdc"
DATASET_URL = "https://doi.org/10.7910/DVN/0TJX8Y"
TEXT_FILE = re.compile(r"(?P<iso3>[A-Z]{2,4})_(?P<session>\d+)_(?P<year>\d{4})\.txt$")

# codes in the speaker workbook that differ from the ones its text files use
CODE_FIXES = {"CZK": "CSK", "DKN": "DNK", "EC": "EU", "PAR": "PRY", "PKR": "PRK", "POR": "PRT", "YDYE": "YMD", "ZFA": "ZAF"}

# the speaker workbook's headers vary between releases; map them onto one set of names
COLUMN_ALIASES = {
    "year": "year",
    "session": "session",
    "iso code": "iso3",
    "iso": "iso3",
    "country": "country",
    "name of person speaking": "speaker_name",
    "post": "speaker_title",
    "language": "language",
    "notes": "notes",
}


def load_speakers(path: Path | None = None) -> pd.DataFrame:
    path = path or next(UNGDC_DIR.glob("Speakers_by_session*.xlsx"), None)
    if not path:
        raise FileNotFoundError(f"put Speakers_by_session.xlsx from {DATASET_URL} into {UNGDC_DIR}")
    frame = pd.read_excel(path)
    frame.columns = [COLUMN_ALIASES.get(str(c).strip().lower(), str(c).strip().lower()) for c in frame.columns]
    missing = {"year", "session", "iso3", "speaker_title"} - set(frame.columns)
    if missing:
        raise ValueError(f"speaker workbook is missing {sorted(missing)}; its columns are {list(frame.columns)}")
    frame["iso3"] = frame["iso3"].astype(str).str.strip().replace(CODE_FIXES)
    frame["role"] = [roles.classify(t if isinstance(t, str) else None) for t in frame["speaker_title"]]
    frame["role_group"] = frame["role"].map(roles.ROLE_GROUP)
    return frame


def iter_texts(archive: Path | None = None):
    """Yield (iso3, session, year, text) from the corpus archive without unpacking it."""
    archive = archive or next(UNGDC_DIR.glob("UNGDC_*.tar.gz"), None)
    if not archive:
        raise FileNotFoundError(f"put UNGDC_1946-*.tar.gz from {DATASET_URL} into {UNGDC_DIR}")
    with tarfile.open(archive) as tar:
        for member in tar:
            match = TEXT_FILE.search(member.name)
            if member.isfile() and match and not Path(member.name).name.startswith("."):
                text = tar.extractfile(member).read().decode("utf-8", errors="replace").strip()
                yield match["iso3"], int(match["session"]), int(match["year"]), text


def build_history() -> Path:
    speakers = load_speakers()
    texts = pd.DataFrame(iter_texts(), columns=["iso3", "session", "year", "text_en"])
    merged = texts.merge(speakers, on=["iso3", "session", "year"], how="outer", indicator=True)
    merged["source"] = DATASET_URL
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / "history_ungdc.parquet"
    merged.to_parquet(out, index=False)
    return out
