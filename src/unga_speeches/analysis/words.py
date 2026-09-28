"""Word counts: the debate's commonest words, each region's distinctive words, and each speech's own."""

import math
import re
from collections import Counter

import numpy as np

from unga_speeches.analysis.corpus import Speech
from unga_speeches.analysis.topics import URLS, _stop_words

# letters of any alphabet, so "antónio" stays one word; a contraction such as "doesn't" is dropped whole
WORD = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*")
EXTRA_STOP = {"prime", "minister", "ministers", "honour", "honor", "pleased", "behalf"}
# the session's theme, "Restoring trust, managing transformation: a United Nations that delivers for all"; phrases made only of it echo the title
THEME = {"theme", "restoring", "restore", "trust", "managing", "transformation", "delivers", "deliver"}
# job titles that survive as word pairs
TITLE_PHRASES = {"foreign affairs", "external affairs", "general assembly", "united nations"}
TOP_WORDS = 30
TOP_PHRASES = 20
REGION_WORDS = 10
SPEECH_WORDS = 10
SIMILAR = 3


def _tokens(text: str, stop: set[str]) -> list[str]:
    words = (w for w in WORD.findall(URLS.sub(" ", text.lower())) if "'" not in w and "’" not in w)
    return [w for w in words if len(w) > 2 and w not in stop and w not in EXTRA_STOP]


def common(speeches: list[Speech]) -> dict:
    """The words and two-word phrases used most, with how many speeches use each."""
    stop = set(_stop_words())
    words, phrases, word_speeches, phrase_speeches = Counter(), Counter(), Counter(), Counter()
    for s in speeches:
        tokens = _tokens(s.text, stop)
        pairs = [f"{a} {b}" for a, b in zip(tokens, tokens[1:], strict=False)]
        words.update(tokens)
        phrases.update(pairs)
        word_speeches.update(set(tokens))
        phrase_speeches.update(set(pairs))
    return {
        "words": [{"word": w, "count": n, "speeches": word_speeches[w]} for w, n in words.most_common(TOP_WORDS)],
        "phrases": [
            {"phrase": p, "count": n, "speeches": phrase_speeches[p]}
            for p, n in phrases.most_common(TOP_PHRASES * 2)
            if not set(p.split()) <= THEME and p not in TITLE_PHRASES
        ][:TOP_PHRASES],
    }


def distinctive_by_group(speeches: list[Speech], groups: list[str], key) -> dict[str, list[dict]]:
    """Words each group uses more than the rest, by weighted log-odds with an informative Dirichlet prior (Monroe, Colaresi and Quinn, 2008)."""
    stop = set(_stop_words())
    counts = {g: Counter() for g in groups}
    for s in speeches:
        group = key(s)
        if group in counts:
            counts[group].update(_tokens(s.text, stop))
    total = sum(counts.values(), Counter())
    prior_total = sum(total.values())
    out = {}
    for g in groups:
        mine, rest = counts[g], total - counts[g]
        n_mine, n_rest = sum(mine.values()), sum(rest.values())
        scored = []
        for word, prior in total.items():
            if prior < 10 or mine[word] < 5:
                continue
            a = mine[word] + prior
            b = rest[word] + prior
            delta = math.log(a / (n_mine + prior_total - a)) - math.log(b / (n_rest + prior_total - b))
            scored.append((delta / math.sqrt(1 / a + 1 / b), word))
        out[g] = [{"word": w, "z": round(z, 1), "count": mine[w]} for z, w in sorted(scored, reverse=True)[:REGION_WORDS]]
    return out


def per_speech(speeches: list[Speech], matrix, terms, similarity) -> list[dict]:
    """Each speech's most distinctive words (highest TF-IDF) and its most similar speeches."""
    near_all = similarity.copy()
    np.fill_diagonal(near_all, -1)
    out = []
    for i in range(len(speeches)):
        row = matrix[i].toarray().ravel()
        top = row.argsort()[::-1][:SPEECH_WORDS]
        near = near_all[i].argsort()[::-1][:SIMILAR]
        out.append(
            {
                "words": [terms[j] for j in top if row[j] > 0],
                "similar": [
                    {"slug": speeches[j].slug, "delegation": speeches[j].delegation, "similarity": round(float(similarity[i, j]), 3)}
                    for j in near
                ],
            }
        )
    return out


SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"“])")
SALUTATION = re.compile(r"madam president|mr\.? president|excellencies|secretary-general", re.I)


def representative_sentence(verbatim: str, distinctive: list[str]) -> str:
    """The sentence carrying the most of a speech's distinctive words, from its verbatim text; ties go to the earlier sentence."""
    wanted = set(distinctive)
    best, best_count = "", 0
    for sentence in SENTENCE.split(verbatim):
        sentence = " ".join(sentence.split())
        if not 60 <= len(sentence) <= 320 or SALUTATION.search(sentence):
            continue
        count = len(wanted & {w.strip(".,;:!?()“”\"'").lower() for w in sentence.split()})
        if count > best_count:
            best, best_count = sentence, count
    best = re.sub(r"(\w)[\u2010\u00ad] (\w)", r"\1\2", best)
    # a paragraph number that follows the sentence in a numbered statement, e.g. "... ocean state. 60."
    return re.sub(r"\s+\d{1,3}\.$", "", best)
