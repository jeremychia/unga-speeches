"""Write the session's analysis page to site/: the figures from analyse.py, and prose built around them."""

import html
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

from unga_speeches.analysis import analyse, lexicons, topics
from unga_speeches.config import OUTPUT_DIR, PROJECT_ROOT

SITE_DIR = PROJECT_ROOT / "site"
TEMPLATE = Path(__file__).with_name("page.html")
REPO = "https://github.com/jeremychia/unga-speeches"
REGIONS = analyse.REGIONS

LENS_TEXT = {
    "Realism": (
        "States are the main actors, the system has no government above them, and so each pursues power and security. "
        "Realists expect speeches to dwell on threats, force, deterrence and the balance of power."
    ),
    "Liberal institutionalism": (
        "Cooperation is possible and lasting when it runs through institutions, law and trade, which make promises credible. "
        "Liberals expect speeches to appeal to the Charter, multilateralism, treaties and reform."
    ),
    "Constructivism": (
        "What states want depends on who they believe they are. Identity, history, norms and shared values shape interests, "
        "so constructivists read speeches for how a state tells its own story."
    ),
    "Critical and postcolonial": (
        "The order itself distributes power and wealth unequally, and its history of empire still shapes it. "
        "These approaches read speeches for grievance about structure: colonialism, reparations, sanctions, debt and double standards."
    ),
}


def _p(text: str) -> str:
    return f"<p>{text}</p>"


def _e(text) -> str:
    return html.escape(str(text))


def _pct(v: float) -> str:
    return f"{round(100 * v)}%"


def _normalise(text: str) -> str:
    return " ".join(re.sub(r"[‐­]\s+", "", text).split())


def _verbatim_texts(session: int) -> dict[str, list[str]]:
    texts: dict[str, list[str]] = {}
    with (OUTPUT_DIR / f"texts_{session}.jsonl").open(encoding="utf-8") as f:
        for line in f:
            t = json.loads(line)
            if t["text"]:
                texts.setdefault(t["slug"], []).append(_normalise(t["text"]))
    return texts


def _check_quotes(d: dict) -> None:
    """Every quote must appear word for word in a stored source text; a quote that does not stops the build."""
    sources = _verbatim_texts(d["session"])
    for frame, examples in d["frames"]["exemplars"].items():
        for e in examples:
            if e["quote"] and not any(_normalise(e["quote"]) in t for t in sources.get(e["slug"], [])):
                raise ValueError(f"quote for {e['delegation']} ({frame}) is not in its source text: {e['quote'][:80]}")


def _region_of_most(rows: list[dict], key: str, value: str) -> tuple[str, int, int]:
    members = [r for r in rows if r[key] == value]
    region, count = Counter(r["region"] for r in members).most_common(1)[0]
    return region, count, len(members)


def build(session: int) -> Path:
    d = analyse.build(session)
    _check_quotes(d)
    unlabelled = [t["label"] for t in d["topics"] if t["label"].startswith(topics.UNLABELLED)]
    if unlabelled:
        raise ValueError(f"topics need a label in analysis/topics.py before publishing: {unlabelled}")
    rows, o, dist, an = d["speeches"], d["overview"], d["distributions"], d["anomalies"]
    issues = {i["name"]: i for i in d["issues"]}
    frames = d["frames"]
    region_frames = {g["group"]: g for g in frames["by_group"]["region"]}
    days = dist["days"]

    lede = (
        f"All {o['speeches']} speeches with an English text from the {d['year']} general debate, read by a deterministic pipeline. "
        "Topics, issues, readability and four lenses from international relations theory. Every figure is computed from the texts, "
        "and every quote is checked word for word against its source."
    )

    who = _p(
        f"<b>{_pct(o['heads_share'])} of member states sent a head of state or government.</b> The rank falls through the week: "
        f"{_pct(days[0]['heads_share'])} of the first day's speakers held the top office, and {_pct(days[-1]['heads_share'])} of the last day's. "
        "The debate's speaking order puts heads of state first, so the final days belong to ministers and ambassadors."
    )

    regional = []
    for t in d["topics"]:
        region, count, total = _region_of_most(rows, "topic", t["label"])
        if count / total > 0.5:
            regional.append(t["label"])
    topics_html = _p(
        "<b>Most topics are one region's agenda, not a global theme.</b> "
        f"In {len(regional)} of the {len(d['topics'])} topics, more than half the speeches come from a single region. "
        "The Pacific's oceans and fossil fuels, the Caribbean's reparatory justice, the Sahel's security and the Gulf's regional stability each stand apart."
    ) + _p(
        "The topics come from a statistical model (non-negative matrix factorisation) that finds groups of words used together across speeches. "
        "The model fixes the groups; the names are ours, chosen from each topic's top terms, which the table below lists."
    )

    first, second, *rest = d["issues"]
    ai, gaza, ukr = issues["Artificial intelligence"], issues["Gaza and Palestine"], issues["Ukraine"]
    issues_html = _p(
        f"<b>{_e(first['name'])} and {_e(second['name'].lower())} were the most widely raised issues.</b> {_pct(first['share'])} of speeches mention the first "
        f"and {_pct(second['share'])} the second, ahead of {_e(rest[0]['name'])} ({_pct(rest[0]['share'])}) and {_e(rest[1]['name'])} ({_pct(rest[1]['share'])})."
    ) + _p(
        f"Wars are regional in attention. Ukraine appears in {_pct(ukr['by_region']['Europe'])} of European speeches and {_pct(ukr['by_region']['Africa'])} of African ones. "
        f"Gaza appears in {_pct(gaza['by_region']['Europe'])} of European and {_pct(gaza['by_region']['Asia'])} of Asian speeches, "
        f"but {_pct(gaza['by_region']['Oceania'])} of Pacific ones. {issues['The next Secretary-General']['speeches']} speeches mention choosing the next Secretary-General, "
        "whose term begins in 2027."
    )

    distributions_html = _p(
        f"<b>The median speech runs to {o['words_median']:,} words, about 15 to 20 minutes.</b> "
        f"The delegations' written statements read at a median Flesch–Kincaid grade of {dist['grade_median']}, around first-year university, "
        f"with {dist['sentence_words_median']} words to a sentence. Transcripts are not scored, because a machine sets their punctuation."
    ) + _p(
        f"Speakers deliver most of what they file: the median speech says {_pct(dist['delivered_median'])} of its written statement. "
        "The gaps come from speeches cut short and from speakers who switch languages mid-speech."
    )

    longest = an["length"][0]
    complex_ = an["readability"][0] if an["readability"] else None
    pair = an["similar_pairs"][0]
    least = an["least_delivered"][:2]
    multipolar_users = [r["delegation"] for r in rows if "Multipolar" in r["markers"]]
    notable = [
        (
            "The longest speech",
            f"{_e(longest['delegation'])} spoke for {longest['words']:,} words, {longest['words'] / o['words_median']:.1f} times the median.",
        ),
        (
            "The densest prose",
            f"{_e(complex_['delegation'])}'s statement averages {complex_['sentence_words']} words a sentence, a reading grade of {complex_['grade']}."
            if complex_
            else "",
        ),
        (
            "The most alike",
            f"{_e(pair['a'])} and {_e(pair['b'])} share the most vocabulary. Their longest shared passage is {pair['longest_shared_words']} words, so the likeness is in theme, not copied text. Both belong to the Alliance of Sahel States."
            if {pair["a"], pair["b"]} == {"Burkina Faso", "Mali"}
            else f"{_e(pair['a'])} and {_e(pair['b'])} share the most vocabulary; their longest shared passage is {pair['longest_shared_words']} words.",
        ),
        (
            "The most distinctive",
            f"{_e(an['most_distinctive'][0]['delegation'])} and {_e(an['most_distinctive'][1]['delegation'])} share the least vocabulary with everyone else.",
        ),
        (
            "Filed but not said",
            f"{_e(least[0]['delegation'])} said {_pct(least[0]['delivered_share'])} of its filed text and {_e(least[1]['delegation'])} {_pct(least[1]['delivered_share'])}, the lowest of the debate.",
        ),
        (
            "AI everywhere",
            f"{ai['speeches']} of {o['speeches']} speeches mention AI, more than mention Gaza, Ukraine or Sudan."
            if ai["speeches"] > max(gaza["speeches"], ukr["speeches"], issues["Sudan"]["speeches"])
            else "",
        ),
        (
            "A rare word",
            f"Only {len(multipolar_users)} speeches say “multipolar”, from {_e(', '.join(multipolar_users[:6]))} and others. The word has no single camp.",
        ),
        ("Taiwan", f"{issues['Taiwan']['speeches']} speeches mention Taiwan, which has no seat and gives no speech."),
    ]
    notable_html = "".join(f"<div class='callout'><b>{t}</b>{body}</div>" for t, body in notable if body)

    theory_html = _p(
        "<b>Europe speaks the language of security; Africa speaks the language of institutions and justice.</b> "
        f"European speeches use realist vocabulary at {region_frames['Europe']['Realism']:.1f} words per 1,000, against {region_frames['Africa']['Realism']:.1f} in African ones. "
        f"African speeches lead on liberal-institutional vocabulary ({region_frames['Africa']['Liberal institutionalism']:.1f} per 1,000) "
        f"and use critical and postcolonial vocabulary {region_frames['Africa']['Critical and postcolonial'] / region_frames['Europe']['Critical and postcolonial']:.1f} times as often as European ones."
    ) + _p(
        "Each lens is measured by counting its signature words, listed with each lens below. This shows the vocabulary a speech leans on, "
        "not the argument it makes: the same word can serve different theories. The readings of each lens are ours, and the quotes are the speakers' own."
    )

    lenses = []
    for f in frames["names"]:
        examples = "".join(
            f"<blockquote><p>“{_e(e['quote'])}”</p><cite>{_e(e['speaker'])}, {_e(e['delegation'])} · "
            f"{'the UN interpreters’ English' if e['english_kind'] == 'transcript' else 'the delegation’s English text'} · <a href='{_e(e['url'])}'>source</a></cite></blockquote>"
            for e in frames["exemplars"][f]
            if e["quote"]
        )
        tags = "".join(f"<span class='tag'>{_e(_readable_pattern(t))}</span>" for t in lexicons.FRAMES[f])
        lenses.append(
            f"<div class='lens'><h3>{_e(f)}</h3>{_p(_e(LENS_TEXT[f]))}{_lens_reading(f, d)}"
            f"<p class='small'>Vocabulary counted:</p><div>{tags}</div><h3 style='font-size:.95rem'>Where it is strongest</h3>{examples}</div>"
        )
    lenses.append(f"<div class='lens'><h3>Reading the debate as a whole</h3>{_synthesis(d)}</div>")

    method = "".join(
        _p(t)
        for t in [
            f"<b>Texts.</b> Each speech's English comes from the delegation's written statement where one exists ({o['english_kinds'].get('statement', 0)} speeches), "
            f"and otherwise from the UN's machine transcript of the English interpretation ({o['english_kinds'].get('transcript', 0)}). "
            "A transcript of an interpreted speech is the interpreters' English, not the speaker's words.",
            "<b>Topics.</b> TF-IDF over single words and word pairs, with names, salutations and transcript filler removed, and a twelve-topic NMF model with a fixed seed. "
            "Topic models shift when the texts change even slightly, so the labels are reviewed each time the page is rebuilt; the build stops if a topic has none.",
            "<b>Readability.</b> Flesch–Kincaid grade and words per sentence from the textstat library, on written statements only.",
            "<b>Theory lenses.</b> Word lists matched as prefixes and counted per 1,000 words, then standardised across speeches. "
            "Lists are in the source code. “Trust” is excluded because it is this session's theme.",
            "<b>Outliers.</b> A speech is an outlier when it sits 2.5 standard deviations from the mean of its kind of text.",
            f"<b>Reproduce it.</b> The pipeline, the analysis code and the data are at <a href='{REPO}'>{REPO.removeprefix('https://')}</a>. "
            "The <a href='data.json'>figures behind this page</a> are published beside it.",
        ]
    )
    footer = f"Built {date.today().isoformat()} from <a href='{REPO}'>jeremychia/unga-speeches</a>. Speech texts belong to their publishers; the code is under Apache 2.0."

    page = TEMPLATE.read_text(encoding="utf-8")
    for key, value in {
        "__LEDE__": _e(lede),
        "__WHO__": who,
        "__TOPICS__": topics_html,
        "__ISSUES__": issues_html,
        "__DISTRIBUTIONS__": distributions_html,
        "__NOTABLE__": notable_html,
        "__THEORY__": theory_html,
        "__LENSES__": "".join(lenses),
        "__METHOD__": method,
        "__FOOTER__": footer,
        "__DATA__": json.dumps(d, ensure_ascii=False).replace("</", "<\\/"),
    }.items():
        page = page.replace(key, value)
    SITE_DIR.mkdir(exist_ok=True)
    (SITE_DIR / "index.html").write_text(page, encoding="utf-8")
    (SITE_DIR / "data.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    (SITE_DIR / ".nojekyll").write_text("")
    return SITE_DIR / "index.html"


def _readable_pattern(pattern: str) -> str:
    """A word-list pattern as a reader would write it: "defen[cs]e" becomes "defence", "treat(y|ies)" becomes "treaty"."""
    pattern = pattern.replace("\\b", "")
    pattern = re.sub(r"\[(\w)\w*\]", r"\1", pattern)
    return re.sub(r"\((\w+)\|\w+\)", r"\1", pattern)


def _lens_reading(frame: str, d: dict) -> str:
    """What the figures show for one lens, in sentences built from those figures."""
    region = {g["group"]: g for g in d["frames"]["by_group"]["region"]}
    markers = {m["name"]: m for m in d["markers"]}
    ranked = sorted(REGIONS, key=lambda r: -region[r][frame])
    lean = d["frames"]["lean_by_region"]

    def share(r: str) -> float:
        return lean[r].get(frame, 0) / sum(lean[r].values()) if lean.get(r) else 0

    spread = {f: max(region[r][f] for r in REGIONS) / max(0.01, min(region[r][f] for r in REGIONS)) for f in d["frames"]["names"]}
    charter_or_law = d["overview"]["charter_or_law"]
    no_double_standards = [r for r in REGIONS if markers["Double standards"]["by_region"][r] == 0]
    issues = {i["name"]: i for i in d["issues"]}
    base = (
        f"<b>Strongest in {ranked[0]} ({region[ranked[0]][frame]:.1f} per 1,000 words), weakest in {ranked[-1]} ({region[ranked[-1]][frame]:.1f}).</b> "
        f"{_pct(share(ranked[0]))} of {ranked[0]}'s speeches lean this way."
    )
    readings = {
        "Realism": (
            f" The vocabulary gathers where war is close. Ukraine appears in {_pct(issues['Ukraine']['by_region']['Europe'])} of European speeches, "
            f"and nuclear weapons in {_pct(markers['Nuclear']['by_region']['Europe'])} of European and {_pct(markers['Nuclear']['by_region']['Asia'])} of Asian ones, "
            f"against {_pct(markers['Nuclear']['by_region']['Africa'])} of African ones. Much of the word “security” also covers food, climate and health, which flatters this count."
        ),
        "Liberal institutionalism": (
            f" Its words are the debate's common ground: {_pct(charter_or_law / len(d['speeches']))} of speeches invoke the UN Charter or international law. "
            f"The difference lies in use. Some speakers defend today's institutions; others, such as Liberia, cite them to demand a larger say. "
            f"{issues['Security Council reform']['speeches']} speeches call for Security Council reform, and {markers['Security Council veto']['speeches']} name the veto."
        ),
        "Constructivism": (
            (
                " It is the most evenly spread lens: every region uses its vocabulary at a similar rate. "
                if min(spread, key=spread.get) == "Constructivism"
                else " "
            )
            + "History, identity and dignity are how every state explains itself, whatever its interests."
        ),
        "Critical and postcolonial": (
            f" Grievance about the order's structure comes mainly from Africa and the Caribbean. Reparations appear in {_pct(markers['Reparations']['by_region']['Americas'])} of speeches from the Americas "
            f"and {_pct(markers['Reparations']['by_region']['Africa'])} of African ones. {_pct(markers['Unilateral sanctions']['by_region']['Africa'])} of African speeches criticise sanctions, "
            f"and {_pct(markers['Double standards']['by_region']['Africa'])} accuse others of double standards"
            + (f", a charge no speaker from {' or '.join(no_double_standards)} makes." if no_double_standards else ".")
        ),
    }
    return _p(base + readings[frame])


def _synthesis(d: dict) -> str:
    markers = {m["name"]: m for m in d["markers"]}
    lean = d["frames"]["lean_counts"]
    no_lean = lean.get(analyse.NO_LEAN, 0)
    return "".join(
        _p(t)
        for t in [
            f"<b>No single theory owns the debate.</b> Of {sum(lean.values())} speeches, {no_lean} lean towards none of the four lenses. "
            "The rest divide close to evenly among them, so the debate is a mix of vocabularies rather than a contest between them.",
            "<b>Where a state stands shapes the words it reaches for.</b> Europe, with a war on its border, talks of security and deterrence. "
            "Africa, seeking more voice in institutions it did not design, talks of reform, law and justice. "
            "Small island states talk of the ocean and survival. The pattern fits realism's claim that position drives interest, "
            "and constructivism's claim that each region tells a different story about the same order.",
            f"<b>The vocabulary of a new order is rare.</b> “Multipolar” appears in {markers['Multipolar']['speeches']} speeches, “spheres of influence” in "
            f"{markers['Spheres of influence']['speeches']}, and “rules-based order” in {markers['Rules-based order']['speeches']}. "
            "Speakers argue about the order through its existing institutions rather than naming a replacement.",
        ]
    )
