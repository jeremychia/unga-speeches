"""How alike speeches are in vocabulary: the closest pairs, and blocs of speeches that sound alike."""

import re
from collections import Counter
from difflib import SequenceMatcher

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from unga_speeches.analysis.corpus import Speech
from unga_speeches.analysis.topics import URLS, _stop_words

N_BLOCS = 8
TOP_PAIRS = 20
BLOC_WORDS = 8
# a bloc whose members are barely closer to each other than to everyone else is reported as loose
LOOSE_RATIO = 1.05

# a bloc takes the label whose anchors appear most among its top words, as topics do
BLOC_LABELS = [
    ("Europe and the West: Russia and the rules", {"russia", "rules", "europe", "aggression", "freedom"}),
    ("Francophone and central Africa: the Sahel and solidarity", {"sahel", "solidarity", "youth", "calls"}),
    ("Africa and South Asia: finance and governance", {"governance", "debt", "finance", "digital", "investment"}),
    ("The Arab world: Palestine and Syria", {"palestinian", "israeli", "brotherly", "blessings", "syria"}),
    ("The Caribbean and island states: reparations and resilience", {"caribbean", "caricom", "reparatory", "hurricane", "vulnerability"}),
    ("Latin America: crime and democracy", {"crime", "democracy", "trafficking", "young"}),
    ("The Pacific: the ocean and fossil fuels", {"pacific", "ocean", "fossil", "sea-level", "marine"}),
    ("Asia and neighbours: connectivity and relations", {"asia", "initiative", "mutual", "relations", "connectivity"}),
]


def tfidf(speeches: list[Speech]):
    """The TF-IDF matrix every similarity figure is computed from, with its terms."""
    vectoriser = TfidfVectorizer(
        stop_words=_stop_words(), sublinear_tf=True, min_df=2, max_df=0.5, token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z\-]{2,}\b"
    )
    matrix = vectoriser.fit_transform([URLS.sub(" ", s.text) for s in speeches])
    return matrix, vectoriser.get_feature_names_out()


CONTEXT_WORDS = 25
_BARE = re.compile(r"[^\w]+")


def shared_passage(a: str, b: str) -> dict:
    """The longest run of words two texts share, matched ignoring case and punctuation, shown as written with its context in each."""
    x, y = a.split(), b.split()
    bare_x, bare_y = [_BARE.sub("", w).lower() for w in x], [_BARE.sub("", w).lower() for w in y]
    block = max(SequenceMatcher(None, bare_x, bare_y, autojunk=False).get_matching_blocks(), key=lambda m: m.size)

    def context(words: list[str], start: int) -> dict:
        return {
            "before": " ".join(words[max(0, start - CONTEXT_WORDS) : start]),
            "passage": " ".join(words[start : start + block.size]),
            "after": " ".join(words[start + block.size : start + block.size + CONTEXT_WORDS]),
            "cut_start": start > CONTEXT_WORDS,
            "cut_end": start + block.size + CONTEXT_WORDS < len(words),
        }

    return {"words": block.size, "a": context(x, block.a), "b": context(y, block.b)}


def matrices(speeches: list[Speech]):
    """(TF-IDF matrix, its terms, speech-by-speech cosine similarity): the one definition of "alike" the page uses."""
    matrix, terms = tfidf(speeches)
    return matrix, terms, cosine_similarity(matrix)


def build(speeches: list[Speech], matrix, terms, similarity) -> dict:
    n = len(speeches)

    upper = [(similarity[i, j], i, j) for i in range(n) for j in range(i + 1, n)]
    pairs = []
    for sim, i, j in sorted(upper, reverse=True)[:TOP_PAIRS]:
        # the speech text, without transcript headers or the chair's words, which every transcript shares
        passage = shared_passage(speeches[i].text, speeches[j].text)
        pairs.append(
            {
                "a": speeches[i].slug,
                "b": speeches[j].slug,
                "similarity": round(float(sim), 3),
                "longest_shared_words": passage["words"],
                "shared": passage,
            }
        )

    labels = AgglomerativeClustering(n_clusters=N_BLOCS, linkage="ward").fit_predict(matrix.toarray())
    blocs = []
    for c in sorted(set(labels), key=lambda c: -(labels == c).sum()):
        members = np.where(labels == c)[0]
        others = np.where(labels != c)[0]
        within = similarity[np.ix_(members, members)]
        cohesion = (within.sum() - len(members)) / (len(members) * (len(members) - 1)) if len(members) > 1 else 1.0
        outside = float(similarity[np.ix_(members, others)].mean())
        centroid = np.asarray(matrix[members].mean(axis=0)).ravel()
        words = [terms[j] for j in centroid.argsort()[::-1][:BLOC_WORDS]]
        blocs.append(
            {
                "members": [speeches[i].slug for i in members],
                "words": words,
                "within": round(float(cohesion), 3),
                "outside": round(outside, 3),
                "loose": bool(cohesion < outside * LOOSE_RATIO),
                "regions": dict(Counter(speeches[i].region for i in members).most_common()),
            }
        )
    for bloc, label in zip(blocs, _label(blocs), strict=True):
        bloc["label"] = label
    return {
        "order": [s.slug for s in speeches],
        # every pair's similarity in thousandths (0 to 1000), so the page can shade the map for any country
        "matrix": [[int(round(1000 * v)) for v in row] for row in similarity],
        "pairs": pairs,
        "blocs": blocs,
    }


def _label(blocs: list[dict]) -> list[str]:
    scores = sorted(
        ((len(anchors & set(b["words"])), i, n) for i, b in enumerate(blocs) for n, (_, anchors) in enumerate(BLOC_LABELS)), reverse=True
    )
    names, used_blocs, used_labels = {}, set(), set()
    for score, i, n in scores:
        if score and i not in used_blocs and n not in used_labels:
            names[i] = BLOC_LABELS[n][0]
            used_blocs.add(i)
            used_labels.add(n)
    # a bloc no anchor fits is named by its region mix and words, so it is never silently mislabelled
    return [names.get(i, f"{next(iter(b['regions']))}: {', '.join(b['words'][:3])}") for i, b in enumerate(blocs)]
