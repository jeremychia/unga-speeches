"""The UN's scanned verbatim records of the general debate, 1946–1992 (sessions 1 to 47), read from the OCR text layer they carry.

The records before 1993 are scans. Their text layer is the UN's own OCR, so it is read as it stands, never re-recognised, and
every speech carries a score for how much of it is recognisable English. Until 1976 the records are numbered across sessions
(A/PV.<n>), so each session's debate meetings are found by date; from session 31 they are numbered within it (A/<s>/PV.<n>).
"""

import difflib
import json
import logging
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import pymupdf

from unga_speeches.config import OUTPUT_DIR, RAW_DIR, session_year
from unga_speeches.enrich import countries
from unga_speeches.http import Client
from unga_speeches.sources import verbatim

log = logging.getLogger(__name__)

LAST_SCANNED_SESSION = 47
FIRST_SESSION_NUMBERED = 31  # from 1976 each session numbers its own meetings
LAST_MEETING_BEFORE_31 = 2450  # A/PV.<n> runs to about here by the end of 1975
SESSION_SPAN = 500  # a session's opening lies within this many meetings of the previous debate's end
DEBATE_SCAN_LIMIT = 70  # meetings looked at after a session opens
MEETINGS_AFTER_DEBATE = 8  # this many in a row without the debate, once it has started, ends it; commemorations can interrupt it
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], start=1
)}  # fmt: skip
# the meeting's own date names its weekday ("Held on Thursday, 24 October 1946"); other dates on the page are quoted ones
DATE = re.compile(
    r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s*,?\s*(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s*,?\s+(19\d\d)", re.I
)
# a special session names itself in the record's capitalised heading; a mention of one in the text does not count
SPECIAL = re.compile(r"SPECIAL\s+SESSION")
HEADING_CHARS = 800  # the heading sits within this much text at the top of the first page
# the debate as an agenda item on a meeting's front page, not a mention of it in a speech
# ocr turns the item number's brackets into "[9)", "[91", "[9J" or "(9)"
# the item was "General discussion" in the early sessions; ocr can space its letters out ("G en era I discussion")
GENERAL = r"g\s?e\s?n\s?e\s?r\s?a\s?[l1I]\s+(?:debate|discussion)"
DEBATE = re.compile(
    rf"{GENERAL}\s*(?:[\[(]\s*\w{{1,3}}\s*[\])1Jjl|]?|\(\s*continu(?:ed|ation)\s*\))|agenda\s+item\s+\d+\s*[:.]?\s*(?:\(continued\)\s*)?{GENERAL}",
    re.I,
)
# an agenda heading inside a meeting: what follows it belongs to that item
AGENDA_HEADING = re.compile(
    r"(?:^|\n)\s*(?:AGENDA\s+ITEM\s+(?P<number>\d+)[^\n]*\n\s*(?P<title>[^\n(]*)|(?P<debate>GENERAL\s+(?:DEBATE|DISCUSSION))\b)"
)
# a tribute or commemoration interrupts the debate under its own heading, not an agenda item
TRIBUTE = re.compile(r"(?:^|\n)\s*(?:TRIBUTE\s+TO|Tribute\s+to\s+the\s+memory|COMMEMORATI|Commemorati)")
# the debate's item number, as the front page gives it: "General debate [9]"
DEBATE_ITEM = re.compile(rf"{GENERAL}\s*[\[(]\s*(\d{{1,3}})", re.I)
TITLE = (
    r"(?:Mr|Mrs|Miss|Ms|Sir|Dame|Lord|Lady|Prince|Princess|Sheikh|Shaikh|King|Queen|Emir|General|Marshal|Archbishop|Cardinal|Baron|Count"
    r"|Dr|U|Mgr|Monsignor|President|Vice-President|Prime\s+Minister|Chancellor|Emperor|Grand\s+Duke|Crown\s+Prince)"
)
# a label starts a line, or follows the previous speaker's last sentence when the ocr puts each word on its own line (1988 to 1991)
START = r"(?:^|\n|(?<=[.!?:;\"”)])\s)"
LABEL = re.compile(
    rf"{START}\s*(?:\d{{1,3}}\s*[.,]\s*)?(?P<name>{TITLE}[.•,]?\s+[^():]{{1,60}}?)\s*\((?P<country>[^()]{{2,70}})\)\s*"
    r"(?:\((?P<lang>(?:translated|interpretation|spoke)[^)]*)\))?\s*:",
)
# the records print a speaker's surname in capitals, so a label survives an ocr-mangled title ("Hr.", "Nr.") or a line break
CAPS_LABEL = re.compile(
    rf"{START}\s*(?:\d{{1,3}}\s*[.,]\s*)?(?:[A-Za-z][a-z]{{0,8}}[.•,]?\s+){{0,2}}(?P<name>[A-Z][A-Z~!'’\-.]{{2,}}(?:\s+[A-Z][A-Z~!'’\-.]{{1,}}){{0,4}})"
    r"\s*\((?P<country>[^()]{2,70})\)\s*(?:\((?P<lang>(?:translated|interpretation|spoke)[^)]*)\))?\s*[:;]"
)
# heads of state from the 1980s are labelled by office alone, under a heading that names their country
HEAD_LABEL = re.compile(
    rf"{START}\s*(?P<name>(?:President|Prime\s+Minister|King|Queen|Emir|Sultan|Chairman|General|Prince|Grand\s+Duke)\s+[A-Z][^():]{{1,50}}?)\s*"
    r"(?:\((?P<lang>(?:translated|interpretation|spoke)[^)]*)\))?\s*:"
)
# the heading can wrap onto a second line of capitals
ADDRESS = re.compile(r"ADDRESS\s+BY\s+(?P<speaker>[^\n]+?),\s+(?P<title>[^\n]+?)\s+OF\s+(?P<country>[^\n]+(?:\n[A-Z][A-Z ,.'\-]+(?=\n))?)")
DEBATE_TITLE = re.compile(GENERAL, re.I)
PLAIN_DEBATE = re.compile(GENERAL, re.I)
CHAIR = re.compile(r"(?:^|\n)\s*(?:\d{1,3}\s*[.,]\s*)?The\s+(?:ACTING\s+|TEMPORARY\s+)?PRESIDENT\b[^:\n]{0,70}:", re.I)
ROSE = re.compile(r"The\s+meeting\s+rose\s+at", re.I)
LANG = re.compile(r"(?:translated|interpretation|spoke)\s+(?:from|in)\s+([A-Za-z]+)", re.I)
FRENCH = {"le", "la", "les", "des", "et", "est", "dans", "pour", "que", "qui", "une", "du", "au", "sur", "pas", "par", "nous", "ce"}
ENGLISH = {"the", "of", "and", "to", "in", "that", "is", "for", "which", "this", "we", "be", "it", "by", "on", "are"}
FRONT_PAGES = 3  # the contents and the first agenda heading fall within these
SINGLE_COLUMN_SHARE = 0.5  # a page with more of its text in full-width blocks than this is one column
MARGIN = 40  # points at the top and bottom of a page that hold running heads and page numbers
COUNTRY_MATCH = 0.85  # a label's country must be at least this close to a known name, after OCR noise
HEADING_REACH = 3000  # characters between an address heading and the turn it introduces
MIN_TURN_WORDS = 150  # shorter turns are procedural
MIN_DEBATE_WORDS = 600  # a delegation's debate speech is at least this long; tributes and replies run shorter


@dataclass
class ScannedSpeech:
    session: int
    year: int
    meeting: str
    meeting_url: str
    order_in_meeting: int
    iso3: str | None
    label: str
    heading_speaker: str | None
    heading_title: str | None
    spoken_language: str | None
    spoken_language_note: str | None
    ocr_quality: float  # share of words that are in the vocabulary of the born-digital records
    words: int
    text: str


def symbol(session: int, meeting: int) -> str:
    return f"A/{session}/PV.{meeting}" if session >= FIRST_SESSION_NUMBERED else f"A/PV.{meeting}"


def fetch(client: Client, sym: str) -> Path | None:
    dest = RAW_DIR / "scanned" / (sym.replace("/", "_") + ".pdf")
    fetched = client.fetch(verbatim.DOCUMENT_URL.format(symbol=sym), dest)
    if not fetched or not dest.read_bytes()[:5].startswith(b"%PDF"):
        dest.unlink(missing_ok=True)
        dest.with_suffix(".pdf.meta.json").unlink(missing_ok=True)
        return None
    return dest


def _front(path: Path) -> str:
    with pymupdf.open(path) as doc:
        return "".join(doc[i].get_text() for i in range(min(FRONT_PAGES, doc.page_count)))


def header(path: Path, early: bool = False) -> dict:
    """The meeting's date, whether it belongs to a special session, and whether its agenda holds the general debate.

    Early records name the item plainly ("general debate") with no number, so for them a plain mention on the first page,
    where the heading and contents sit, is enough."""
    front = _front(path)
    with pymupdf.open(path) as doc:
        first = doc[0].get_text() if doc.page_count else ""
    when = None
    for m in DATE.finditer(front):
        try:
            when = date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
            break
        except ValueError:  # an ocr slip such as "31 September"
            continue
    debate = bool(DEBATE.search(front)) or (early and bool(PLAIN_DEBATE.search(first)))
    return {"date": when, "special": bool(SPECIAL.search(first[:HEADING_CHARS])), "debate": debate}


def _first_on_or_after(client: Client, target: date, lo: int, hi: int) -> int:
    """The first A/PV.<n> dated on or after the target, by binary search; meeting dates only move forward."""
    while lo < hi:
        mid = (lo + hi) // 2
        probe, head = mid, None
        # a missing or undated record is stepped over to the next one
        while probe < hi:
            path = fetch(client, symbol(1, probe))
            if path and (head := header(path))["date"]:
                break
            probe += 1
        if head is None or head["date"] is None or head["date"] >= target:
            hi = mid
        else:
            lo = probe + 1
    return lo


def debate_meetings(client: Client, session: int, start: int) -> list[tuple[str, Path]]:
    """The meetings of a session's general debate, walking forward from its opening.

    Every meeting from the first to the last that lists the debate is kept, since a meeting in between can hold debate turns
    whose front page lost the words to ocr; which turns belong to the debate is decided later, by agenda heading."""
    seen, flagged, since = [], [], 0
    # before 1976 the search lands near the opening; meetings are skipped until one is dated in the session's autumn
    opened = session >= FIRST_SESSION_NUMBERED
    for n in range(start, start + DEBATE_SCAN_LIMIT):
        sym = symbol(session, n)
        path = fetch(client, sym)
        if not path:
            if session >= FIRST_SESSION_NUMBERED and flagged:
                break
            continue
        head = header(path, early=session < FIRST_SESSION_NUMBERED)
        if not opened:
            if not head["date"] or head["date"] < date(session_year(session), 9, 1):
                continue
            opened = True
        # special and emergency sessions can meet in the middle of a regular one, so their meetings are stepped over
        if head["special"]:
            continue
        if session < FIRST_SESSION_NUMBERED and head["date"] and head["date"].year > session_year(session) + 1:
            break
        seen.append((sym, path))
        if head["debate"]:
            flagged.append(len(seen) - 1)
            since = 0
        elif flagged:
            since += 1
            if since >= MEETINGS_AFTER_DEBATE:
                break
    return seen[flagged[0] : flagged[-1] + 1] if flagged else []


def _language(text: str) -> str:
    words = re.findall(r"[a-zà-ÿ]+", text.lower())
    fr, en = sum(w in FRENCH for w in words), sum(w in ENGLISH for w in words)
    return "fr" if fr > en else "en"


def _blocks(page) -> list[tuple[float, float, float, str]]:
    height = page.rect.height
    return [
        (b[0], b[2], b[1], b[4])
        for b in page.get_text("blocks")
        if b[6] == 0 and MARGIN < b[1] < height - MARGIN and b[4].strip() and _language(b[4]) == "en"
    ]


def _lines(page) -> list[tuple[float, float, float, str]]:
    """The page's English text lines as (x0, x1, y, text), running heads dropped and French blocks of bilingual pages dropped."""
    out = []
    height = page.rect.height
    for block in page.get_text("dict")["blocks"]:
        lines = [(ln["bbox"], "".join(s["text"] for s in ln["spans"])) for ln in block.get("lines", [])]
        text = " ".join(x for _, x in lines)
        if not text.strip() or _language(text) != "en":
            continue
        out += [(b[0], b[2], b[1], x) for b, x in lines if MARGIN < b[1] < height - MARGIN and x.strip()]
    return out


def ordered_text(path: Path, unit: str = "lines") -> str:
    """The English text of a record in reading order: a typescript page top to bottom, a two-column page left column then right,
    band by band between full-width pieces. The pieces are the ocr's lines, or its blocks, which keep a label with its text
    but can straddle both columns."""
    parts = []
    with pymupdf.open(path) as doc:
        for page in doc:
            mid = page.rect.width / 2
            lines = _lines(page) if unit == "lines" else _blocks(page)
            spanning = sorted((ln for ln in lines if ln[0] < mid - 20 and ln[1] > mid + 20), key=lambda ln: ln[2])
            if sum(len(ln[3]) for ln in spanning) > SINGLE_COLUMN_SHARE * sum(len(ln[3]) for ln in lines):
                parts += [ln[3] for ln in sorted(lines, key=lambda ln: (round(ln[2]), ln[0]))]
                continue
            band_start = 0.0
            for cut in [ln[2] for ln in spanning] + [page.rect.height]:
                band = [ln for ln in lines if band_start <= ln[2] < cut and ln not in spanning]
                parts += [ln[3] for ln in sorted((ln for ln in band if ln[0] < mid), key=lambda ln: ln[2])]
                parts += [ln[3] for ln in sorted((ln for ln in band if ln[0] >= mid), key=lambda ln: ln[2])]
                parts += [ln[3] for ln in spanning if ln[2] == cut]
                band_start = cut
    text = "\n".join(parts)
    return re.sub(r"-\s*\n\s*(?=[a-z])", "", text)  # words split across lines


def _country(text: str) -> str | None:
    text = " ".join(text.split())
    if iso3 := countries.resolve(text) or countries.find(text):
        return iso3
    names = countries._names()
    close = difflib.get_close_matches(countries.normalise(text), list(names), n=1, cutoff=COUNTRY_MATCH)
    return names[close[0]] if close else None


_VOCABULARY: set[str] | None = None


def vocabulary() -> set[str]:
    """Words used at least three times in the born-digital records, 1993 onwards: the yardstick for OCR quality."""
    global _VOCABULARY
    if _VOCABULARY is None:
        counts = Counter()
        for path in sorted(OUTPUT_DIR.glob("verbatim_*.jsonl")):
            for line in path.open(encoding="utf-8"):
                counts.update(w.lower() for w in re.findall(r"[A-Za-z]{2,}", json.loads(line)["text"]))
        _VOCABULARY = {w for w, n in counts.items() if n >= 3}
    return _VOCABULARY


def ocr_quality(text: str) -> float:
    words = [w.lower() for w in re.findall(r"[A-Za-z]{2,}", text)]
    return round(sum(w in vocabulary() for w in words) / len(words), 3) if words else 0.0


def parse_meeting(path: Path, session: int, sym: str, debate_items: set[str] | None = None) -> list[ScannedSpeech]:
    """The meeting read both ways, by ocr line and by ocr block, keeping the reading that finds more speech."""
    readings = [parse_text(ordered_text(path, unit), session, sym, debate_items) for unit in ("lines", "blocks")]
    return max(readings, key=lambda r: (len(r), sum(s.words for s in r)))


def parse_text(text: str, session: int, sym: str, debate_items: set[str] | None = None) -> list[ScannedSpeech]:
    """Every delegate's turn in a meeting's text that falls under the general debate, with its country and spoken language."""
    marks = []
    for m in LABEL.finditer(text):
        marks.append((m.start(), m.end(), "delegate", m))
    taken = {start for start, _, _, _ in marks}
    for m in CAPS_LABEL.finditer(text):
        if not any(abs(m.start() - s) < 5 for s in taken):
            marks.append((m.start(), m.end(), "delegate", m))
    for m in HEAD_LABEL.finditer(text):
        marks.append((m.start(), m.end(), "head", m))
    for m in CHAIR.finditer(text):
        marks.append((m.start(), m.end(), "chair", m))
    for m in ROSE.finditer(text):
        marks.append((m.start(), m.end(), "end", m))
    marks.sort(key=lambda x: x[0])
    headings = [(m.start(), m) for m in ADDRESS.finditer(text)]
    debate_items = (
        set(debate_items or ())
        | set(DEBATE_ITEM.findall(text))
        | {m.group("number") for m in AGENDA_HEADING.finditer(text) if m.group("number") and DEBATE_TITLE.search(m.group("title") or "")}
    )
    agenda = [
        (m.start(), bool(m.group("debate")) or m.group("number") in debate_items or bool(DEBATE_TITLE.search(m.group("title") or "")))
        for m in AGENDA_HEADING.finditer(text)
    ]
    # a head of state's address is part of the debate, under its own heading; a tribute is not
    agenda = sorted(agenda + [(pos, True) for pos, _ in headings] + [(m.start(), False) for m in TRIBUTE.finditer(text)])
    out = []
    for i, (start, end, kind, m) in enumerate(marks):
        if kind not in ("delegate", "head"):
            continue
        stop = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        body = " ".join(text[end:stop].split())
        if len(body.split()) < MIN_TURN_WORDS:
            continue
        # with no agenda headings the whole meeting is the debate; otherwise the latest heading before the turn decides
        item = next((is_debate for pos, is_debate in reversed(agenda) if pos < start), not agenda)
        if not item:
            continue
        # a heading names the speaker only when it stands just before the turn; the contents list names every address
        heading = next((h for pos, h in reversed(headings) if start - HEADING_REACH < pos < start), None)
        country_text = m.group("country") if kind == "delegate" else (heading.group("country") if heading else "")
        lang = LANG.search(m.group("lang") or "")
        out.append(
            ScannedSpeech(
                session=session,
                year=session_year(session),
                meeting=sym,
                meeting_url=verbatim.DOCUMENT_URL.format(symbol=sym),
                order_in_meeting=len(out) + 1,
                iso3=_country(country_text) if country_text else None,
                label=" ".join(m.group(0).split()),
                heading_speaker=heading.group("speaker").title() if heading and kind == "head" else None,
                heading_title=heading.group("title").title() if heading and kind == "head" else None,
                spoken_language=verbatim.LANGUAGE_CODES.get(lang.group(1).lower()) if lang else None,
                spoken_language_note=m.group("lang"),
                ocr_quality=ocr_quality(body),
                words=len(body.split()),
                text=body,
            )
        )
    return out


def session_start(client: Client, session: int, after: int = 1) -> int:
    """The first meeting of a session's autumn part: from session 31 simply meeting 1."""
    if session >= FIRST_SESSION_NUMBERED:
        return 1
    return _first_on_or_after(client, date(session_year(session), 9, 1), after, min(LAST_MEETING_BEFORE_31, after + SESSION_SPAN))


def build_session(session: int, client: Client | None = None, after: int = 1) -> tuple[Path, int]:
    """Every delegation's general debate speech in one session: its longest turn in the debate meetings.

    Returns the output file and the last meeting looked at, so the next session's search can start after it."""
    client = client or Client()
    start = session_start(client, session, after)
    meetings = debate_meetings(client, session, start)
    # the debate's item number is the same all session, so a meeting whose ocr lost the words still knows it
    items = Counter(n for _, path in meetings for n in DEBATE_ITEM.findall(_front(path)))
    session_items = {items.most_common(1)[0][0]} if items else set()
    speeches = [s for sym, path in meetings for s in parse_meeting(path, session, sym, session_items)]
    best: dict[str, ScannedSpeech] = {}
    for s in speeches:
        if s.iso3 and s.words >= MIN_DEBATE_WORDS and (s.iso3 not in best or s.words > best[s.iso3].words):
            best[s.iso3] = s
    out = OUTPUT_DIR / f"scanned_{session}.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for s in sorted(best.values(), key=lambda s: (s.meeting, s.order_in_meeting)):
            f.write(json.dumps(asdict(s), ensure_ascii=False) + "\n")
    last = int(meetings[-1][0].rsplit(".", 1)[1]) if meetings else start
    log.info("session %d: %d debate meetings from %s, %d delegations", session, len(meetings), symbol(session, start), len(best))
    return out, last
