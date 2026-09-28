"""Topics from a fixed-seed NMF model over TF-IDF, labelled by anchor terms so a refit keeps its names."""

import csv
import re
from dataclasses import dataclass

import numpy as np
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

from unga_speeches.analysis.corpus import Speech
from unga_speeches.config import REFERENCE_DIR

N_TOPICS = 12
UNLABELLED = "Unlabelled: "
TOP_TERMS = 15
URLS = re.compile(r"https?://\S+|www\.\S+|\S+\.(gov|org|com|int)\S*")

# words every speech uses, and the filler of speech transcripts, which would otherwise form topics of their own
BOILERPLATE = set(
    """united nations general assembly president excellencies excellency mr madam distinguished delegates session secretary
    eighty 81st ladies gentlemen thank today year years world country countries international people peoples like also must us
    one let would make time even need new global support continue including well many every way sir dear colleagues heads state
    government ministers ambassadors rahman khalilur guterres antónio antonio annalena baerbock mister senor seventy eightieth ms
    dr friends applause mrs know going want did think don say said simply precisely question ask asked context express behalf
    reaffirm particular particularly just really things thing lot got come look good great yes okay right saying says tell told
    mean able different simple shape generation societies spirit populations indeed therefore hence furthermore moreover regard
    regards occasion allow congratulate election tenure wish outgoing successful hand important deal greater""".split()
)

# a topic takes the label whose anchors appear most among its top terms; a refit can move topics, so review labels after one
LABELS = [
    ("Sahel security and African solidarity", {"sahel", "tribute", "solidarity", "armed groups"}),
    ("Russia, Europe and the rules of the order", {"rules", "russia", "europe", "companies", "governments"}),
    ("Gulf and Arab regional stability", {"security stability", "palestinian", "brotherly", "blessings", "syria"}),
    ("Organised crime, drugs and youth", {"crime", "organized crime", "drug", "trafficking", "young"}),
    ("Pacific islands, oceans and fossil fuels", {"pacific", "ocean", "island", "fossil", "sea-level"}),
    ("Caribbean vulnerability and reparatory justice", {"caribbean", "caricom", "reparatory", "hurricane", "haitian"}),
    ("Small and middle states on rules, voice and delivery", {"asean", "deliver", "differences", "size", "voice", "promise"}),
    ("Development finance, debt and health", {"financing", "debt", "health", "finance", "agriculture"}),
    ("Eurasian connectivity and neighbours", {"asia", "connectivity", "railway", "mutual respect", "mutual"}),
    ("War, missiles and military confrontation", {"terrorists", "missiles", "soldiers", "military", "iranian"}),
    ("Russia's aggression and accountability", {"aggression", "court", "crimes", "violations", "integrity"}),
    ("Russia, sea lanes and nuclear risk", {"navigation", "strait", "black sea", "freedom navigation", "nuclear", "sea"}),
    ("Transnational crime and illicit networks", {"criminal networks", "transnational", "illicit", "networks", "criminal"}),
]


@dataclass
class Topic:
    label: str
    terms: list[str]
    speeches: int  # speeches whose largest topic this is
    weights: list[float]  # one per speech, summing to 1 across topics


def _stop_words() -> list[str]:
    names = set()
    with (REFERENCE_DIR / "delegations.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            names |= set(re.findall(r"[a-z]+", row["name"].lower()))
    return sorted(ENGLISH_STOP_WORDS | BOILERPLATE | names)


def fit(speeches: list[Speech]) -> list[Topic]:
    vectoriser = TfidfVectorizer(
        stop_words=_stop_words(),
        max_df=0.5,
        min_df=5,
        ngram_range=(1, 2),
        sublinear_tf=True,
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z\-]{2,}\b",
    )
    matrix = vectoriser.fit_transform([URLS.sub(" ", s.text) for s in speeches])
    terms = vectoriser.get_feature_names_out()
    model = NMF(n_components=N_TOPICS, init="nndsvd", random_state=0, max_iter=3000, tol=1e-5)
    doc_topic = model.fit_transform(matrix)
    shares = doc_topic / np.clip(doc_topic.sum(axis=1, keepdims=True), 1e-12, None)
    dominant = shares.argmax(axis=1)

    top = [[terms[j] for j in row.argsort()[::-1][:TOP_TERMS]] for row in model.components_]
    labels = _assign_labels(top)
    return [
        Topic(label=labels[i], terms=top[i][:10], speeches=int((dominant == i).sum()), weights=[round(float(w), 4) for w in shares[:, i]])
        for i in range(N_TOPICS)
    ]


def _assign_labels(top: list[list[str]]) -> list[str]:
    """Greedy best match of topics to labels by anchor overlap; a topic with no overlap is named by its terms."""
    scores = [(len(anchors & set(terms)), t, n) for t, terms in enumerate(top) for n, (_, anchors) in enumerate(LABELS)]
    labels, used_topics, used_labels = {}, set(), set()
    for score, t, n in sorted(scores, reverse=True):
        if score and t not in used_topics and n not in used_labels:
            labels[t] = LABELS[n][0]
            used_topics.add(t)
            used_labels.add(n)
    return [labels.get(t, UNLABELLED + ", ".join(top[t][:3])) for t in range(len(top))]
