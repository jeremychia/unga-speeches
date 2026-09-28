"""A cleaned copy of each text for language analysis; the verbatim text is always kept beside it."""

import re
from collections import Counter

from unga_speeches.enrich.delivery import transcript_body

SENTENCE_END = re.compile(r"[.!?:;\"”’»)\]]$|[。！？]$")
PAGE_MARK = re.compile(r"^(page\s*)?\d{1,3}(\s*(of|/|de|из)\s*\d{1,3})?$|^-\s*\d{1,3}\s*-$", re.I)
# the presiding officer's words that open and close each transcript
PRESIDING_LINE = re.compile(
    r"^(the (general )?assembly will (now )?hear|on behalf of the (general )?assembly|i thank the .{0,120} for (his|her|their|the)|i would (like|wish) to thank (the )?(president|prime minister|minister|vice|king|his|her)|i would like\.?$|i (now )?(request|ask) (the )?protocol|(and )?(i )?invite (him|her) to|on behalf of the general assembly|"
    r"i now give the floor|i give the floor|thank you\.?$|merci\.?$|gracias\.?$|l'assemblée va|je prie le protocole|la asamblea escuchará|solicito al protocolo)",
    re.I,
)
CLOSING_INLINE = re.compile(
    r"\s*(on behalf of the (general )?assembly, i (wish to )?thank|i thank the .{0,120} for (his|her|their) ).*$", re.I
)
DELIVERY_NOTE = re.compile(
    r"^\(?\s*(please\s+)?check\s+against\s+delivery\s*\)?$|^\(?\s*seul le prononcé fait foi\s*\)?$|^\(?\s*cotejar con el discurso pronunciado\s*\)?$",
    re.I,
)


def clean(text: str, kind: str) -> str:
    if not text:
        return ""
    lines = [line.strip() for line in text.replace("\r", "").split("\n")]
    if kind == "transcript":
        lines = [line.lstrip("\u200f") for line in transcript_body(text).split("\n")]
        lines = _trim_presiding(lines)
    # headers and footers repeat on every page of a pdf
    repeated = {line for line, n in Counter(line for line in lines if line and len(line) < 80).items() if n >= 3 and kind == "statement"}
    kept = [line for line in lines if not (line in repeated or PAGE_MARK.match(line) or DELIVERY_NOTE.match(line))]

    paragraphs, current = [], []
    for line in kept:
        if not line:
            if current and SENTENCE_END.search(current[-1]):
                paragraphs.append(current)
                current = []
            continue
        if current and SENTENCE_END.search(current[-1]) and (line[:1].isupper() or not line[:1].isalpha()):
            paragraphs.append(current)
            current = []
        current.append(line)
    if current:
        paragraphs.append(current)
    return "\n\n".join(_join(p) for p in paragraphs).strip()


def _join(lines: list[str]) -> str:
    out = lines[0]
    for line in lines[1:]:
        # word processors rarely hyphenate, so a line-end hyphen is a compound ("well-known") and is kept
        if out.endswith("-") and out[-2:-1].isalpha():
            out += line
        elif re.search(r"[　-鿿]$", out) and re.match(r"[　-鿿]", line):
            out += line
        else:
            out += " " + line
    return re.sub(r"[ \t]+", " ", out)


def _trim_presiding(lines: list[str]) -> list[str]:
    # the chair's introduction sits in the first few lines, sometimes after the tail of the previous speaker's thanks
    opening = [i for i, line in enumerate(lines[:10]) if PRESIDING_LINE.match(line)]
    start = opening[-1] + 1 if opening else 0
    end = len(lines)
    while end > start and (not lines[end - 1] or PRESIDING_LINE.match(lines[end - 1])):
        end -= 1
    kept = lines[start:end]
    if kept:
        kept[-1] = CLOSING_INLINE.sub("", kept[-1])
    return kept
