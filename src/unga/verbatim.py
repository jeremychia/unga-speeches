"""Split the UN's official verbatim records (A/<session>/PV.<n>) into general debate speeches.

The records are born-digital from session 48 (1993). Each gives the official English text of every speech and
notes the language it was spoken in, e.g. "(spoke in Japanese; English interpretation provided by the delegation)".
"""

import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import pymupdf

from . import countries
from .config import OUTPUT_DIR, RAW_DIR, session_year
from .http import Client

log = logging.getLogger(__name__)

FIRST_DIGITAL_SESSION = 48
DOCUMENT_URL = "https://documents.un.org/api/symbol/access?s={symbol}&l=en&t=pdf"
# the general debate never runs past this meeting number; scanning stops after a run of missing meetings
MAX_MEETING = 60
MAX_MISSING_IN_A_ROW = 5
# once the debate has started, this many meetings in a row without it means it has ended
MEETINGS_AFTER_DEBATE = 3
# opening and summit meetings can hold a few addresses, so the end is only watched for once the debate is under way
DEBATE_UNDER_WAY = 100

BODY_MIN_SIZE = 9.5  # page headers and footers are set smaller
# page numbers, the document number ("23-27138 (E)") and its barcode ("*2327138*"), some set at body size
PAGE_FURNITURE = re.compile(r"\d{1,3}|\d{2}-\d{5}\s*\(E\)|\*\d{7,}\*|\d{1,3}\s*/\s*\d{1,3}")
PRESIDING = re.compile(r"^the\s*(acting\s*|temporary\s*)?president\b|^the\s*chair", re.I)
GAP_AS_SPACE = 0.15  # a gap wider than this share of the font size between glyphs is a word space
LANGUAGE_NOTE = re.compile(r"\((?:spoke in|interpretation from) ([^;)]+)(;[^)]*)?\)", re.I)
LABEL_COUNTRY = re.compile(r"\(([^()]+)\)\s*(?:\((?:spoke|interpretation)[^)]*\))?\s*$")
ADDRESS_HEADING = re.compile(r"^Address by (?P<speaker>.+?)(?:, (?P<title>.+))?$", re.S)
# the stage direction names the speaker when a record has no heading
ESCORTED = re.compile(r"^(?P<speaker>.+?)(?:, (?P<title>.+?),)? was escorted into", re.S)
RIGHT_OF_REPLY = re.compile(r"right of reply", re.I)
LANGUAGE_CODES = {
    "english": "en", "french": "fr", "spanish": "es", "russian": "ru", "arabic": "ar", "chinese": "zh",
    "portuguese": "pt", "german": "de", "japanese": "ja", "italian": "it", "farsi": "fa", "persian": "fa",
    "korean": "ko", "turkish": "tr", "ukrainian": "uk", "kyrgyz": "ky", "kazakh": "kk", "uzbek": "uz",
    "tajik": "tg", "turkmen": "tk", "azerbaijani": "az", "armenian": "hy", "georgian": "ka", "mongolian": "mn",
    "indonesian": "id", "bahasa indonesia": "id", "malay": "ms", "vietnamese": "vi", "thai": "th", "khmer": "km",
    "lao": "lo", "burmese": "my", "hindi": "hi", "bengali": "bn", "bangla": "bn", "urdu": "ur", "nepali": "ne",
    "sinhala": "si", "dari": "fa", "pashto": "ps", "hebrew": "he", "greek": "el", "polish": "pl", "czech": "cs",
    "slovak": "sk", "hungarian": "hu", "romanian": "ro", "bulgarian": "bg", "serbian": "sr", "croatian": "hr",
    "bosnian": "bs", "slovenian": "sl", "macedonian": "mk", "albanian": "sq", "montenegrin": "sr", "latvian": "lv",
    "lithuanian": "lt", "estonian": "et", "finnish": "fi", "swedish": "sv", "norwegian": "no", "danish": "da",
    "icelandic": "is", "dutch": "nl", "maltese": "mt", "catalan": "ca", "luxembourgish": "lb", "swahili": "sw",
    "amharic": "am", "somali": "so", "tigrinya": "ti", "tetum": "tet", "dhivehi": "dv", "belarusian": "be",
}


@dataclass
class VerbatimSpeech:
    session: int
    year: int
    meeting: str
    meeting_url: str
    order_in_meeting: int
    kind: str  # general_debate, right_of_reply or other_intervention
    page: int
    iso3: str | None
    label: str
    heading_speaker: str | None
    heading_title: str | None
    spoken_language: str | None
    spoken_language_note: str | None
    interpretation_note: str | None
    text: str


def symbol(session: int, meeting: int) -> str:
    return f"A/{session}/PV.{meeting}"


def fetch_meeting(client: Client, session: int, meeting: int) -> Path | None:
    sym = symbol(session, meeting)
    dest = RAW_DIR / "verbatim" / str(session) / f"PV.{meeting}.pdf"
    fetched = client.fetch(DOCUMENT_URL.format(symbol=sym), dest)
    if not fetched or not dest.read_bytes().startswith(b"%PDF"):
        dest.unlink(missing_ok=True)
        dest.with_suffix(".pdf.meta.json").unlink(missing_ok=True)
        return None
    return dest


@dataclass
class _Block:
    page: int
    text: str
    bold_prefix: str
    all_bold: bool
    italic: bool


def _span_text(span: dict) -> str:
    """Span text rebuilt from glyph positions, with a space wherever letters sit apart; some records omit space characters."""
    out, prev = [], None
    for c in span["chars"]:
        if prev is not None and c["c"] != " " and prev["c"] != " " and c["bbox"][0] - prev["bbox"][2] > GAP_AS_SPACE * span["size"]:
            out.append(" ")
        out.append(c["c"])
        prev = c
    return "".join(out)


def _rows(block: dict) -> list[list[dict]]:
    """Group a block's lines into visual rows; some records place every word as its own line."""
    rows: list[list[dict]] = []
    last_y = None
    for line in block.get("lines", []):
        spans = [{**s, "text": _span_text(s)} for s in line["spans"]]
        spans = [s for s in spans if s["text"].strip()]
        if not spans:
            continue
        y = round(line["bbox"][1])
        if rows and last_y is not None and abs(y - last_y) <= 2:
            rows[-1] += spans
        else:
            rows.append(spans)
        last_y = y
    return rows


def _segment(page_no: int, rows: list[list[dict]]):
    """Cut a block where a row opens with a bold label or a bold heading begins or ends."""
    segment: list[list[dict]] = []
    for row in rows:
        first_bold = bool(row[0]["flags"] & 16)
        all_bold = all(s["flags"] & 16 for s in row)
        prev_all_bold = bool(segment) and all(s["flags"] & 16 for s in segment[-1])
        if segment and ((first_bold and not all_bold) or all_bold != prev_all_bold):
            yield _make_block(page_no, segment)
            segment = []
        segment.append(row)
    if segment:
        yield _make_block(page_no, segment)


def _make_block(page_no: int, rows: list[list[dict]]) -> _Block:
    spans = [s for row in rows for s in row]
    text = " ".join(_row_text(row) for row in rows)
    text = re.sub(r"(\w)- (\w)", r"\1-\2", re.sub(r"\s+", " ", text)).strip()
    prefix = ""
    for s in spans:
        if not s["flags"] & 16:
            break
        prefix += s["text"] + " "
    return _Block(page_no, text, re.sub(r"\s+", " ", prefix).strip(), all(s["flags"] & 16 for s in spans), all(s["flags"] & 2 for s in spans))


def _row_text(row: list[dict]) -> str:
    parts = [row[0]["text"]]
    for a, b in zip(row, row[1:]):
        parts.append(" " if b["bbox"][0] - a["bbox"][2] > GAP_AS_SPACE * a["size"] else "")
        parts.append(b["text"])
    return "".join(parts)


def _blocks(path: Path):
    with pymupdf.open(path) as doc:
        for page_no, page in enumerate(doc, start=1):
            for block in page.get_text("rawdict")["blocks"]:
                rows = [r for r in _rows(block) if r[0]["size"] >= BODY_MIN_SIZE and not PAGE_FURNITURE.fullmatch("".join(s["text"] for s in r).strip())]
                if rows:
                    yield from _segment(page_no, rows)


def _split_turn(block: _Block) -> tuple[str, str] | None:
    """(label, speech text) when the block opens a speaker's turn, e.g. 'Mr. Lavrov (Russian Federation) (spoke in Russian): ...'."""
    if not block.bold_prefix or block.all_bold:
        return None
    match = re.match(r"^(.{2,200}?(?:\([^)]*\)\s*)*):\s*", block.text)
    if not match or not block.text.startswith(block.bold_prefix[:10]):
        return None
    return match.group(1).strip(), block.text[match.end():]


def _agenda_state(block: _Block) -> bool | None:
    """True when a heading opens the general debate, False when it opens other business, None when it is not an agenda heading."""
    if not block.bold_prefix:
        return None
    lowered = block.text.lower()
    if lowered.startswith("general debate") or lowered.startswith("agenda item") and "general debate" in lowered[:200]:
        return True
    if lowered.startswith("agenda item") or block.all_bold and re.search(r"summit|high-level|commemorat", lowered):
        return False
    return None


def parse_meeting(path: Path, session: int, meeting: int) -> list[VerbatimSpeech]:
    speeches, current = [], None
    heading_text, escorted, last_was_heading = None, None, False
    # none until the record says which agenda item is under way; some records never say
    in_debate: bool | None = None
    replies = False
    introduction = None
    for block in _blocks(path):
        state = _agenda_state(block)
        if state is not None:
            in_debate, current, last_was_heading = state, None, False
            continue
        if block.all_bold:
            # a heading can run over two blocks: "Address by Mr. X," then "President of Y"
            if block.text.startswith("Address by"):
                heading_text, escorted = block.text, None
            elif last_was_heading and heading_text:
                heading_text += " " + block.text
            current, last_was_heading = None, block.text.startswith("Address by") or last_was_heading
            continue
        last_was_heading = False
        if block.italic and not block.bold_prefix:
            match = ESCORTED.match(block.text)
            if match:
                escorted = match
            continue  # stage directions: "was escorted into the General Assembly Hall"
        turn = _split_turn(block)
        if not turn:
            if current:
                current.text += "\n\n" + block.text
            continue
        label, text = turn
        current = None
        if PRESIDING.search(label):
            replies = replies or "right of reply" in text.lower()
            introduction = text  # "I now give the floor to ... of the Kingdom of Morocco"
            continue
        if in_debate is False:
            continue
        heading = ADDRESS_HEADING.match(heading_text) if heading_text else None
        language = LANGUAGE_NOTE.search(label)
        country = LABEL_COUNTRY.search(label)
        iso3 = (countries.find(heading.group(0)) if heading else None) or (countries.find(escorted.group(0)) if escorted else None)
        if not iso3 and country:
            iso3 = countries.resolve(country.group(1))
        if not iso3 and introduction:
            iso3 = countries.find(introduction)
        current = VerbatimSpeech(
            session=session,
            year=session_year(session),
            meeting=symbol(session, meeting),
            meeting_url=DOCUMENT_URL.format(symbol=symbol(session, meeting)),
            order_in_meeting=len(speeches) + 1,
            kind="right_of_reply" if replies or RIGHT_OF_REPLY.search(text[:400]) else "general_debate",
            page=block.page,
            iso3=iso3,
            label=LANGUAGE_NOTE.sub("", label).strip(),
            heading_speaker=heading.group("speaker").strip() if heading else None,
            heading_title=re.sub(r"\s+", " ", heading.group("title")).strip() if heading and heading.group("title") else None,
            spoken_language=LANGUAGE_CODES.get(language.group(1).strip().lower(), language.group(1).strip().lower()) if language else "en",
            spoken_language_note=language.group(0) if language else None,
            interpretation_note=language.group(2).strip("; ") if language and language.group(2) else None,
            text=text,
        )
        speeches.append(current)
        heading_text, escorted, introduction = None, None, None
    return speeches


def build_session(session: int, client: Client | None = None) -> Path:
    client = client or Client()
    speeches, missing, quiet, meeting = [], 0, 0, 0
    while meeting < MAX_MEETING and missing < MAX_MISSING_IN_A_ROW and quiet < MEETINGS_AFTER_DEBATE:
        meeting += 1
        path = fetch_meeting(client, session, meeting)
        if not path:
            missing += 1
            continue
        missing = 0
        found = parse_meeting(path, session, meeting)
        quiet = quiet + 1 if len(speeches) >= DEBATE_UNDER_WAY and not found else 0
        speeches += found
        log.info("%s: %d general debate speeches", symbol(session, meeting), len(found))
    # a delegation's debate speech is its longest turn; the rest introduce a video, raise a point of order or answer someone
    longest: dict[str, VerbatimSpeech] = {}
    for s in speeches:
        if s.kind == "general_debate" and s.iso3 and (s.iso3 not in longest or len(s.text) > len(longest[s.iso3].text)):
            longest[s.iso3] = s
    for s in speeches:
        if s.kind == "general_debate" and s.iso3 and longest[s.iso3] is not s:
            s.kind = "other_intervention"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"verbatim_{session}.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for s in speeches:
            f.write(json.dumps(asdict(s), ensure_ascii=False) + "\n")
    return out
