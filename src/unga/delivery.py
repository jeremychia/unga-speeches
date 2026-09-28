"""Compare the filed statement with the transcript of what was said, in the language it was spoken."""

import re
import unicodedata
from difflib import SequenceMatcher

ARABIC_MARKS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
ARABIC_LETTERS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ی": "ي", "ة": "ه", "ک": "ك"})
CJK = re.compile(r"[぀-ヿ㐀-鿿]")
WORD = re.compile(r"\w+")
# the site's header lines end at the auto-generated notice, in whichever language
TRANSCRIPT_NOTICE = re.compile(r"^‏?\[.*\]\s*$", re.M)


def tokens(text: str, language: str | None) -> list[str]:
    text = unicodedata.normalize("NFKC", text).lower()
    if language == "ar":
        # arabic pdfs split words at ligatures and stretch letters, so compare letters and ignore spacing
        text = ARABIC_MARKS.sub("", text).translate(ARABIC_LETTERS)
        return [c for c in text if c.isalnum()]
    if language in ("zh", "ja"):
        return [c for c in text if CJK.match(c) or c.isalnum()]
    return WORD.findall(text)


def transcript_body(text: str) -> str:
    notice = TRANSCRIPT_NOTICE.search(text)
    return text[notice.end():] if notice else text


def compare(statement: str, transcript: str, language: str | None) -> tuple[float, float]:
    """(share of the filed words that were said, share of the said words that were not filed)."""
    filed, said = tokens(statement, language), tokens(transcript_body(transcript), language)
    if not filed or not said:
        return 0.0, 0.0
    matched = sum(block.size for block in SequenceMatcher(None, filed, said, autojunk=False).get_matching_blocks())
    return round(matched / len(filed), 3), round(1 - matched / len(said), 3)
