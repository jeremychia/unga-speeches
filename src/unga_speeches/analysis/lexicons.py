"""Transparent word lists: which issues a speech raises, and which theory of international relations its vocabulary leans on."""

import re

# an issue is raised when any pattern appears once
ISSUES = {
    "Ukraine": r"\bukrain",
    "Gaza or Palestine": r"\bgaza\b|\bpalestin",
    "Gaza": r"\bgaza\b",
    "Palestinian statehood": r"two-state|palestinian state|state of palestine|recogni[sz]\w*\s+(of\s+)?(the\s+)?(state\s+of\s+)?palestin",
    "Iran and the Gulf war": r"\biran\b|\biranian|persian gulf|gulf war|\bhormuz",
    "Sudan": r"(?<!south )\bsudan\b",
    "Haiti": r"\bhaiti",
    "Climate change": r"climate|global warming|sea[- ]level",
    "Artificial intelligence": r"(?i:artificial intelligence)|\bAI\b",
    "Security Council reform": r"reform of the security council|security council reform|reform(ing)? the security council",
    "Debt": r"\bdebt\b",
    "Nuclear weapons": r"nuclear weapon|non-proliferation|nuclear disarmament",
    "Terrorism": r"terroris",
    "Migration and refugees": r"\bmigra|\brefugee",
    "Sanctions": r"sanction|unilateral coercive",
    "Colonialism and reparations": r"colonial|reparat",
    "The next Secretary-General": r"(next|new|future) secretary-general|woman secretary-general|female secretary-general|selection of the secretary-general",
    "Taiwan": r"\btaiwan",
}

# phrases that separate one reading of world order from another, reported as the share of speeches using each
MARKERS = {
    "Multipolar": r"multipolar",
    "Rules-based order": r"rules-based",
    "Great power(s)": r"great powers?\b",
    "Spheres of influence": r"spheres? of influence",
    "Hegemony": r"hegemon",
    "Double standards": r"double standard",
    "Global South": r"global south",
    "Unilateral sanctions": r"unilateral coercive|sanction",
    "Reparations": r"reparat",
    "Security Council veto": r"\bveto",
    "Nuclear": r"\bnuclear",
}

# each theory's signature vocabulary, matched as word prefixes and counted per 1,000 words
FRAMES = {
    "Realism": [
        r"power",
        r"security",
        r"threat",
        r"deter",
        r"military",
        r"armed forces",
        r"arms\b",
        r"weapon",
        r"defen[cs]e",
        r"force\b",
        r"strateg",
        r"balance of power",
        r"great power",
        r"national interest",
        r"territor",
        r"war\b",
        r"wars\b",
    ],
    "Liberal institutionalism": [
        r"cooperat",
        r"multilateral",
        r"institution",
        r"international law",
        r"rules-based",
        r"rule of law",
        r"trade",
        r"interdependen",
        r"partnership",
        r"treat(y|ies)",
        r"charter",
        r"agreement",
        r"reform",
        r"governance",
        r"democra",
    ],
    # "trust" is left out, because this session's theme is "Restoring trust"
    "Constructivism": [
        r"identit",
        r"norm\b",
        r"norms\b",
        r"values",
        r"dignity",
        r"cultur",
        r"civili[sz]ation",
        r"histor",
        r"shared",
        r"solidarity",
        r"humanity",
        r"belong",
        r"memory",
        r"narrative",
        r"moral",
    ],
    "Critical and postcolonial": [
        r"colonial",
        r"imperial",
        r"global south",
        r"inequalit",
        r"injustice",
        r"justice",
        r"reparat",
        r"exploit",
        r"hegemon",
        r"sanction",
        r"unilateral coercive",
        r"debt",
        r"marginali",
        r"domination",
        r"north and south",
    ],
}

_MARKER_PATTERNS = {name: re.compile(p, re.I) for name, p in MARKERS.items()}
_FRAME_PATTERNS = {name: re.compile(r"\b(" + "|".join(terms) + r")", re.I) for name, terms in FRAMES.items()}
# "AI" is matched in capitals only, so a name such as "Ai" is not counted
_ISSUE_PATTERNS = {name: re.compile(pattern, 0 if name == "Artificial intelligence" else re.I) for name, pattern in ISSUES.items()}
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"“])")
# a sentence carrying the salutations is a heading run into the speech, not something said about the world
SALUTATION = re.compile(r"madam president|mr\.? president|excellencies", re.I)


def issues(text: str) -> dict[str, bool]:
    return {name: bool(p.search(text)) for name, p in _ISSUE_PATTERNS.items()}


def markers(text: str) -> list[str]:
    return [name for name, p in _MARKER_PATTERNS.items() if p.search(text)]


def frame_rates(text: str) -> dict[str, float]:
    """Matches per 1,000 words for each theory's vocabulary."""
    words = max(1, len(text.split()))
    return {name: round(1000 * len(p.findall(text)) / words, 2) for name, p in _FRAME_PATTERNS.items()}


def densest_sentence(text: str, frame: str) -> str:
    """The sentence with the most of a theory's vocabulary, as an illustration; ties go to the earlier sentence."""
    pattern = _FRAME_PATTERNS[frame]
    best, best_count = "", 0
    for sentence in SENTENCE.split(text):
        sentence = " ".join(sentence.split())
        if 60 <= len(sentence) <= 400 and not SALUTATION.search(sentence):
            count = len(pattern.findall(sentence))
            if count > best_count:
                best, best_count = sentence, count
    # a typographic or soft hyphen followed by a space is the pdf's line break inside a word
    return re.sub(r"(\w)[\u2010\u00ad] (\w)", r"\1\2", best)
