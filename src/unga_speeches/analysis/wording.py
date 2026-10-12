"""How a speech describes the wars in Ukraine and Gaza: the strongest framing it uses, and the sentence that shows it.

Each classifier reads the sentences that name the place, and the sentences either side, and returns the first framing it finds,
strongest first. The evidence sentence is returned so every label can be checked against the text."""

import re
import unicodedata

UKRAINE_CLASSES = [
    "blames Russia or calls it aggression",
    "names the war or calls for talks only",
    "uses Russia's framing",
    "mentions Ukraine only",
    "does not mention Ukraine",
]
GAZA_CLASSES = ["calls it genocide", "criticises Israel's conduct", "no criticism of Israel", "does not mention Gaza or Palestine"]

# a sentence ends at . ! or ? before a capital, or at a bullet; not after a title such as "Mr." or "H.E."
SENTENCE = re.compile(r"(?<!\bMr\.)(?<!\bMs\.)(?<!\bDr\.)(?<!\bSt\.)(?<!Mrs\.)(?<!H\.E\.)(?<=[.!?])\s+(?=[A-Z\"“‘(])|\s*[•●▪]\s*")
_WORDS = r"(?:\W+[\w’'-]+)"

UKRAINE = re.compile(r"\bukrain|\bkyiv\b|\bkiev\b", re.I)
RUSSIAS_FRAMING = re.compile(
    r"kyiv regime|kiev regime|ukrainian regime|neo-?nazi|special military operation|last ukrainian|indivisible security|proxy war|collective west",
    re.I,
)
# nato's growth counts as russia's framing only when it is offered as a cause or a threat
NATO_EXPANSION = re.compile(r"nato(?:'s|’s)? (?:expansion|enlargement)|expansion of nato|eastward expansion", re.I)
NATO_AS_CAUSE = re.compile(r"threat|provok|root cause|encircl|led to|caus", re.I)
# russia's framing quoted in order to reject it
REBUTTAL = re.compile(r"so-called|\blies?\b|false|pretext|propaganda|disinformation|myth|claims?\b", re.I)
_RUSSIA = r"\b(?:russia(?:n federation)?(?:'s|’s)?|russian(?!s)|putin(?:'s|’s)?|kremlin|moscow)"
# russia as the one acting: russia, then within six words a word of violence; a bare "war" counts only as "russia's war", since
# "russia would win this war" names a side, not an aggressor; and "russians" are left out, since russians can be victims too
RUSSIA_ACTS = re.compile(
    rf"{_RUSSIA}{_WORDS}{{0,6}}?\W+"
    r"(?:wag(?:e|es|ing)\b|attack|aggress|invasion|invad|occup|annex|bomb|strike|shelling|targeting|missile|drone|illegal|brutal|unprovoked|withdraw)"
    rf"|\b(?:russia|putin)(?:'s|’s){_WORDS}{{0,4}}?\W+war\b"
    rf"|{_RUSSIA}{_WORDS}{{0,6}}?\W+responsib\w*\W+for\W+(?:this|the)\W+(?:war|aggression|invasion)\b"
    rf"|\b(?:war|aggression|invasion|attacks?|conquest)\b{_WORDS}{{0,8}}?\W+by (?:the )?(?:russia|putin|kremlin|moscow)",
    re.I,
)
# wording that puts the two countries on the same footing, as in "the war between Russia and Ukraine"
EVEN_HANDED = re.compile(
    r"russia[- /]ukrain|ukrain\w*[- /]russia|between russia and ukraine|between ukraine and russia|russia and ukraine|ukraine and russia|russian-ukrainian|ukrainian-russian",
    re.I,
)
AGGRESSION = re.compile(r"\baggression\b|\binvasion\b|\baggressor|war (?:against|on) ukraine", re.I)
# aggression laid at someone else's door: ukraine, nato, the west, the united states or israel
OTHER_AGGRESSOR = re.compile(
    r"ukrainian aggression|nato(?:'s|’s)? aggression|western aggression|israeli aggression|american aggression"
    r"|aggression (?:of|by) (?:the )?(?:ukrain|nato|west|united states|israel)|aggression against (?!ukrain)\w+",
    re.I,
)
TALKS = re.compile(r"\bpeace|all parties|both parties|settlement|negotiat|ceasefire|cease-fire|dialogue|diploma", re.I)
NAMES_WAR = re.compile(r"\bwar\b|conflict|crisis|hostilities|fighting|tensions?", re.I)
# other trouble spots: a sentence that only names the war alongside one of these lists Ukraine in passing
OTHER_PLACES = {
    "middle east": r"\bgaza|palestin|israel|middle east|west bank|lebanon|syria|yemen|\biran|gulf",
    "africa": r"\bsudan|congo|\bdrc\b|sahel|libya|somalia|ethiopia",
    "elsewhere": r"haiti|myanmar|afghanistan",
}

GAZA = re.compile(r"\bgaza(?:ns?)?\b|\bpalestin|west bank", re.I)
GENOCIDE = re.compile(r"genocid", re.I)
# the court case's title, and the charge quoted in order to reject it
CASE_OR_DENIAL = re.compile(
    r"convention on the prevention|crime of genocide in the gaza strip|application of the convention|genocide convention"
    r"|what genocidal|blood libel|\blibel|slander|so-called genocide|genocide (?:lie|libel|hoax)|false(?:ly)? accus|hate speech",
    re.I,
)
# genocides elsewhere; these rule a sentence out only when it does not also name gaza, palestine or israel, so a comparison still counts
ELSEWHERE = re.compile(r"srebrenica|rwanda|holocaust|khmer|bosnia|armenia|cambodia|darfur|fasher|\bsudan|rohingya|myanmar|yazidi", re.I)
NAMES_THIS_WAR = re.compile(r"\bgaza|palestin|israel|netanyahu|zionis", re.I)
_ISRAEL = r"(?:israel|netanyahu|occupying power|occupying (?:military )?force|occupation forces|israeli occupation|zionis)"
_CONDUCT = (
    r"(?:violat|crime|kill|murder|starv|famine|displac|settlements|annex|demoli|collective punishment|apartheid|ethnic cleansing|massacre|bombard"
    r"|aggress|blockade|siege|targeting|atrocit|impunity|illegal|unlawful|use of force|strike|destr|state terror)"
)
ISRAEL_TERM = re.compile(rf"\b{_ISRAEL}", re.I)
CONDUCT = re.compile(_CONDUCT, re.I)
# between israel and the act, a passive ("was killed") or a shared subject ("israel and palestine must end violations") means israel is not the actor
NOT_THE_ACTOR = re.compile(r"\b(?:was|were|been|being)\b|\b(?:and|or) (?:the )?palestin|\bhamas|all parties|both sides|both parties", re.I)
ACT_BY_ISRAEL = re.compile(rf"{_CONDUCT}\w*{_WORDS}{{0,8}}?\W+by (?:the )?(?:israel|israeli|occupation|occupying)", re.I)
# criticism that needs no named actor: settlements in occupied land, the war "on" gaza, israeli strikes, the government's actions
CRITICISM = re.compile(
    r"(?:illegal|unlawful) settlement|settlement (?:expansion|activit|construction)|expansion of (?:illegal )?settlements|settler violence"
    r"|war (?:on|against) (?:gaza|the palestinian)|israeli (?:strikes|bombardment|attacks|military operations)"
    r"|israeli government(?:'s|’s)? actions|actions of the israeli government|state terrorism",
    re.I,
)
NAMES_HAMAS = re.compile(
    r"\bhamas\b|hostages?|7 october|october 7|7th of october|october the 7th|seventh of october"
    r"|terrorist attacks? (?:on|against) israel|israel(?:'s|’s) right to (?:defend|self-defen[cs]e|exist)",
    re.I,
)


def _sentences(text: str) -> list[str]:
    """the speech's sentences, with ligatures such as "ﬂ" unfolded so that words match."""
    return [s for s in SENTENCE.split(unicodedata.normalize("NFKC", text)) if s and s.strip()]


def _around(sents: list[str], idx: list[int], width: int = 1) -> list[str]:
    keep = sorted({j for i in idx for j in range(i - width, i + width + 1) if 0 <= j < len(sents)})
    return [sents[j] for j in keep]


def _other_places(s: str) -> int:
    return sum(bool(re.search(p, s, re.I)) for p in OTHER_PLACES.values())


def ukraine(text: str) -> tuple[str, str]:
    """The strongest framing a speech uses for the war in Ukraine, and the sentence that shows it."""
    sents = _sentences(text)
    idx = [i for i, s in enumerate(sents) if UKRAINE.search(s)]
    if not idx:
        return UKRAINE_CLASSES[4], ""
    on = [sents[i] for i in idx]
    near = _around(sents, idx)
    framing = next(
        (
            s
            for s in near
            if (RUSSIAS_FRAMING.search(s) or (NATO_EXPANSION.search(s) and NATO_AS_CAUSE.search(s))) and not REBUTTAL.search(s)
        ),
        None,
    )
    if framing:
        return UKRAINE_CLASSES[2], framing
    if s := next((s for s in near if RUSSIA_ACTS.search(s) and not EVEN_HANDED.search(s)), None):
        return UKRAINE_CLASSES[0], s
    if s := next((s for s in on if AGGRESSION.search(s) and not EVEN_HANDED.search(s) and not OTHER_AGGRESSOR.search(s)), None):
        return UKRAINE_CLASSES[0], s
    if s := next((s for s in on if TALKS.search(s) or (NAMES_WAR.search(s) and not _other_places(s))), None):
        return UKRAINE_CLASSES[1], s
    return UKRAINE_CLASSES[3], on[0]


def _israel_acts(s: str) -> bool:
    """whether a sentence has israel doing something harmful or unlawful, rather than suffering it or sharing the blame."""
    if ACT_BY_ISRAEL.search(s):
        return True
    for actor in ISRAEL_TERM.finditer(s):
        after = s[actor.end() :]
        act = CONDUCT.search(after)
        if act and len(after[: act.start()].split()) <= 18 and not NOT_THE_ACTOR.search(after[: act.start()]):
            if not re.match(r"\w*\W+(?:\w+\W+){0,3}by (?!the israel|israel)", after[act.start() :], re.I):
                return True
    return False


def gaza(text: str) -> dict:
    """The strongest criticism of Israel a speech makes about Gaza, whether it names Hamas or the hostages, and the sentences that show both."""
    sents = _sentences(text)
    idx = [i for i, s in enumerate(sents) if GAZA.search(s)]
    if not idx:
        return {"class": GAZA_CLASSES[3], "evidence": "", "hamas": False, "hamas_evidence": ""}
    near = _around(sents, idx)
    hamas = next((s for s in _around(sents, idx, width=2) if NAMES_HAMAS.search(s)), "")
    genocide = next(
        (s for s in near if GENOCIDE.search(s) and not CASE_OR_DENIAL.search(s) and (NAMES_THIS_WAR.search(s) or not ELSEWHERE.search(s))),
        "",
    )
    conduct = next((s for s in near if CRITICISM.search(s) or _israel_acts(s)), "")
    if genocide:
        cls, evidence = GAZA_CLASSES[0], genocide
    elif conduct:
        cls, evidence = GAZA_CLASSES[1], conduct
    else:
        cls, evidence = GAZA_CLASSES[2], sents[idx[0]]
    return {"class": cls, "evidence": evidence, "hamas": bool(hamas), "hamas_evidence": hamas}
