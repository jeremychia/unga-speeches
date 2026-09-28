"""Every figure the 2026 page shows, computed in one place and written as data.json."""

import re
import statistics
from collections import Counter, defaultdict
from difflib import SequenceMatcher

import numpy as np
import textstat
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from unga_speeches.analysis import lexicons, topics
from unga_speeches.analysis.corpus import Speech, load
from unga_speeches.config import session_year

REGIONS = ["Africa", "Americas", "Asia", "Europe", "Oceania"]
ROLE_GROUPS = ["head_of_state_or_government", "deputy_head", "foreign_minister", "other_minister", "diplomat"]
OUTLIER_Z = 2.5
# a speech leans towards a theory only if its vocabulary for it sits this far above the debate's average
LEAN_Z = 0.5
NO_LEAN = "No clear lean"
CHARTER_OR_LAW = re.compile(r"\bcharter\b|international law", re.I)


def _z(values: list[float]) -> list[float]:
    mean, sd = statistics.fmean(values), statistics.pstdev(values) or 1.0
    return [(v - mean) / sd for v in values]


def _histogram(values: list[float], width: float, start: float = 0.0) -> list[dict]:
    counts = Counter(int((v - start) // width) for v in values)
    return [
        {"from": start + b * width, "to": start + (b + 1) * width, "count": counts.get(b, 0)} for b in range(min(counts), max(counts) + 1)
    ]


def _readability(s: Speech) -> dict:
    sentences = max(1, textstat.sentence_count(s.text))
    return {
        "grade": round(textstat.flesch_kincaid_grade(s.text), 1),
        "ease": round(textstat.flesch_reading_ease(s.text), 1),
        "sentence_words": round(s.words / sentences, 1),
    }


def build(session: int) -> dict:
    speeches = load(session)
    fitted = topics.fit(speeches)
    rows = []
    for i, s in enumerate(speeches):
        weights = [t.weights[i] for t in fitted]
        rates = lexicons.frame_rates(s.text)
        rows.append(
            {
                "slug": s.slug,
                "delegation": s.delegation,
                "iso3": s.iso3,
                "region": s.region,
                "status": s.status,
                "speaker": s.speaker,
                "title": s.title,
                "role": s.role,
                "role_group": s.role_group,
                "date": s.date,
                "language": s.original_language or "not known",
                "english_kind": s.english_kind,
                "words": s.words,
                "page_url": s.page_url,
                "english_url": s.english_url,
                "delivered_share": s.delivered_share,
                "topic": fitted[int(np.argmax(weights))].label,
                "topic_weights": weights,
                "frames": rates,
                "issues": [k for k, v in lexicons.issues(s.text).items() if v],
                "markers": lexicons.markers(s.text),
                **({"readability": _readability(s)} if s.english_kind != "transcript" else {}),
            }
        )

    states = [r for r in rows if r["status"] == "member_state"]
    overview = _overview(rows, states)
    overview["charter_or_law"] = sum(bool(CHARTER_OR_LAW.search(s.text)) for s in speeches)
    return {
        "session": session,
        "year": session_year(session),
        "overview": overview,
        "distributions": _distributions(rows, states),
        "anomalies": _anomalies(speeches, rows),
        "topics": _topics(fitted, rows),
        "issues": _issues(rows),
        "markers": _shares(rows, "markers", lexicons.MARKERS),
        "frames": _frames(speeches, rows),
        "speeches": rows,
    }


def _overview(rows: list[dict], states: list[dict]) -> dict:
    words = [r["words"] for r in rows]
    return {
        "speeches": len(rows),
        "member_states": len(states),
        "words_total": sum(words),
        "words_median": int(statistics.median(words)),
        "heads_share": round(sum(r["role_group"] == "head_of_state_or_government" for r in states) / len(states), 3),
        "english_kinds": dict(Counter(r["english_kind"] for r in rows)),
        "languages": Counter(r["language"] for r in rows).most_common(),
        "roles": [[g, sum(r["role_group"] == g for r in states)] for g in ROLE_GROUPS],
    }


def _distributions(rows: list[dict], states: list[dict]) -> dict:
    statements = [r for r in rows if "readability" in r]
    by_day = defaultdict(list)
    for r in states:
        by_day[r["date"]].append(r)
    return {
        "words": _histogram([r["words"] for r in rows], 250),
        "words_by_role": [
            {"role_group": g, "median": int(statistics.median(v)), "count": len(v)}
            for g in ROLE_GROUPS
            if (v := [r["words"] for r in states if r["role_group"] == g])
        ],
        "grade": _histogram([r["readability"]["grade"] for r in statements], 1, 6),
        "grade_median": statistics.median(r["readability"]["grade"] for r in statements),
        "sentence_words_median": statistics.median(r["readability"]["sentence_words"] for r in statements),
        "statements_scored": len(statements),
        "delivered": _histogram([r["delivered_share"] for r in rows if r["delivered_share"] is not None], 0.05),
        "delivered_median": statistics.median(r["delivered_share"] for r in rows if r["delivered_share"] is not None),
        "days": [
            {
                "date": d,
                "speeches": len(v),
                "heads_share": round(sum(r["role_group"] == "head_of_state_or_government" for r in v) / len(v), 3),
                "words_median": int(statistics.median(r["words"] for r in v)),
            }
            for d, v in sorted(by_day.items())
        ],
    }


def _anomalies(speeches: list[Speech], rows: list[dict]) -> dict:
    # compare lengths within one kind of text, since a transcript also carries the interpreter's words
    long_short = []
    for kind in ("statement", "transcript"):
        group = [r for r in rows if r["english_kind"] == kind]
        for r, z in zip(group, _z([r["words"] for r in group]), strict=True):
            if abs(z) >= OUTLIER_Z:
                long_short.append({"slug": r["slug"], "delegation": r["delegation"], "words": r["words"], "z": round(z, 1), "kind": kind})
    statements = [r for r in rows if "readability" in r]
    readability = [
        {
            "slug": r["slug"],
            "delegation": r["delegation"],
            "grade": r["readability"]["grade"],
            "sentence_words": r["readability"]["sentence_words"],
            "z": round(z, 1),
        }
        for r, z in zip(statements, _z([r["readability"]["grade"] for r in statements]), strict=True)
        if abs(z) >= OUTLIER_Z
    ]

    matrix = TfidfVectorizer(stop_words="english", sublinear_tf=True, min_df=2).fit_transform([s.text for s in speeches])
    similarity = cosine_similarity(matrix)
    np.fill_diagonal(similarity, np.nan)
    distinct = np.nanmean(similarity, axis=1)
    order = np.argsort(distinct)
    pairs = [
        {"a": rows[i]["delegation"], "b": rows[j]["delegation"], "similarity": round(float(similarity[i, j]), 3)}
        for i in range(len(rows))
        for j in range(i + 1, len(rows))
    ]
    delivered = sorted((r for r in rows if r["delivered_share"] is not None), key=lambda r: r["delivered_share"])
    return {
        "length": sorted(long_short, key=lambda a: -a["z"]),
        "readability": sorted(readability, key=lambda a: -a["z"]),
        "most_distinctive": [{"delegation": rows[i]["delegation"], "similarity": round(float(distinct[i]), 3)} for i in order[:5]],
        "most_typical": [{"delegation": rows[i]["delegation"], "similarity": round(float(distinct[i]), 3)} for i in order[::-1][:5]],
        "similar_pairs": [
            {**p, "longest_shared_words": _longest_shared_run(speeches, p["a"], p["b"])}
            for p in sorted(pairs, key=lambda p: -p["similarity"])[:5]
        ],
        "least_delivered": [{"delegation": r["delegation"], "delivered_share": r["delivered_share"]} for r in delivered[:6]],
    }


def _longest_shared_run(speeches: list[Speech], a: str, b: str) -> int:
    """Length in words of the longest passage two speeches share, which separates copied text from shared vocabulary."""
    x, y = (next(s.text.split() for s in speeches if s.delegation == name) for name in (a, b))
    return max(block.size for block in SequenceMatcher(None, x, y, autojunk=False).get_matching_blocks())


def _topics(fitted: list[topics.Topic], rows: list[dict]) -> list[dict]:
    out = []
    for t_index, t in enumerate(fitted):
        leaders = sorted(range(len(rows)), key=lambda i: -t.weights[i])[:5]
        by_region = {}
        for region in REGIONS:
            members = [r["topic_weights"][t_index] for r in rows if r["region"] == region]
            by_region[region] = round(statistics.fmean(members), 3) if members else 0
        out.append(
            {
                "label": t.label,
                "terms": t.terms,
                "speeches": t.speeches,
                "leaders": [rows[i]["delegation"] for i in leaders],
                "by_region": by_region,
            }
        )
    return sorted(out, key=lambda t: -t["speeches"])


def _issues(rows: list[dict]) -> list[dict]:
    return sorted(_shares(rows, "issues", lexicons.ISSUES), key=lambda i: -i["speeches"])


def _shares(rows: list[dict], field: str, names) -> list[dict]:
    """For each name, how many speeches carry it in the given field, overall and as a share of each region."""
    out = []
    for name in names:
        by_region = {}
        for region in REGIONS:
            members = [r for r in rows if r["region"] == region]
            by_region[region] = round(sum(name in r[field] for r in members) / len(members), 3) if members else 0
        count = sum(name in r[field] for r in rows)
        out.append({"name": name, "speeches": count, "share": round(count / len(rows), 3), "by_region": by_region})
    return out


def _frames(speeches: list[Speech], rows: list[dict]) -> dict:
    names = list(lexicons.FRAMES)
    # standardise each theory's rate across speeches, so a speech's lean is relative to the debate, not to vocabulary size
    z = {f: _z([r["frames"][f] for r in rows]) for f in names}
    for i, r in enumerate(rows):
        r["frame_z"] = {f: round(z[f][i], 2) for f in names}
        strongest = max(names, key=lambda f: z[f][i])
        r["lean"] = strongest if z[strongest][i] >= LEAN_Z else NO_LEAN
    by_group = {}
    for key, groups in (("region", REGIONS), ("role_group", ROLE_GROUPS)):
        by_group[key] = [
            {"group": g, "count": len(m), **{f: round(statistics.fmean(r["frames"][f] for r in m), 2) for f in names}}
            for g in groups
            if (m := [r for r in rows if r[key] == g])
        ]
    exemplars = {}
    for f in names:
        top = sorted(range(len(rows)), key=lambda i: -z[f][i])[:3]
        exemplars[f] = [
            {
                "slug": rows[i]["slug"],
                "delegation": rows[i]["delegation"],
                "speaker": rows[i]["speaker"],
                "rate": rows[i]["frames"][f],
                "z": round(z[f][i], 1),
                "quote": lexicons.densest_sentence(speeches[i].verbatim, f),
                "english_kind": rows[i]["english_kind"],
                "english_url": rows[i]["english_url"],
                "url": rows[i]["page_url"],
            }
            for i in top
        ]
    return {
        "names": names,
        "lexicon": lexicons.FRAMES,
        "mean": {f: round(statistics.fmean(r["frames"][f] for r in rows), 2) for f in names},
        "lean_counts": dict(Counter(r["lean"] for r in rows)),
        "lean_by_region": {g: dict(Counter(r["lean"] for r in rows if r["region"] == g)) for g in REGIONS},
        "by_group": by_group,
        "exemplars": exemplars,
    }
