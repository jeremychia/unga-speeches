"""Classify a speaker's title into the rank of office they spoke in."""

import re

# first match wins, so narrower titles come before the broader ones they contain
RULES: list[tuple[str, str]] = [
    ("un_official", r"secretary-general|president of the general assembly"),
    ("regional_organisation", r"president of the european (council|commission)|chair(person)? of the african union commission"),
    ("other_official", r"head of (the )?administration of the president|chief of staff"),
    ("junior_minister", r"vice[- ]minister|deputy minister|state secretary|secretary of state for|minister of state(?! and for foreign)|parliamentary secretary"),
    ("deputy_head", r"vice[- ]president|deputy prime minister|vice prime minister|first deputy|crown prince|vice[- ]chair"),
    ("head_of_government", r"prime minister|taoiseach|president of the government|president of the council of ministers|chairman of the council of ministers|head of (the )?govern?ment|chancellor|premier\b|chief adviser|chief executive"),
    ("head_of_state", r"\bpresident\b|head of state|\bking\b|\bqueen\b|\bamir\b|\bemir\b|emperor|sultan|grand duke|prince\b|c?h?airman of the presidency|member of the presidency|chair of the presidential council|chairman of the presidential council|chairman of the assembly presidium|governor-general|captain regent"),
    ("foreign_minister", r"foreign affairs|foreign minister|external affairs|external relations|international relations|european and international affairs|foreign relations|relations with states"),
    ("other_minister", r"\bminister\b"),
    ("diplomat", r"permanent representative|ambassador|charg[ée] d'affaires|head of (the )?delegation|chair(man)? of (the )?delegation|un representative|^delegation$"),
]

# offices whose title reads differently from the rank they hold
DELEGATION_OVERRIDES = {
    # the cardinal secretary of state heads the holy see's government
    ("holy-see", "secretary of state"): "head_of_government",
}

ROLE_GROUP = {
    "head_of_state": "head_of_state_or_government",
    "head_of_government": "head_of_state_or_government",
    "deputy_head": "deputy_head",
    "foreign_minister": "foreign_minister",
    "junior_minister": "other_minister",
    "other_minister": "other_minister",
    "diplomat": "diplomat",
    "other_official": "other",
    "regional_organisation": "not_a_state",
    "un_official": "not_a_state",
    "unclassified": "unclassified",
}


def classify(title: str | None, slug: str | None = None) -> str:
    if not title:
        return "unclassified"
    normalised = re.sub(r"\s+", " ", title.lower()).strip()
    if (slug, normalised) in DELEGATION_OVERRIDES:
        return DELEGATION_OVERRIDES[(slug, normalised)]
    for role, pattern in RULES:
        if re.search(pattern, normalised):
            return role
    return "unclassified"
