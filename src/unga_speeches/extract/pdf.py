"""Pull the text layer out of a statement pdf, changing nothing but known extraction faults."""

import re
import shutil
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf
from langdetect import DetectorFactory, detect_langs

DetectorFactory.seed = 0

ARABIC_SCRIPT = re.compile(r"[؀-ۿ]")
# share of non-space characters that are letters; a broken font encoding yields mostly symbols
MIN_LETTER_SHARE = 0.6
MIN_CHARS = 300
MAX_MISORDERED_MARK_SHARE = 0.01
MAX_MIXED_SCRIPT_SHARE = 0.01
# a page image with little text beside it is a scan or a printout, e.g. a web page saved to pdf with the speech as pictures
SCAN_MIN_IMAGE_PAGE_SHARE = 0.9
SCAN_MAX_CHARS_PER_PAGE = 400
# a capital inside a lowercase word, e.g. "diLerences" where the font maps the "ff" ligature to "L"
MIS_MAPPED_LIGATURE = re.compile(r"\b[a-z]+[A-Z][a-z]{2,}\b")
MIN_MIS_MAPPED = 3
NON_LATIN = re.compile(r"[\u0370-\u052F\u0590-\u08FF\u0900-\u0DFF\u0E00-\u10FF\u1200-\u139F\u1780-\u17FF\uFB50-\uFDFF\uFE70-\uFEFF]")
INDIC = re.compile(r"[\u0900-\u0DFF]")
# too few non-latin words to judge, e.g. one cyrillic letter typed into an english word
MIN_NON_LATIN_WORDS = 50
ASCII_NOISE = re.compile(r"[A-Za-z@<>{}|~^]")
PRESENTATION_FORMS = re.compile(r"[\uFB50-\uFDFF\uFE70-\uFEFF]+")


@dataclass
class ExtractedText:
    text: str
    pages: int
    method: str  # text_layer, ocr, or none
    detected_language: str | None
    language_confidence: float | None
    warnings: list[str] = field(default_factory=list)


def _letter_share(text: str) -> float:
    chars = [c for c in text if not c.isspace()]
    return sum(unicodedata.category(c)[0] in "LM" for c in chars) / len(chars) if chars else 0.0


def _mixed_script_share(text: str) -> float:
    """Share of non-latin words carrying ascii letters or symbols, the mark of a font whose glyphs map to the wrong characters."""
    words = [w for w in text.split() if NON_LATIN.search(w)]
    if len(words) < MIN_NON_LATIN_WORDS:
        return 0.0
    return sum(bool(ASCII_NOISE.search(w)) for w in words) / len(words)


def _normalise_presentation_forms(text: str) -> str:
    """Map arabic presentation forms (glyph shapes) to the letters they draw, leaving every other character alone."""
    return PRESENTATION_FORMS.sub(lambda m: unicodedata.normalize("NFKC", m.group()), text)


def refine_cyrillic(language: str | None, text: str) -> str | None:
    """Langdetect has no kyrgyz, kazakh or tajik and calls them russian; their extra letters tell them apart."""
    if language != "ru":
        return language

    def count(letters: str) -> int:
        return sum(text.count(c) for c in letters)

    if count("ҳҷӣӯ") > 20:
        return "tg"
    if count("әғқұһі") > 20:
        return "kk"
    if count("ңөү") > 20:
        return "ky"
    return language


def _misordered_mark_share(text: str) -> float:
    """Share of indic words that open with a combining mark, which valid text never does; a mis-encoded indic font does it constantly."""
    words = [w for w in text.split() if INDIC.search(w)]
    return sum(unicodedata.category(w[0]) in ("Mn", "Mc") for w in words) / len(words) if words else 0.0


def _indic_word_count(text: str) -> int:
    return sum(bool(INDIC.search(w)) for w in text.split())


def _is_scan(doc: pymupdf.Document, text: str) -> bool:
    image_pages = sum(1 for page in doc if page.get_images())
    return image_pages >= SCAN_MIN_IMAGE_PAGE_SHARE * doc.page_count and len(text) < SCAN_MAX_CHARS_PER_PAGE * doc.page_count


def _page_text_repairing_ligatures(page: pymupdf.Page) -> str:
    """Rebuild the page from glyphs, restoring arabic ligatures (لا, ﷲ) that the pdf stores as zero-width letters then one wide letter, in reverse."""
    lines = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            chars = [c for span in line["spans"] for c in span["chars"]]
            out, run = [], []
            for c in chars:
                zero_width = abs(c["bbox"][2] - c["bbox"][0]) < 0.05
                if zero_width and ARABIC_SCRIPT.match(c["c"]):
                    run.append(c["c"])
                    continue
                if run and ARABIC_SCRIPT.match(c["c"]):
                    out.append(c["c"] + "".join(reversed(run)))
                else:
                    out.extend(run + [c["c"]])
                run = []
            out.extend(run)
            lines.append("".join(out))
    return "\n".join(lines)


def _ocr_page(page: pymupdf.Page, language: str) -> str:
    return page.get_textpage_ocr(language=language, full=True).extractText()


def extract(path: Path, ocr_language: str = "eng") -> ExtractedText:
    warnings = []
    with pymupdf.open(path) as doc:
        text = "\n\n".join(page.get_text("text").strip("\n") for page in doc).strip()
        method = "text_layer"
        if ARABIC_SCRIPT.search(text):
            text = "\n\n".join(_page_text_repairing_ligatures(page).strip("\n") for page in doc).strip()
            text = _normalise_presentation_forms(text)
            warnings.append("right-to-left text: punctuation at line ends may sit on the wrong side; check against the pdf")
        broken_indic = _misordered_mark_share(text) > MAX_MISORDERED_MARK_SHARE
        if broken_indic and _indic_word_count(text) < MIN_NON_LATIN_WORDS:
            warnings.append("a short passage in an indic script is mis-encoded in the pdf; read that passage in the pdf itself")
            broken_indic = False
        unusable = (
            len(text) < MIN_CHARS
            or _is_scan(doc, text)
            or _letter_share(text) < MIN_LETTER_SHARE
            or broken_indic
            or _mixed_script_share(text) > MAX_MIXED_SCRIPT_SHARE
        )
        if unusable:
            if shutil.which("tesseract"):
                text = "\n\n".join(_ocr_page(page, ocr_language).strip("\n") for page in doc).strip()
                method = "ocr"
                warnings.append("text layer unusable, so this text is ocr output and may contain recognition errors")
            else:
                text, method = "", "none"
                warnings.append("text layer unusable and tesseract is not installed, so no text was taken from this pdf")
        mis_mapped = MIS_MAPPED_LIGATURE.findall(text)
        if len(mis_mapped) >= MIN_MIS_MAPPED:
            warnings.append(f"a ligature is mis-mapped in the pdf, e.g. {mis_mapped[0]!r}; read those words in the pdf itself")
        pages = doc.page_count
    language, confidence = detect_language(text) if text else (None, None)
    return ExtractedText(text, pages, method, language, confidence, warnings)


def detect_language(text: str) -> tuple[str | None, float | None]:
    try:
        best = detect_langs(text[:20000])[0]
    except Exception:
        return None, None
    # langdetect reports chinese as zh-cn / zh-tw
    return refine_cyrillic(best.lang.split("-")[0], text), round(best.prob, 3)
