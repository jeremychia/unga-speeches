"""Write the session's analysis page to site/: the figures from analyse.py, and prose built around them."""

import html
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

from unga_speeches.analysis import analyse, corpus, geo, lexicons, topics
from unga_speeches.analysis.highlights import HIGHLIGHTS
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


def _drill(label, **spec) -> str:
    """A figure the reader can click to see the speeches behind it."""
    return f"<button type='button' class='drill' data-drill='{html.escape(json.dumps(spec), quote=True)}'>{label}</button>"


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


def _check_quotes(d: dict, highlights: list) -> None:
    """Every quote on the page must appear word for word in a stored source text; one that does not stops the build."""
    sources = _verbatim_texts(d["session"])
    quotes = [(e["slug"], e["quote"]) for examples in d["frames"]["exemplars"].values() for e in examples]
    quotes += [(r["slug"], r["quote"]) for r in d["speeches"]] + [(h.slug, h.quote) for h in highlights]
    quotes += [(r["slug"], e["text"]) for r in d["speeches"] for e in r["evidence"].values()]
    for slug, quote in quotes:
        if quote and not any(_normalise(quote) in t for t in sources.get(slug, [])):
            raise ValueError(f"quote for {slug} is not in its source text: {quote[:80]}")
    # shared passages come from the speech text with headers and page furniture removed, so they are checked against it
    cleaned = {s.slug: _normalise(s.text) for s in corpus.load(d["session"])}
    for pair in d["similarity"]["pairs"] + d["anomalies"]["similar_pairs"]:
        slugs = (pair.get("slug_a", pair["a"]), pair.get("slug_b", pair["b"]))
        for side, slug in zip(("a", "b"), slugs, strict=True):
            c = pair["shared"][side]
            excerpt = " ".join(x for x in (c["before"], c["passage"], c["after"]) if x)
            if _normalise(excerpt) not in cleaned[slug]:
                raise ValueError(f"shared passage for {slug} is not in its speech text: {excerpt[:80]}")


def _region_of_most(rows: list[dict], key: str, value: str) -> tuple[str, int, int]:
    members = [r for r in rows if r[key] == value]
    region, count = Counter(r["region"] for r in members).most_common(1)[0]
    return region, count, len(members)


def _picture(name: str, alt: str) -> str:
    """A figure in its light and dark versions; the browser picks the one for the reader's theme."""
    return (
        f"<picture><source srcset='figures/{name}-dark.svg' media='(prefers-color-scheme: dark)'>"
        f"<img src='figures/{name}-light.svg' alt='{_e(alt)}' loading='lazy'></picture>"
    )


def _figures(d: dict) -> None:
    from unga_speeches.analysis import figures

    out = SITE_DIR / "figures"
    out.mkdir(parents=True, exist_ok=True)
    figures.trend_multiples(d["trends"], out, analyse.TREND_ISSUES)
    figures.leaders_trend(d["trends"], out)
    figures.lens_dots(d["frames"]["by_group"]["region"], out, d["frames"]["names"])
    figures.length_swarm(d["speeches"], out, REGIONS)


def _year(trends: list[dict], year: int) -> dict:
    return next(t for t in trends if t["year"] == year)


def build(session: int) -> Path:
    d = analyse.build(session)
    chosen = HIGHLIGHTS.get(session, [])
    _check_quotes(d, chosen)
    _check_beyond(d)
    beyond = _beyond(d)
    d["geo"] = geo.paths()
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
        issues[k] for k in ("Artificial intelligence", "Climate change", "Gaza or Palestine", "Ukraine", "Iran and the Gulf war")
    )
    statehood = issues["Palestinian statehood"]
    vocab = d["vocabulary"]
    by_slug = {r["slug"]: r for r in rows}

    def region_share(region: str, test) -> float:
        members = [r for r in rows if r["region"] == region]
        return sum(test(r) for r in members) / len(members)

    def neither(r: dict) -> bool:
        return "Ukraine" not in r["issues"] and "Gaza or Palestine" not in r["issues"]

    lead_ukraine = max(REGIONS, key=lambda g: ukr["by_region"][g])
    lead_gaza, second_gaza = sorted(REGIONS, key=lambda g: -gaza["by_region"][g])[:2]
    majority_ukraine = [g for g in REGIONS if ukr["by_region"][g] > 0.5]
    most_neither = sorted(REGIONS, key=lambda g: -region_share(g, neither))[:2]
    gaza_only = issues["Gaza"]
    law = o["charter_or_law"] / o["speeches"]
    ai_regions = ai["by_region"]
    regional = [t for t in d["topics"] if (lambda r: r[1] / r[2] > 0.5)(_region_of_most(rows, "topic", t["label"]))]
    china = next((p for p in lead["p5"] if p["iso3"] == "CHN"), None)
    g20_now, g20_last = now["g20_heads"], last["g20_heads"]
    first_year = min(t["year"] for t in d["trends"])
    climate_floor = min(t["Climate change"] for t in d["trends"])
    terrorism_lowest = now["Terrorism"] < min(t["Terrorism"] for t in d["trends"] if t["year"] != d["year"])

    quiet_issues = sorted(
        (i for i in d["press"]["issues"] if i["speeches"] >= 30 and (i["press_ratio"] or 0) <= QUIET_RATIO),
        key=lambda i: i["press_ratio"] or 0,
    )
    title = "The world's attention has moved"
    kicker = (
        "In 2026 artificial intelligence became the one worry almost every country shares. "
        "The wars that filled recent debates faded from most speeches outside Europe and Asia. "
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
                f"{_drill(_pct(ai['share']), kind='mention', name='Artificial intelligence')} of speeches raised AI, up from {_pct(last['Artificial intelligence'])} in {last['year']} and {_pct(y2023['Artificial intelligence'])} in 2023.",
            ),
            (
                "wars",
                "Beyond Europe and Asia, the wars of recent years are fading from view",
                f"Gaza or Palestine fell from {_pct(last['Gaza or Palestine'])} of speeches to {_drill(_pct(gaza['share']), kind='mention', name='Gaza or Palestine')}, and Ukraine from {_pct(y2022['Ukraine'])} in 2022 to {_drill(_pct(ukr['share']), kind='mention', name='Ukraine')}. "
                "Most speeches from the Americas and the Pacific name neither.",
            ),
            (
                "leaders",
                "The most powerful were the least likely to come",
                f"{_drill(f'{g20_now} of 19', kind='rank', g20=True)} G20 members sent their leader, down from {g20_last} in {last['year']}."
                + (f" China sent its {china['title']}." if china else ""),
            ),
            (
                "order",
                "States argued over the rules, not for a new order",
                f"{_drill(_pct(law), kind='mention', name='UN Charter or international law')} invoked the UN Charter or international law. Only {_drill(markers['Multipolar']['speeches'], kind='mention', name='Multipolar')} speeches said “multipolar”.",
            ),
            (
                "press",
                "The world heard a narrower debate than the one given",
                f"{_drill(_pct(d['press']['attention']['top5_share']), kind='press', slug=d['press']['attention']['rows'][0]['slug'])} of press mentions went to five delegations. "
                f"Issues raised by dozens of speeches, such as {'; '.join(_issue_phrase(i['issue']) for i in quiet_issues[:3])}, got a third or less of their share of the speeches.",
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
            f"<b>In 2022, {_pct(y2022['Artificial intelligence'])} of speeches mentioned artificial intelligence. This year {_drill(_pct(ai['share']), kind='mention', name='Artificial intelligence')} did.</b> "
            f"Only climate change is raised more often ({_drill(_pct(cc['share']), kind='mention', name='Climate change')}), and it has been raised by at least {_pct(climate_floor)} of speeches in every year since {first_year}."
        )
        + _p(
            f"AI is raised in every region: by at least {_pct(min(ai_regions.values()))} of the speeches in each, led by Europe at {_pct(ai_regions['Europe'])}. "
            f"Terrorism went the other way: {_drill(_pct(now['Terrorism']), kind='mention', name='Terrorism')} of speeches mentioned it"
            + (f", the lowest since at least {first_year}." if terrorism_lowest else ".")
        )
        + _p(
            "<span class='so-what'>So what:</span> governments now bring AI to the UN as a shared question of rules and risk, not only as a matter for technology firms or the richest economies."
        )
    )

    wars = _p(
        f"<b>Attention to the wars of recent years is falling.</b> Gaza or Palestine fell from {_pct(last['Gaza or Palestine'])} of speeches in {last['year']} to {_drill(_pct(gaza['share']), kind='mention', name='Gaza or Palestine')}, "
        f"and Ukraine from {_pct(y2022['Ukraine'])} in 2022 to {_drill(_pct(ukr['share']), kind='mention', name='Ukraine')}. Attention went to the Gulf instead: {_drill(_pct(gulf['share']), kind='mention', name='Iran and the Gulf war')} of speeches mentioned Iran or the Gulf war, "
        f"against {_pct(last['Iran and the Gulf war'])} last year."
    ) + _p(
        (
            f"The map shows the split. {lead_ukraine} is the only region where most speeches name Ukraine ({_pct(ukr['by_region'][lead_ukraine])}). "
            if majority_ukraine == [lead_ukraine]
            else f"The map shows the split. {lead_ukraine} names Ukraine most ({_pct(ukr['by_region'][lead_ukraine])} of its speeches). "
        )
        + (
            f"It also leads on Gaza or Palestine ({_pct(gaza['by_region'][lead_gaza])}), just ahead of {second_gaza} ({_pct(gaza['by_region'][second_gaza])}). "
            if lead_gaza == lead_ukraine
            else f"{lead_gaza} names Gaza or Palestine most ({_pct(gaza['by_region'][lead_gaza])}), ahead of {second_gaza} ({_pct(gaza['by_region'][second_gaza])}). "
        )
        + f"Most speeches from {most_neither[0].replace('Oceania', 'the Pacific').replace('Americas', 'the Americas')} ({_pct(region_share(most_neither[0], neither))}) "
        f"and {most_neither[1].replace('Oceania', 'the Pacific').replace('Americas', 'the Americas')} ({_pct(region_share(most_neither[1], neither))}) name neither war."
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
            f"<b>{_drill(_pct(o['heads_share']), kind='rank')} of member states sent a head of state or government, down from {_pct(last['heads_share'])} last year.</b> "
            f"The fall is sharpest among the largest economies: {_drill(f'{g20_now} of 19', kind='rank', g20=True)} G20 members sent their leader, against {g20_last} in {last['year']}. "
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
        f"<b>{_drill(_pct(law), kind='mention', name='UN Charter or international law')} of speeches appeal to the UN Charter or international law.</b> Only {_drill(markers['Multipolar']['speeches'], kind='mention', name='Multipolar')} use the word “multipolar”, "
        f"{_drill(markers['Spheres of influence']['speeches'], kind='mention', name='Spheres of influence')} speak of spheres of influence and {_drill(markers['Rules-based order']['speeches'], kind='mention', name='Rules-based order')} of a rules-based order. "
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
        f"<b>The median speech runs to {_drill(format(o['words_median'], ','), kind='metric', field='words')} words, about 15 to 20 minutes.</b> The written statements read at a median Flesch–Kincaid grade of "
        f"{_drill(dist['grade_median'], kind='metric', field='grade')}, around first-year university, with {dist['sentence_words_median']} words to a sentence."
    ) + _p(
        f"Speakers deliver most of what they file: the median speech says {_drill(_pct(dist['delivered_median']), kind='metric', field='delivered')} of its written statement. "
        "The gaps come from speeches cut short and from speakers who switch language mid-speech."
    )

    def ranked(items: list[dict], show, summary: str = "The top five") -> str:
        return (
            f"<details><summary>{summary}</summary><ol>"
            + "".join(f"<li>{_e(i['delegation'])}: {show(i)}</li>" for i in items)
            + "</ol></details>"
        )

    pair = an["similar_pairs"][0]
    multipolar_users = [r["delegation"] for r in rows if "Multipolar" in r["markers"]]
    taiwan = [r["delegation"] for r in rows if "Taiwan" in r["issues"]]

    def see_all(label: str, **spec) -> str:
        return f"<p class='small' style='margin:6px 0 0'>{_drill(label, **spec)}</p>"

    def shared(x: dict) -> str:
        def side(c: dict, name: str) -> str:
            return (
                f"<p><b>{_e(name)}:</b> “{'…' if c['cut_start'] else ''}{_e(c['before'])} <mark>{_e(c['passage'])}</mark> "
                f"{_e(c['after'])}{'…' if c['cut_end'] else ''}”</p>"
            )

        return f"<div class='shared'>{side(x['shared']['a'], x['a'])}{side(x['shared']['b'], x['b'])}</div>"

    notable = [
        (
            "The longest and the shortest",
            f"{_e(an['longest'][0]['delegation'])} used {an['longest'][0]['words']:,} words, {an['longest'][0]['words'] / o['words_median']:.1f} times the median; "
            f"{_e(an['shortest'][0]['delegation'])} used {an['shortest'][0]['words']:,}."
            + ranked(an["longest"], lambda i: f"{i['words']:,} words", "The five longest")
            + ranked(an["shortest"], lambda i: f"{i['words']:,} words", "The five shortest")
            + see_all("Every speech by length", kind="metric", field="words"),
        ),
        (
            "The densest and the plainest prose",
            f"{_e(an['densest'][0]['delegation'])}'s statement averages {an['densest'][0]['sentence_words']} words a sentence, a reading grade of {an['densest'][0]['grade']}. "
            f"{_e(an['plainest'][0]['delegation'])}'s reads at grade {an['plainest'][0]['grade']}."
            + ranked(an["densest"], lambda i: f"grade {i['grade']}, {i['sentence_words']} words a sentence", "The five densest")
            + ranked(an["plainest"], lambda i: f"grade {i['grade']}, {i['sentence_words']} words a sentence", "The five plainest")
            + see_all("Every statement by reading grade", kind="metric", field="grade"),
        ),
        (
            "The most alike",
            f"{_e(pair['a'])} and {_e(pair['b'])} share the most vocabulary. Their longest shared passage is {pair['longest_shared_words']} words, highlighted here in each speech:"
            + shared(pair)
            + "<details><summary>The five closest pairs, with their shared passages</summary><ol>"
            + "".join(
                f"<li>{_e(x['a'])} and {_e(x['b'])}: similarity {x['similarity']:.2f}, longest shared passage {x['longest_shared_words']} words{shared(x)}</li>"
                for x in an["similar_pairs"]
            )
            + "</ol></details>",
        ),
        (
            "The most distinctive",
            f"{_e(an['most_distinctive'][0]['delegation'])} and {_e(an['most_distinctive'][1]['delegation'])} share the least vocabulary with everyone else."
            + ranked(
                an["most_distinctive"],
                lambda i: "its own words: " + _e(", ".join(by_slug[i["slug"]]["distinctive_words"][:5])),
                "The five most distinctive",
            ),
        ),
        (
            "Filed but not said",
            f"{_e(an['least_delivered'][0]['delegation'])} said {_pct(an['least_delivered'][0]['delivered_share'])} of its filed text, the lowest of the debate. "
            "The gaps come from speeches cut short and from speakers switching language."
            + ranked(an["least_delivered"][:5], lambda i: f"{_pct(i['delivered_share'])} of the filed text said", "The five lowest")
            + see_all("Every speech by share delivered", kind="metric", field="delivered"),
        ),
        (
            "A rare word",
            f"Only {_drill(len(multipolar_users), kind='mention', name='Multipolar')} speeches say “multipolar”: {_e(', '.join(multipolar_users[:-1]))} and {_e(multipolar_users[-1])}. "
            "The word has no single camp.",
        ),
        (
            "Palestine as a question of statehood",
            f"{_drill(gaza['speeches'], kind='mention', name='Gaza or Palestine')} speeches mention Gaza or Palestine. Of these, "
            f"{_drill(gaza_only['speeches'], kind='mention', name='Gaza')} name Gaza, and {_drill(statehood['speeches'], kind='mention', name='Palestinian statehood')} "
            "speak of Palestinian statehood: the two-state solution or recognising Palestine.",
        ),
        (
            "The next Secretary-General",
            f"{_drill(issues['The next Secretary-General']['speeches'], kind='mention', name='The next Secretary-General')} speeches mention choosing the next Secretary-General, "
            "whose term begins in 2027.",
        ),
        ("Women at the podium", beyond.pop("_women")),
        (
            "Taiwan",
            f"{_drill(len(taiwan), kind='mention', name='Taiwan')} speeches mention Taiwan, which has no seat and gives no speech: {_e(', '.join(taiwan))}.",
        ),
    ]
    notable_html = "".join(f"<div class='callout'><b>{t}</b>{body}</div>" for t, body in notable if body)

    top_two = [w["word"] for w in vocab["words"][:2]]
    vocab_html = _p(
        f"<b>“{top_two[0].capitalize()}” and “{top_two[1]}” are still the debate's commonest words.</b> "
        "“Trust” also ranks high, because it is this session's theme. The pairs say more: “security council”, “human rights” and “artificial intelligence” lead them."
    ) + _p(
        "Each region's distinctive words read like its agenda: the Sahel and debt for Africa, the Caribbean and crime for the Americas, "
        "Russia and aggression for Europe, the ocean and sea-level rise for the Pacific."
    )

    sim = d["similarity"]
    closest = sim["pairs"][0]
    longest_pair = max(sim["pairs"], key=lambda x: x["longest_shared_words"])
    blocs = sim["blocs"]
    regional_blocs = [b for b in blocs if max(b["regions"].values()) / len(b["members"]) > 0.7]
    tightest = max(blocs, key=lambda b: b["within"])
    loose = [b for b in blocs if b["loose"]]
    africa_blocs = [b for b in blocs if next(iter(b["regions"])) == "Africa"]

    def bloc_name(b: dict) -> str:
        """A bloc's name mid-sentence: the part before the colon, with a leading "The" lowered."""
        name = b["label"].split(":")[0]
        return "the " + name[4:] if name.startswith("The ") else name

    alike_html = _p(
        f"<b>The closest pair is {_e(by_slug[closest['a']]['delegation'])} and {_e(by_slug[closest['b']]['delegation'])}, at {closest['similarity']:.2f}.</b> "
        "Their likeness is mostly shared vocabulary, not shared text. "
        f"Among the twenty closest pairs, the longest passage any two share is {longest_pair['longest_shared_words']} words, between "
        f"{_e(by_slug[longest_pair['a']]['delegation'])} and {_e(by_slug[longest_pair['b']]['delegation'])}: “{_e(longest_pair['shared']['a']['passage'])}”. "
        "Click a pair below to read its shared passage in context."
    ) + _p(
        f"Clustering the speeches finds {len(blocs)} blocs, and {len(regional_blocs)} of them are mostly one region. "
        f"The tightest is {_e(bloc_name(tightest))} (cohesion {tightest['within']:.2f})."
        + (
            f" African speeches fall into {len(africa_blocs)} blocs: {_e('; '.join(bloc_name(b) for b in africa_blocs))}."
            if len(africa_blocs) > 1
            else ""
        )
        + (f" One, {_e(bloc_name(loose[0]))}, is loose: its members are no closer to each other than to the rest." if loose else "")
    )

    def highlight(h) -> str:
        r = by_slug[h.slug]
        near = ", ".join(x["delegation"] for x in r["similar"][:2])
        return (
            f"<div class='highlight'><h3>{_e(h.headline)}</h3><p>{_e(h.note)}</p>"
            f"<blockquote><p>“{_e(h.quote)}”</p><cite>{_e(r['speaker'])}, {_e(r['delegation'])} · "
            f"{'the UN interpreters’ English' if r['english_kind'] == 'transcript' else 'the delegation’s English text'} · <a href='{_e(r['page_url'])}'>source</a></cite></blockquote>"
            f"<p class='meta'>{_e(r['title'])} · {r['words']:,} words · main topic: {_e(r['topic'])} · lean: {_e(r['lean'])} · closest speeches: {_e(near)} · "
            f"<a href='#country' data-profile='{_e(h.slug)}'>open the profile</a></p></div>"
        )

    highlights_html = "".join(highlight(h) for h in chosen)

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
            "<b>Maps.</b> Natural Earth boundaries (public domain), simplified to about 15 km and drawn in the browser. States too small to see are drawn as dots. Hatched areas gave no speech, or are not UN members.",
            "<b>Words.</b> Counts leave out common English words, names, salutations and transcript filler. Region words use weighted log-odds with an informative prior; each speech's distinctive words are its highest TF-IDF terms.",
            "<b>Similarity.</b> Cosine similarity of TF-IDF word profiles, with names, salutations and filler removed; the same measure drives the closest speeches, the pairs and the blocs. Blocs come from Ward clustering into eight groups, and are named by their top words.",
            "<b>Naming.</b> A speech names a state when it uses the state's name, a formal or former name, or, for about fifty states, a common adjective such as “Russian” or “Israeli”. "
            "Places named after a state, such as the Gulf of Guinea, are not counted, and neither is a bare “Congo”, which speakers use for both Congos.",
            "<b>Press.</b> News reports are listed by hand in reference/news_81.csv, downloaded, and cut to their paragraphs by fixed rules. Only short excerpts are shown, each linked to its report and "
            "checked word for word against the downloaded page. A report names a delegation when a paragraph names the country or, in a report that names the country, its speaker's surname.",
            "<b>The UN's summaries.</b> Each speaker's UN page carries the UN press office's headline and summary. A summary keeps an issue when it names it with the same word list used for the speeches. "
            "A headline's tone is set by its first reporting verb.",
            "<b>Highlights.</b> The eight speeches worth reading are an editorial choice, and their notes are our reading. Their quotes are checked like every other quote on the page.",
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
        "__WARS_TITLE__": "Beyond Europe and Asia, the wars of recent years are fading from view",
        "__WARS__": wars,
        "__TOPICS__": topics_html,
        "__LEADERS_TITLE__": "The most powerful were the least likely to come",
        "__LEADERS__": leaders,
        "__P5__": p5,
        "__FIG_LEADERS__": _picture("trend-leaders", "Line chart of G20 members sending their leader each year"),
        "__ORDER_TITLE__": "States argue over the rules, not for a new order",
        "__ORDER__": order,
        "__LENSES_TITLE__": "Europe frames the world as security; Africa frames it as justice",
        "__THEORY__": theory,
        "__FIG_DOTS__": _picture("dots-lenses", "Dot plot of each region's use of each theory's vocabulary"),
        "__NOLEAN__": str(frames["lean_counts"].get(analyse.NO_LEAN, 0)),
        "__LENSCARDS__": "".join(cards),
        "__READING_TITLE__": "Speeches are long, dense and mostly delivered as written",
        "__READING__": reading,
        "__FIG_SWARM__": _picture("swarm-length", "Swarm plot of every speech's length by region"),
        "__NOTABLE__": notable_html,
        "__HIGHLIGHTS__": highlights_html,
        "__VOCAB_TITLE__": f"“{top_two[0].capitalize()}” and “{top_two[1]}” still lead; each region has words of its own",
        "__VOCAB__": vocab_html,
        "__ALIKE_TITLE__": "Speeches cluster by neighbourhood, and alike in theme rather than wording",
        "__ALIKE__": alike_html,
        "__METHOD__": method,
        **beyond,
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


TONE_ORDER = ["Alarm", "Appeal", "Showcase", "Statement, no verb"]
ARGENTINA_QUOTE = "it's become a useless organization"
TURN = "Latin America's turn"
QUIET_RATIO = 0.34
# how prose names a region's outlets and its delegations
REGION_PRESS = {
    "Africa": ("African outlets", "African delegations"),
    "Americas": ("outlets in the Americas", "delegations from the Americas"),
    "Asia": ("Asian outlets", "Asian delegations"),
    "Oceania": ("Pacific outlets", "Pacific delegations"),
}
# the names prose uses where the formal name would read awkwardly mid-sentence
SHORT_NAMES = {
    "united-states-america": "the United States",
    "iran-islamic-republic": "Iran",
    "venezuela-bolivarian-republic": "Venezuela",
    "russian-federation": "Russia",
    "palestine-state": "Palestine",
    "united-kingdom-great-britain-and-northern-ireland": "the United Kingdom",
    "syrian-arab-republic": "Syria",
    "bolivia-plurinational-state": "Bolivia",
}


def _check_beyond(d: dict) -> None:
    """The naming evidence, candidate evidence and press excerpts must each appear in the text they are cut from."""
    sources = _verbatim_texts(d["session"])
    quotes = [(e["from"], e["evidence"]["text"]) for e in d["mentions"]["edges"] if e["evidence"]]
    quotes += [(n["slug"], n["evidence"]["text"]) for c in d["race"]["candidates"] for n in c["named_by"] if n["evidence"]]
    quotes += [(n["slug"], n["evidence"]["text"]) for v in d["race"]["asks"].values() for n in v if n["evidence"]]
    quotes += [("argentina", ARGENTINA_QUOTE)]
    for slug, quote in quotes:
        if not any(_normalise(quote) in t for t in sources.get(slug, [])):
            raise ValueError(f"quote for {slug} is not in its source text: {quote[:80]}")
    from unga_speeches.analysis import press

    paragraphs = {n["url"]: [_normalise(p) for p in n["paragraphs"]] for n in press.load_news(d["session"])}
    for row in d["press"]["attention"]["rows"]:
        for snip in row["snippets"]:
            if not any(_normalise(snip["text"]) in p for p in paragraphs.get(snip["url"], [])):
                raise ValueError(f"press excerpt is not in its article: {snip['text'][:80]}")


def _issue_phrase(issue: str) -> str:
    """An issue's name mid-sentence: lowered, except for place names."""
    return (
        issue if issue.split()[0] in ("Sudan", "Haiti", "Gaza", "Ukraine", "Iran", "Taiwan", "Palestinian", "Security") else issue.lower()
    )


def _upper_first(text: str) -> str:
    return text[:1].upper() + text[1:]


def _beyond(d: dict) -> dict[str, str]:
    """Copy for the sections that look past the speeches themselves: naming, the press, the Secretary-General race and the UN's own summary."""
    names, rows = d["names"], d["speeches"]
    by_slug = {r["slug"]: r for r in rows}
    m, pr, rc = d["mentions"], d["press"], d["race"]
    most = m["most_named"]

    def n(slug: str) -> str:
        return _e(SHORT_NAMES.get(slug, names.get(slug, slug)))

    def named_drill(i: int) -> str:
        x = most[i]
        return f"{n(x['slug'])} ({_drill(x['speeches'], kind='named', slug=x['slug'])} speeches)"

    pairs_total = len(m["edges"])
    usa = next((x for x in most if x["slug"] == "united-states-america"), None)
    rus = next((x for x in most if x["slug"] == "russian-federation"), None)
    top_namer = m["names_most"][0]
    taiwan = next((x for x in most if x["slug"] == "TWN"), None)
    mutual_examples = [
        p for p in m["mutual"] if p in (["armenia", "azerbaijan"], ["iran-islamic-republic", "israel"], ["cuba", "united-states-america"])
    ]
    naming = (
        _p(
            f"<b>{named_drill(0)}, {named_drill(1)} and {named_drill(2)} are the states other speeches name most.</b> "
            f"Next come {named_drill(3)} and {named_drill(4)}. Across the debate, a speech named another state in {pairs_total:,} speech-to-state pairs."
        )
        + _p(
            (
                f"Russia is named by fewer speeches than the United States ({rus['speeches']} against {usa['speeches']}), but more insistently: "
                f"{rus['times']} times against {usa['times']}. "
                if rus and usa and rus["speeches"] < usa["speeches"] and rus["times"] > usa["times"]
                else ""
            )
            + f"{n(top_namer['slug'])} names more states than anyone ({_drill(top_namer['states'], kind='names', slug=top_namer['slug'])}). "
            f"{_pct(m['same_region_share'])} of all naming stays within the speaker's own region."
        )
        + _p(
            f"{len(m['mutual'])} pairs of states name each other"
            + (", among them " + "; ".join(f"{n(a)} and {n(b)}" for a, b in mutual_examples) + "." if mutual_examples else ".")
            + f" {len(m['named_nobody'])} speeches name no other state at all: {', '.join(n(s) for s in m['named_nobody'])}."
            + (
                f" Taiwan, which has no seat, is named in {_drill(taiwan['speeches'], kind='named', slug='TWN')} speeches."
                if taiwan
                else ""
            )
        )
        + _p(
            "<span class='so-what'>So what:</span> naming a state is how a speech assigns blame or offers solidarity. The most-named are the places at war, not the great powers, "
            "and naming mostly stays close to home."
        )
    )

    att = pr["attention"]
    top = att["rows"][:5]
    iss = {i["issue"]: i for i in pr["issues"]}
    # issues many speeches raised that the press gave a third or less of their podium share
    quiet = sorted(
        (i for i in pr["issues"] if i["speeches"] >= 30 and (i["press_ratio"] or 0) <= QUIET_RATIO), key=lambda i: i["press_ratio"] or 0
    )
    loud = max(pr["issues"], key=lambda i: i["press_ratio"] or 0)
    heads = pr["headlines"]
    tones = dict(heads["tones"])
    tr = pr["translations"]
    outlets = sorted({s["outlet"].replace(" (via GlobalSecurity.org)", "") for s in pr["sources"] if s["outlet"] != "Wikipedia"})
    outside = [s for s in pr["sources"] if not s["outlet"].startswith("UN News") and s["outlet"] != "Wikipedia"]
    us = att["rows"][0]
    home = att["by_base"]
    europe = next((b for b in home if b["region"] == "Europe"), None)
    elsewhere = [b for b in home if b["region"] != "Americas"]
    us_elsewhere = sum(us["by_base"].get(b["region"], 0) for b in elsewhere) / max(1, sum(b["mentions"] for b in elsewhere))
    press_html = (
        _p(
            f"<b>{_drill(_pct(us['share_of_press']), kind='press', slug=us['slug'])} of the paragraphs in {att['articles']} outside news reports were about {n(us['slug'])}, "
            f"whose speaker gave {us['share_of_words'] * 100:.1f}% of the debate's words.</b> "
            f"Five delegations took {_pct(att['top5_share'])} of all press mentions: "
            + ", ".join(f"{n(r['slug'])} ({_drill(_pct(r['share_of_press']), kind='press', slug=r['slug'])})" for r in top)
            + f". Only {att['named']} of {att['delegations']} delegations were named at all."
        )
        + _p(
            f"The press also heard different issues. {_e(loud['issue'])} got {loud['press_ratio']:.0f} times as much press text per word as podium text. "
            + (
                "Issues raised by many speeches got a third or less of their podium share: "
                + "; ".join(
                    f"{_e(_issue_phrase(i['issue']))} ({_drill(i['speeches'], kind='mention', name=i['issue'])} speeches, "
                    f"{'no press' if not i['press_ratio'] else format(i['press_ratio'], '.1f') + '×'})"
                    for i in quiet
                )
                + ". "
                if quiet
                else ""
            )
            + f"Climate change, raised by {_drill(iss['Climate change']['speeches'], kind='mention', name='Climate change')} speeches, got {iss['Climate change']['press_ratio']:.1f} times its podium share."
        )
        + _p(
            "<b>Each region's press looks mostly at its own region.</b> "
            + _upper_first(
                "; ".join(
                    f"{REGION_PRESS[b['region']][0]} gave {_pct(b['home_share'])} of their mentions to {REGION_PRESS[b['region']][1]}, "
                    f"which are {_pct(b['home_speaker_share'])} of speakers"
                    for b in home
                    if b["region"] in REGION_PRESS and b["home_share"] is not None
                )
            )
            + ". "
            + (
                f"Europe's {europe['articles']} reports come from {_e(', '.join(europe['outlets']))}, so its {_pct(europe['home_share'])} is mostly the war seen from each side. "
                if europe
                else ""
            )
            + f"Outside the Americas' press, the United States takes {_pct(us_elsewhere)} of mentions, against {_pct(us['share_of_press'])} overall. "
            + "The delegation from outside their own region that each names most: "
            + "; ".join(
                f"{REGION_PRESS[b['region']][0]}, {n(b['outsider']['slug'])}" for b in home if b["region"] in REGION_PRESS and b["outsider"]
            )
            + "."
        )
        + _p(
            f"<b>The UN's own summaries filter too.</b> Of the {iss['Ukraine']['speeches']} speeches that raised Ukraine, the UN press office's summary kept it for "
            f"{_drill(_pct(iss['Ukraine']['kept_share']), kind='dropped', issue='Ukraine')}. For Palestinian statehood it kept "
            f"{_drill(_pct(iss['Palestinian statehood']['kept_share']), kind='dropped', issue='Palestinian statehood')}, and for AI "
            f"{_drill(_pct(iss['Artificial intelligence']['kept_share']), kind='dropped', issue='Artificial intelligence')}. "
            f"Its headlines are mostly statements or quotes with no reporting verb ({_drill(tones.get('Statement, no verb', 0), kind='tone', tone='Statement, no verb')}); "
            f"of the rest, {_drill(tones.get('Showcase', 0), kind='tone', tone='Showcase')} showcase, {_drill(tones.get('Appeal', 0), kind='tone', tone='Appeal')} appeal "
            f"and {_drill(tones.get('Alarm', 0), kind='tone', tone='Alarm')} sound the alarm."
        )
        + _p(
            f"UN News also rewrote {tr['speeches']} speeches for readers in other languages, "
            + ", ".join(f"{lang} ({k})" for lang, k in tr["languages"][:3])
            + " most often."
        )
        + _p(
            "<span class='so-what'>So what:</span> the debate the world reads about is narrower than the one given. A handful of outlets follow a handful of speakers, "
            "and most governments reach a wider audience, if at all, through the UN's own summaries."
        )
    )
    words_by = {b["region"]: b["words"] for b in home}
    press_note = (
        f"Outside press: {len(outside)} reports from {len(outlets) - 1} outlets across {len(home)} regions, downloaded and cut to their paragraphs. "
        f"The Americas still supply {_pct(words_by.get('Americas', 0) / max(1, sum(words_by.values())))} of the words, mostly US live blogs. "
        "BBC, Reuters, AP, the Guardian, the New York Times, CNA, the Straits Times and several Indian and French outlets could not be searched or refused the download. "
        "Politico had no coverage and TLDR News is video only. <a href='https://github.com/jeremychia/unga-speeches/blob/main/docs/news-sourcing.md'>How the sample was built</a> · "
        "<a href='https://github.com/jeremychia/unga-speeches/blob/main/reference/outlets.csv'>every outlet considered</a>."
    )

    cands = rc["candidates"]
    leader = max((c for c in cands if not c["withdrew"]), key=lambda c: c["poll"]["encourage"])
    most_named_c = max(cands, key=lambda c: len(c["named_by"]))
    unnamed = [c for c in cands if not c["named_by"] and not c["withdrew"]]
    withdrawn = [c for c in cands if c["withdrew"]]
    asks = rc["asks"]
    race_html = (
        _p(
            f"<b>{_drill(len(most_named_c['named_by']), kind='candidate', index=cands.index(most_named_c))} speeches named {_e(most_named_c['name'])}, "
            f"{'all from the Caribbean' if all(by_slug.get(x['slug'], {}).get('region') == 'Americas' for x in most_named_c['named_by']) else 'more than any other candidate'}.</b> "
            f"{_e(leader['name'])}, who led the Security Council's {rc['poll_date'][8:].lstrip('0')} September straw poll with {leader['poll']['encourage']} of "
            f"{leader['poll']['of']} members encouraging, was named by "
            + (
                f"{_drill(len(leader['named_by']), kind='candidate', index=cands.index(leader))} speech{'es' if len(leader['named_by']) != 1 else ''}: "
                + _e(", ".join(names[x["slug"]] for x in leader["named_by"]))
                + (", in Spanish" if leader["named_by"] and all(x["language"] == "es" for x in leader["named_by"]) else "")
                + "."
                if leader["named_by"]
                else "no speech."
            )
        )
        + _p(
            (
                "Not every nominee was named even by the state that nominated them. "
                + "; ".join(f"{_e(c['name'])}, nominated by {_e(c['nominated_by'])}, by none" for c in unnamed)
                + ". "
                if unnamed
                else ""
            )
            + (
                f"Argentina's president used the podium to call the UN “{_e(ARGENTINA_QUOTE.split('become ', 1)[1])}”."
                if any(c["nominated_by"] == "Argentina" for c in unnamed)
                else ""
            )
            + (
                " " + "; ".join(f"{_e(c['name'])} withdrew on {int(c['withdrew'][8:])} September" for c in withdrawn) + "."
                if withdrawn
                else ""
            )
        )
        + _p(
            f"Beyond names, {_drill(len(asks['A woman']), kind='ask', name='A woman')} speeches asked for the first woman Secretary-General and "
            f"{_drill(len(asks[TURN]), kind='ask', name=TURN)} said it was Latin America's turn. "
            f"{_drill(len(rc['mention_selection']), kind='mention', name='The next Secretary-General')} speeches mentioned the selection at all."
        )
        + _p(
            "<span class='so-what'>So what:</span> the selection is decided in the Security Council, not the Assembly Hall, and most governments kept quiet about it. "
            "Only one region used the podium to campaign as a bloc."
        )
    )
    race_rows = "".join(
        f"<tr><td><b>{_e(c['name'])}</b><br><span class='small'>{_e(c['nationality'])} · nominated by {_e(c['nominated_by'])}"
        f"{' · withdrew ' + _e(c['withdrew']) if c['withdrew'] else ''}</span></td>"
        f"<td><div class='poll' role='img' aria-label='{c['poll']['encourage']} encourage, {c['poll']['discourage']} discourage, {c['poll']['no_opinion']} no opinion'>"
        + "".join(
            f"<span class='{k}' style='flex:{c['poll'][k]}' title='{c['poll'][k]} {label}'>{c['poll'][k] or ''}</span>"
            for k, label in (("encourage", "encourage"), ("no_opinion", "no opinion"), ("discourage", "discourage"))
        )
        + "</div></td>"
        f"<td>{_drill(str(len(c['named_by'])), kind='candidate', index=cands.index(c)) if c['named_by'] else '0'}"
        f"{'<br><span class=small>' + _e(', '.join(names[x['slug']] for x in c['named_by'])) + '</span>' if c['named_by'] else ''}</td></tr>"
        for c in sorted(cands, key=lambda c: (bool(c["withdrew"]), -c["poll"]["encourage"]))
    )
    race_table = (
        "<figure><h4>The candidates: the Security Council's straw poll against the podium</h4><div class='scroll'><table class='data race'>"
        "<thead><tr><th>Candidate</th><th>Straw poll, 18 September</th><th>Speeches naming them</th></tr></thead>"
        f"<tbody>{race_rows}</tbody></table></div>"
        "<div class='legend'><span style='--sw:var(--c1)'>Encourage</span><span style='--sw:var(--none)'>No opinion</span><span style='--sw:var(--c2)'>Discourage</span></div>"
        f"<figcaption>Straw poll of the 15 Security Council members, as reported on the <a href='{_e(cands[0]['source_url'])}'>Wikipedia page on the selection</a>, "
        "which cites 1 for 8 Billion and Reuters. A speech names a candidate when their surname appears in its English or original text.</figcaption></figure>"
    )

    verdict_class = {
        "Matches": "ok",
        "Holds": "ok",
        "As expected": "ok",
        "Close": "near",
        "Close second": "near",
        "Depends on wording": "near",
    }
    claims = "".join(
        f"<tr><td><b>{_e(c['topic'])}</b></td><td>“{_e(c['quote'])}”<br><span class='small'><a href='{_e(c['url'])}'>{_e(c['source'])}</a></span></td>"
        f"<td>{_e(c['ours'])}<br><span class='small'>{_e(c['detail'])}</span></td><td><span class='verdict {verdict_class.get(c['verdict'], 'off')}'>{_e(c['verdict'])}</span></td></tr>"
        for c in pr["claims"]
    )
    claims_html = _p(
        "<b>The Assembly President closed the debate with a set of numbers. Counting the same things in the texts mostly bears him out.</b> "
        "The speaker totals and the rise of AI match almost exactly. Two claims depend on how you count: AI beats the phrase “climate change” but not climate language as a whole, "
        "and “peace” is the second word of the debate, just behind “security”."
    ) + (
        "<figure><h4>What was said about the debate, checked against the speeches</h4><div class='scroll'><table class='data claims'>"
        "<thead><tr><th>Claim</th><th>As reported</th><th>From the texts</th><th>Verdict</th></tr></thead>"
        f"<tbody>{claims}</tbody></table></div></figure>"
    )

    timeline = "".join(
        f"<li><time>{int(c['date'][8:])} Sep</time><div><b>{_e(c['event'])}</b><br><span class='small'>“{_e(c['quote'])}” · <a href='{_e(c['url'])}'>{_e(c['outlet'])}</a></span></div></li>"
        for c in pr["context"]
    )
    women = pr["women"]
    women_rate = women["women_and_girls_per_1000"]
    women_callout = (
        f"{_drill(women['count'], kind='women')} of {women['of']} speakers were introduced as “Her Excellency”: "
        + ", ".join(f"{k} {analyse_role(r)}" for r, k in women["by_role"])
        + f". Their speeches mention women, girls or gender {women_rate['women']:.2f} times per 1,000 words, against {women_rate['men']:.2f} in speeches by men."
    )
    return {
        "__NAMING_TITLE__": f"{n(most[0]['slug'])} and {n(most[1]['slug'])} are named most; naming stays close to home",
        "__NAMING__": naming,
        "__PRESS_TITLE__": "The world heard a narrower debate than the one given",
        "__PRESS__": press_html,
        "__PRESS_NOTE__": press_note,
        "__RACE_TITLE__": "One region campaigned for the next Secretary-General from the podium",
        "__RACE__": race_html,
        "__RACE_TABLE__": race_table,
        "__CLAIMS_TITLE__": "The UN's own summary mostly holds up",
        "__CLAIMS__": claims_html,
        "__TIMELINE__": timeline,
        "_women": women_callout,
    }


ROLE_WORDS = {
    "head_of_state_or_government": "heads of state or government",
    "foreign_minister": "foreign ministers",
    "deputy_head": "deputy heads",
    "diplomat": "ambassadors",
    "other_minister": "other ministers",
    "other": "other",
}


def analyse_role(role_group: str) -> str:
    return ROLE_WORDS.get(role_group, role_group)
