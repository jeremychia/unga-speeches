"""How a speech describes the wars in Ukraine and Gaza: the strongest framing it uses, and the sentence that shows it.

Each classifier reads the sentences that name the place, and the sentences either side, and returns the first framing it finds,
strongest first. The evidence sentence is returned so every label can be checked against the text."""

import re
import unicodedata

from unga_speeches.analysis import lexicons

UKRAINE_CLASSES = [
    "blames Russia or calls it aggression",
    "names the war or calls for talks only",
    "uses Russia's framing",
    "mentions Ukraine only",
    "does not mention Ukraine",
]
GAZA_CLASSES = [
    "calls it genocide",
    "criticises Israel's conduct",
    "humanitarian or peace language only",
    "does not mention Gaza or Palestine",
]

UKRAINE = re.compile(r"\bukrain", re.I)
RUSSIAS_FRAMING = re.compile(
    r"kyiv regime|kiev regime|ukrainian regime|neo-?nazi|special military operation|nato(?:'s|’s)? (?:expansion|enlargement)|expansion of nato|eastward expansion",
    re.I,
)
# russia as the one acting: russia, putin, the kremlin or moscow, then within six words a word of violence; a bare "war" counts only
# as "russia's war", since "russia would win this war" names a side, not an aggressor
RUSSIA_ACTS = re.compile(
    r"\b(?:russia|putin|kremlin|moscow)\w*(?:\W+[\w’'-]+){0,6}?\W+"
    r"(?:wag(?:e|es|ing)\b|attack|aggress|invasion|invad|occup|annex|bomb|strike|shelling|targeting|missile|drone|illegal|brutal|unprovoked|withdraw)"
    r"|\b(?:russia|putin)\w*(?:'s|’s)(?:\W+[\w’'-]+){0,4}?\W+war\b"
    r"|\b(?:russia|putin|kremlin|moscow)\w*(?:\W+[\w’'-]+){0,6}?\W+responsib\w*\W+for\W+(?:this|the)\W+(?:war|aggression|invasion)\b"
    r"|\b(?:war|aggression|invasion|attacks?|conquest)\b(?:\W+[\w’'-]+){0,8}?\W+by (?:the )?(?:russia|putin|kremlin|moscow)",
    re.I,
)
# wording that puts the two countries on the same footing, as in "the war between Russia and Ukraine"
EVEN_HANDED = re.compile(
    r"russia[- /]ukrain|ukrain\w*[- /]russia|between russia and ukraine|between ukraine and russia|russia and ukraine|ukraine and russia|russian-ukrainian|ukrainian-russian",
    re.I,
)
AGGRESSION = re.compile(r"\baggression\b|\binvasion\b|\baggressor|war (?:against|on) ukraine", re.I)
WAR_OR_TALKS = re.compile(
    r"\bwar\b|conflict|crisis|hostilities|fighting|tensions?|all parties|both parties|settlement|negotiat|peace talks|ceasefire|cease-fire|dialogue|diploma",
    re.I,
)
# a sentence that names two or more other trouble spots lists Ukraine in passing rather than describing the war
OTHER_PLACES = re.compile(
    r"\bgaza|palestin|israel|\bsudan|\biran|middle east|yemen|haiti|congo|\bdrc\b|myanmar|sahel|lebanon|syria|afghanistan|libya|somalia",
    re.I,
)

GAZA = re.compile(r"\bgaza\b|\bpalestin|west bank", re.I)
GENOCIDE = re.compile(r"genocid", re.I)
# a charge quoted in order to reject it, or a genocide from another time and place
DENIAL_OR_HISTORY = re.compile(
    r"what genocidal|\baccus|\blie\b|\blies\b|libel|slander|false|so-called|srebrenica|rwanda|holocaust|khmer|bosnian|armenian|cambodia|hate speech",
    re.I,
)
_CONDUCT = (
    r"(?:violat|crime|kill|murder|starv|famine|displac|settlements|settlement (?:activit|expansion|construction|building)|settlers|annex|demoli"
    r"|collective punishment|apartheid|ethnic cleansing|massacre|bombard|aggress|blockade|targeting|atrocit|impunity|illegal|use of force)"
)
_ISRAEL = r"(?:israel|netanyahu|occupying power|occupation forces|israeli occupation|zionis)"
# israel as the one acting: israel first and the act within eighteen words, not in the passive ("was killed"); or the act done "by" israel
ISRAEL_ACTS = re.compile(
    rf"\b{_ISRAEL}\w*(?:\W+[\w’'-]+){{0,18}}?\W+(?<!was )(?<!were )(?<!been )(?<!being ){_CONDUCT}"
    rf"|{_CONDUCT}\w*(?:\W+[\w’'-]+){{0,8}}?\W+by (?:the )?(?:israel|israeli|occupation|occupying)",
    re.I,
)
# "the war on gaza" puts the blame on one side without naming israel
WAR_ON_GAZA = re.compile(r"war (?:on|against) (?:gaza|the palestinian)", re.I)
NAMES_HAMAS = re.compile(
    r"\bhamas\b|hostages?|7 october|october 7|7th of october|october the 7th|seventh of october"
    r"|terrorist attacks? (?:on|against) israel|israel(?:'s|’s) right to (?:defend|self-defen[cs]e|exist)",
    re.I,
)


def _sentences(text: str) -> list[str]:
    """the speech's sentences, with ligatures such as "ﬂ" unfolded so that words match."""
    return lexicons.SENTENCE.split(unicodedata.normalize("NFKC", text))


def _around(sents: list[str], idx: list[int]) -> list[str]:
    return [sents[j] for i in idx for j in (i - 1, i, i + 1) if 0 <= j < len(sents)]


def ukraine(text: str) -> tuple[str, str]:
    """The strongest framing a speech uses for the war in Ukraine, and the sentence that shows it."""
    sents = _sentences(text)
    idx = [i for i, s in enumerate(sents) if UKRAINE.search(s)]
    if not idx:
        return UKRAINE_CLASSES[4], ""
    on = [sents[i] for i in idx]
    near = _around(sents, idx)
    if s := next((s for s in near if RUSSIAS_FRAMING.search(s)), None):
        return UKRAINE_CLASSES[2], s
    if s := next((s for s in sents if RUSSIA_ACTS.search(s) and not EVEN_HANDED.search(s)), None):
        return UKRAINE_CLASSES[0], s
    if s := next((s for s in on if AGGRESSION.search(s) and not EVEN_HANDED.search(s)), None):
        return UKRAINE_CLASSES[0], s
    if s := next((s for s in on if WAR_OR_TALKS.search(s) and len({m.group(0).lower()[:4] for m in OTHER_PLACES.finditer(s)}) < 2), None):
        return UKRAINE_CLASSES[1], s
    return UKRAINE_CLASSES[3], on[0]


def gaza(text: str) -> dict:
    """The strongest criticism of Israel a speech makes about Gaza, whether it names Hamas or the hostages, and the sentences that show both."""
    sents = _sentences(text)
    idx = [i for i, s in enumerate(sents) if GAZA.search(s)]
    if not idx:
        return {"class": GAZA_CLASSES[3], "evidence": "", "hamas": False, "hamas_evidence": ""}
    near = _around(sents, idx)
    hamas = next((s for s in near if NAMES_HAMAS.search(s)), "")
    genocide = next((s for s in near if GENOCIDE.search(s) and not DENIAL_OR_HISTORY.search(s)), "")
    conduct = next(
        (
            s
            for s in near
            if (WAR_ON_GAZA.search(s) or ISRAEL_ACTS.search(s))
            and not DENIAL_OR_HISTORY.search(s)
            and not NAMES_HAMAS.search(s)
            and not re.search(r"terroris", s, re.I)
        ),
        "",
    )
    if genocide:
        cls, evidence = GAZA_CLASSES[0], genocide
    elif conduct:
        cls, evidence = GAZA_CLASSES[1], conduct
    else:
        cls, evidence = GAZA_CLASSES[2], sents[idx[0]]
    return {"class": cls, "evidence": evidence, "hamas": bool(hamas), "hamas_evidence": hamas}
