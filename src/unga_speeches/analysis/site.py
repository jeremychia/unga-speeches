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


def _picture(name: str, alt: str) -> str:
    """A figure in its light and dark versions; the browser picks the one for the reader's theme."""
    ext = "png" if name.startswith("map-") else "svg"
    return (
        f"<picture><source srcset='figures/{name}-dark.{ext}' media='(prefers-color-scheme: dark)'>"
        f"<img src='figures/{name}-light.{ext}' alt='{_e(alt)}' loading='lazy'></picture>"
    )


def _figures(d: dict) -> None:
    from unga_speeches.analysis import figures

    out = SITE_DIR / "figures"
    out.mkdir(parents=True, exist_ok=True)
    rows, world = d["speeches"], figures.world()
    figures.trend_multiples(d["trends"], out, analyse.TREND_ISSUES)
    figures.issue_map(rows, world, out, "Artificial intelligence", "map-ai")
    figures.wars_map(rows, world, out)
    figures.leaders_trend(d["trends"], out)
    figures.rank_map(rows, world, out)
    figures.lens_dots(d["frames"]["by_group"]["region"], out, d["frames"]["names"])
    figures.lens_maps(rows, world, out, d["frames"]["names"])
    figures.length_swarm(rows, out, REGIONS)


def _year(trends: list[dict], year: int) -> dict:
    return next(t for t in trends if t["year"] == year)


def build(session: int) -> Path:
    d = analyse.build(session)
    _check_quotes(d)
    unlabelled = [t["label"] for t in d["topics"] if t["label"].startswith(topics.UNLABELLED)]
    if unlabelled:
        raise ValueError(f"topics need a label in analysis/topics.py before publishing: {unlabelled}")
    _figures(d)

    rows, o, dist, an, lead = d["speeches"], d["overview"], d["distributions"], d["anomalies"], d["leaders"]
    issues = {i["name"]: i for i in d["issues"]}
    markers = {m["name"]: m for m in d["markers"]}
    frames = d["frames"]
    region_frames = {g["group"]: g for g in frames["by_group"]["region"]}
    now, last = _year(d["trends"], d["year"]), _year(d["trends"], d["year"] - 1)
    y2022, y2023 = _year(d["trends"], 2022), _year(d["trends"], 2023)
    ai, cc, gaza, ukr, gulf = (
        issues[k] for k in ("Artificial intelligence", "Climate change", "Gaza and Palestine", "Ukraine", "Iran and the Gulf war")
    )
    americas = [r for r in rows if r["region"] == "Americas"]
    neither_americas = sum("Ukraine" not in r["issues"] and "Gaza and Palestine" not in r["issues"] for r in americas) / len(americas)
    law = o["charter_or_law"] / o["speeches"]
    ai_regions = ai["by_region"]
    regional = [t for t in d["topics"] if (lambda r: r[1] / r[2] > 0.5)(_region_of_most(rows, "topic", t["label"]))]
    china = next((p for p in lead["p5"] if p["iso3"] == "CHN"), None)
    g20_now, g20_last = now["g20_heads"], last["g20_heads"]
    first_year = min(t["year"] for t in d["trends"])
    climate_floor = min(t["Climate change"] for t in d["trends"])
    terrorism_lowest = now["Terrorism"] < min(t["Terrorism"] for t in d["trends"] if t["year"] != d["year"])

    title = "The world's attention has moved"
    kicker = (
        "In 2026 artificial intelligence became the one worry almost every country shares. "
        "The wars that filled recent debates shrank to the regions that live with them. "
        "And fewer of the most powerful leaders came to say so in person."
    )
    scqa = "".join(
        f"<div><b>{k}</b>{v}</div>"
        for k, v in [
            (
                "Situation",
                "Once a year, every UN member speaks to the world on equal terms. The debate decides nothing, which is why it is read so closely: it shows what each government wants the world to hear.",
            ),
            (
                "Complication",
                "This year's debate met with a war in the Gulf, the wars in Ukraine and Gaza unresolved, and the UN choosing its next Secretary-General.",
            ),
            ("Question", "What did governments choose to talk about, and what does that say about how they see the world?"),
            (
                "Answer",
                "They talked about AI far more, and about the old wars far less. Fewer of the powerful came. And they argued over the old rules rather than for new ones.",
            ),
        ]
    )
    messages = "".join(
        f"<li><a href='#{anchor}'>{head}</a><span>{body}</span></li>"
        for anchor, head, body in [
            (
                "agenda",
                "AI joined climate as the world's shared agenda",
                f"{_pct(ai['share'])} of speeches raised AI, up from {_pct(last['Artificial intelligence'])} in {last['year']} and {_pct(y2023['Artificial intelligence'])} in 2023.",
            ),
            (
                "wars",
                "The wars of recent years became regional stories",
                f"Gaza fell from {_pct(last['Gaza and Palestine'])} of speeches to {_pct(gaza['share'])}, and Ukraine from {_pct(y2022['Ukraine'])} in 2022 to {_pct(ukr['share'])}. Europe still names Ukraine; the Global South names Gaza.",
            ),
            (
                "leaders",
                "The most powerful were the least likely to come",
                f"{g20_now} of 19 G20 members sent their leader, down from {g20_last} in {last['year']}."
                + (f" China sent its {china['title']}." if china else ""),
            ),
            (
                "order",
                "States argued over the rules, not for a new order",
                f"{_pct(law)} invoked the UN Charter or international law. Only {markers['Multipolar']['speeches']} speeches said “multipolar”.",
            ),
        ]
    )

    why = _p(
        "Nothing is voted on in the general debate. Its value is as a signal. It is the one day each government chooses, unprompted, "
        "what to put before the rest of the world, and who to send to say it. Readers of the debate usually want answers to five questions, and this page takes them in turn."
    )
    questions = "".join(
        f"<div><b>{q}</b><span>{a}</span></div>"
        for q, a in [
            ("What is on the world's mind?", "The issues most governments raise unprompted are the world's working agenda."),
            ("Whose wars count?", "Which crises each region names shows whose suffering reaches the agenda."),
            ("Who showed up?", "Sending a head of state signals the UN matters; sending a deputy signals less."),
            (
                "How do states see the order?",
                "Words for the system, such as rules, reform or multipolarity, show who wants it kept and who wants it changed.",
            ),
            ("Who stands with whom?", "Speeches that sound alike point to shared positions and blocs."),
        ]
    )

    agenda = (
        _p(
            f"<b>In 2022, {_pct(y2022['Artificial intelligence'])} of speeches mentioned artificial intelligence. This year {_pct(ai['share'])} did.</b> "
            f"Only climate change is raised more often ({_pct(cc['share'])}), and it has been raised by at least {_pct(climate_floor)} of speeches in every year since {first_year}."
        )
        + _p(
            f"AI is raised in every region: by at least {_pct(min(ai_regions.values()))} of the speeches in each, led by Europe at {_pct(ai_regions['Europe'])}. "
            f"Terrorism went the other way: {_pct(now['Terrorism'])} of speeches mentioned it"
            + (f", the lowest since at least {first_year}." if terrorism_lowest else ".")
        )
        + _p(
            "<span class='so-what'>So what:</span> governments now bring AI to the UN as a shared question of rules and risk, not only as a matter for technology firms or the richest economies."
        )
    )

    wars = _p(
        f"<b>Attention to the wars of recent years is falling.</b> Gaza fell from {_pct(last['Gaza and Palestine'])} of speeches in {last['year']} to {_pct(gaza['share'])}, "
        f"and Ukraine from {_pct(y2022['Ukraine'])} in 2022 to {_pct(ukr['share'])}. Attention went to the Gulf instead: {_pct(gulf['share'])} of speeches mentioned Iran or the Gulf war, "
        f"against {_pct(last['Iran and the Gulf war'])} last year."
    ) + _p(
        f"The map shows the split. Europe names Ukraine ({_pct(ukr['by_region']['Europe'])} of its speeches). Africa, the Arab world and South-East Asia name Gaza. "
        f"Most of Latin America names neither: {_pct(neither_americas)} of speeches from the Americas mention neither war."
    )
    topics_html = _p(
        f"<b>Each region also brought its own agenda.</b> In {len(regional)} of the {len(d['topics'])} topics a statistical model finds in the speeches, "
        "more than half the speeches come from a single region: the Pacific's oceans and fossil fuels, the Caribbean's reparatory justice, the Sahel's security and the Gulf's stability. "
        "The model groups words used together; the topic names are ours."
    )

    p5_rows = "".join(
        f"<tr><td>{_e(p['delegation'].replace(' of Great Britain and Northern Ireland', '').replace(' of America', ''))}</td>"
        f"<td>{_e(p['previous']['speaker']) + ', ' + _e(p['previous']['title']) if p['previous'] else '–'}</td><td>{_e(p['speaker'])}, {_e(p['title'])}</td></tr>"
        for p in lead["p5"]
    )
    leaders = (
        _p(
            f"<b>{_pct(o['heads_share'])} of member states sent a head of state or government, down from {_pct(last['heads_share'])} last year.</b> "
            f"The fall is sharpest among the largest economies: {g20_now} of 19 G20 members sent their leader, against {g20_last} in {last['year']}. "
            f"Outside the G20, {_pct(lead['heads_share_outside_g20'])} did."
        )
        + _p(
            f"Those who sent a deputy or a minister include {_e(', '.join(lead['g20_not_leader'][:-1]))} and {_e(lead['g20_not_leader'][-1])}."
        )
        + _p(
            "<span class='so-what'>So what:</span> smaller states still treat the debate as their global stage. The largest powers increasingly send someone else, which says as much about how they rank the UN as anything their envoys say."
        )
    )
    p5 = (
        "<figure><h4>Who the five permanent members of the Security Council sent</h4><div class='scroll'><table class='data p5'>"
        f"<thead><tr><th>Member</th><th>{last['year']}</th><th>{d['year']}</th></tr></thead><tbody>{p5_rows}</tbody></table></div></figure>"
    )

    order = _p(
        f"<b>{_pct(law)} of speeches appeal to the UN Charter or international law.</b> Only {markers['Multipolar']['speeches']} use the word “multipolar”, "
        f"{markers['Spheres of influence']['speeches']} speak of spheres of influence and {markers['Rules-based order']['speeches']} of a rules-based order. "
        "Speakers want the existing rules applied and reformed, not replaced."
    ) + _p(
        f"What differs is who they think bends the rules. African speeches accuse others of double standards ({_pct(markers['Double standards']['by_region']['Africa'])}) "
        f"and criticise unilateral sanctions ({_pct(markers['Unilateral sanctions']['by_region']['Africa'])}). European speeches talk of great powers "
        f"({_pct(markers['Great power(s)']['by_region']['Europe'])}) and the veto ({_pct(markers['Security Council veto']['by_region']['Europe'])})."
    )

    theory = _p(
        f"European speeches use realist vocabulary at {region_frames['Europe']['Realism']:.1f} words per 1,000, against {region_frames['Africa']['Realism']:.1f} in African ones. "
        f"African speeches lead on liberal-institutional vocabulary ({region_frames['Africa']['Liberal institutionalism']:.1f}) "
        f"and use critical and postcolonial vocabulary {region_frames['Africa']['Critical and postcolonial'] / region_frames['Europe']['Critical and postcolonial']:.1f} times as often as European ones."
    ) + _p(
        "Each lens is measured by counting its signature words. That shows the vocabulary a speech leans on, not the argument it makes, "
        "since the same word can serve different theories. The readings below are our interpretation; the quotes are the speakers' own."
    )
    cards = []
    for f in frames["names"]:
        examples = "".join(
            f"<blockquote><p>“{_e(e['quote'])}”</p><cite>{_e(e['speaker'])}, {_e(e['delegation'])} · "
            f"{'the UN interpreters’ English' if e['english_kind'] == 'transcript' else 'the delegation’s English text'} · <a href='{_e(e['url'])}'>source</a></cite></blockquote>"
            for e in frames["exemplars"][f]
            if e["quote"]
        )
        tags = "".join(f"<span class='tag'>{_e(_readable_pattern(t))}</span>" for t in lexicons.FRAMES[f])
        cards.append(
            f"<div class='lens'><h3>{_e(f)}</h3>{_p(_e(LENS_TEXT[f]))}{_lens_reading(f, d)}"
            f"<details><summary>Vocabulary counted and the speeches where it is strongest</summary><div style='margin:8px 0'>{tags}</div>{examples}</details></div>"
        )
    cards.append(f"<div class='lens'><h3>Reading the debate as a whole</h3>{_synthesis(d)}</div>")

    reading = _p(
        f"<b>The median speech runs to {o['words_median']:,} words, about 15 to 20 minutes.</b> The written statements read at a median Flesch–Kincaid grade of "
        f"{dist['grade_median']}, around first-year university, with {dist['sentence_words_median']} words to a sentence."
    ) + _p(
        f"Speakers deliver most of what they file: the median speech says {_pct(dist['delivered_median'])} of its written statement. "
        "The gaps come from speeches cut short and from speakers who switch language mid-speech."
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
            (
                f"{_e(pair['a'])} and {_e(pair['b'])} share the most vocabulary, yet their longest shared passage is {pair['longest_shared_words']} words: alike in theme, not copied. "
                "Both belong to the Alliance of Sahel States."
            )
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
            "A rare word",
            f"Only {len(multipolar_users)} speeches say “multipolar”, from {_e(', '.join(multipolar_users[:6]))} and others. The word has no single camp.",
        ),
        (
            "The next Secretary-General",
            f"{issues['The next Secretary-General']['speeches']} speeches mention choosing the next Secretary-General, whose term begins in 2027.",
        ),
        ("Taiwan", f"{issues['Taiwan']['speeches']} speeches mention Taiwan, which has no seat and gives no speech."),
    ]
    notable_html = "".join(f"<div class='callout'><b>{t}</b>{body}</div>" for t, body in notable if body)

    method = "".join(
        _p(t)
        for t in [
            "<b>A deterministic pipeline.</b> No AI model or web search reads or splits the speeches. Every figure on this page is computed from the texts by fixed rules, and every quote is checked word for word against its source before the page is built.",
            f"<b>Texts.</b> Each speech's English comes from the delegation's written statement where one exists ({o['english_kinds'].get('statement', 0)} speeches), "
            f"and otherwise from the UN's machine transcript of the English interpretation ({o['english_kinds'].get('transcript', 0)}). "
            "A transcript of an interpreted speech is the interpreters' English, not the speaker's words.",
            "<b>History.</b> 2011–2025 figures use the UN General Debate Corpus (Jankin, Baturo and Dasandi), whose English for 2024 is machine-translated and for 2025 machine-transcribed. The same word lists are applied to every year.",
            "<b>Issues and phrases.</b> A speech raises an issue when it names it at least once. The lists are in the source code.",
            "<b>Topics.</b> TF-IDF over words and word pairs, with names, salutations and transcript filler removed, and a twelve-topic NMF model with a fixed seed. "
            "Topic models shift when the texts change, so the labels are reviewed on every rebuild, and the build stops if a topic has none.",
            "<b>Theory lenses.</b> Word lists matched as prefixes, counted per 1,000 words and standardised across speeches. “Trust” is left out because it is this session's theme.",
            "<b>Maps.</b> Natural Earth boundaries (public domain). States too small to see are drawn as dots. Hatched areas gave no speech, or are not UN members.",
            f"<b>Reproduce it.</b> The code and data are at <a href='{REPO}'>{REPO.removeprefix('https://')}</a>, and the <a href='data.json'>figures behind this page</a> are published beside it.",
        ]
    )
    footer = f"Built {date.today().isoformat()} from <a href='{REPO}'>jeremychia/unga-speeches</a>. Speech texts belong to their publishers; the code is under Apache 2.0."

    page = TEMPLATE.read_text(encoding="utf-8")
    for key, value in {
        "__PAGE_TITLE__": f"{title} · UN General Debate {d['year']}",
        "__COUNT__": str(o["speeches"]),
        "__TITLE__": _e(title),
        "__KICKER__": _e(kicker),
        "__SCQA__": scqa,
        "__MESSAGES__": messages,
        "__WHY_TITLE__": "The debate is a signal, not a decision",
        "__WHY__": why,
        "__QUESTIONS__": questions,
        "__AGENDA_TITLE__": "AI went from the margins to the shared agenda in three years",
        "__AGENDA__": agenda,
        "__FIG_TREND__": _picture("trend-issues", "Six line charts of the share of speeches mentioning each issue from 2011 to 2026"),
        "__FIG_AI__": _picture("map-ai", "World map of countries whose speech mentioned artificial intelligence"),
        "__WARS_TITLE__": "The wars of recent years have become regional stories",
        "__WARS__": wars,
        "__TOPICS__": topics_html,
        "__FIG_WARS__": _picture("map-wars", "World map of which countries mentioned Ukraine, Gaza, both or neither"),
        "__LEADERS_TITLE__": "The most powerful were the least likely to come",
        "__LEADERS__": leaders,
        "__P5__": p5,
        "__FIG_LEADERS__": _picture("trend-leaders", "Line chart of G20 members sending their leader each year"),
        "__FIG_RANK__": _picture("map-rank", "World map of the rank of each country's speaker"),
        "__ORDER_TITLE__": "States argue over the rules, not for a new order",
        "__ORDER__": order,
        "__LENSES_TITLE__": "Europe frames the world as security; Africa frames it as justice",
        "__THEORY__": theory,
        "__FIG_DOTS__": _picture("dots-lenses", "Dot plot of each region's use of each theory's vocabulary"),
        "__FIG_LENSMAPS__": _picture("map-lenses", "Four world maps highlighting countries whose speech leans towards each theory"),
        "__NOLEAN__": str(frames["lean_counts"].get(analyse.NO_LEAN, 0)),
        "__LENSCARDS__": "".join(cards),
        "__READING_TITLE__": "Speeches are long, dense and mostly delivered as written",
        "__READING__": reading,
        "__FIG_SWARM__": _picture("swarm-length", "Swarm plot of every speech's length by region"),
        "__NOTABLE__": notable_html,
        "__METHOD__": method,
        "__FOOTER__": footer,
        "__DATA__": json.dumps(d, ensure_ascii=False).replace("</", "<\\/"),
    }.items():
        page = page.replace(key, value)
    leftover = re.findall(r"__[A-Z_]+__", page)
    if leftover:
        raise ValueError(f"unfilled placeholders in the page: {sorted(set(leftover))}")
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
