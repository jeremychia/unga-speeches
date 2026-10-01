"""The network of which delegations name which states: its layout, its hubs, and whether naming follows region, theory lean or bloc."""

import csv
import random
from collections import Counter

import networkx as nx
from sklearn.metrics import adjusted_rand_score

from unga_speeches.config import REFERENCE_DIR

SEED = 81  # fixed, so the layout and the chance baselines are the same on every build
SHUFFLES = 1000  # label shuffles behind each chance baseline
LAYOUT_ITERATIONS = 200
HUBS = 10
SPREAD = 0.97  # share of states inside the drawn square; the rest sit on its edge


def _graph(rows: list[dict], edges: list[dict]) -> nx.DiGraph:
    g = nx.DiGraph()
    for r in sorted(rows, key=lambda r: r["slug"]):
        g.add_node(r["slug"])
    for e in sorted(edges, key=lambda e: (e["from"], e["to"])):
        if e["from"] in g and e["to"] != e["from"]:
            g.add_edge(e["from"], e["to"], weight=e["times"])
    return g


def _same_share(g: nx.DiGraph, label: dict[str, str]) -> float:
    """Share of naming pairs whose two ends carry the same label, among pairs where both ends have one."""
    pairs = [(a, b) for a, b in g.edges if label.get(a) and label.get(b)]
    return sum(label[a] == label[b] for a, b in pairs) / len(pairs) if pairs else 0.0


def _rewired_share(g: nx.DiGraph, label: dict[str, str], rng: random.Random) -> float:
    """The same share after reconnecting the naming pairs at random while every state keeps how many it names and is named by."""
    pairs = [(a, b) for a, b in g.edges if label.get(a) and label.get(b)]
    sources, targets = [a for a, _ in pairs], [b for _, b in pairs]
    rng.shuffle(targets)
    return sum(label[a] == label[b] for a, b in zip(sources, targets, strict=True)) / len(pairs) if pairs else 0.0


def homophily(g: nx.DiGraph, label: dict[str, str]) -> dict:
    """How much more often states name states that share a label than chance predicts.

    Chance is measured two ways: shuffling the labels among states, and reconnecting the naming pairs at random while keeping
    each state's number of names, which allows for some states being named by everyone. p is the share of shuffles at or
    above what was seen."""
    rng = random.Random(SEED)
    observed = _same_share(g, label)
    nodes = [n for n in g.nodes if label.get(n)]
    values = [label[n] for n in nodes]
    shuffled, rewired = [], []
    for _ in range(SHUFFLES):
        rng.shuffle(values)
        shuffled.append(_same_share(g, dict(zip(nodes, values, strict=True))))
        rewired.append(_rewired_share(g, label, rng))
    base_shuffle, base_rewire = sum(shuffled) / SHUFFLES, sum(rewired) / SHUFFLES
    return {
        "observed": round(observed, 3),
        "chance_shuffled": round(base_shuffle, 3),
        "chance_rewired": round(base_rewire, 3),
        "ratio": round(observed / base_rewire, 2) if base_rewire else None,
        "p": round(sum(x >= observed for x in rewired) / SHUFFLES, 3),
        "pairs": sum(1 for a, b in g.edges if label.get(a) and label.get(b)),
    }


def layout(g: nx.DiGraph) -> dict[str, list[float]]:
    """Positions for the states that name or are named, from a seeded force layout, scaled to the unit square (see _spread)."""
    connected = [n for n in sorted(g.nodes) if g.degree(n)]
    u = nx.Graph()
    u.add_nodes_from(connected)
    for a, b, d in g.edges(data=True):
        w = u[a][b]["weight"] + d["weight"] if u.has_edge(a, b) else d["weight"]
        u.add_edge(a, b, weight=w)
    pos = nx.spring_layout(u, seed=SEED, iterations=LAYOUT_ITERATIONS, weight="weight")
    nodes = list(pos)
    xs, ys = _spread([pos[n][0] for n in nodes]), _spread([pos[n][1] for n in nodes])
    return {n: [round(x, 4), round(y, 4)] for n, x, y in zip(nodes, xs, ys, strict=True)}


def _spread(values: list[float]) -> list[float]:
    """Values scaled to the unit interval between the 3rd and 97th percentiles, with the few beyond pinned to the edge,
    so states that name one other state do not squeeze the rest into the middle."""
    ordered = sorted(values)
    low, high = ordered[int(len(ordered) * (1 - SPREAD))], ordered[int(len(ordered) * SPREAD) - 1]
    return [min(1.0, max(0.0, (v - low) / ((high - low) or 1))) for v in values]


def communities(g: nx.DiGraph, region: dict[str, str]) -> dict:
    """Groups the naming network falls into by itself, and how closely they follow regions (adjusted Rand index: 0 is chance)."""
    u = g.to_undirected()
    u.remove_nodes_from([n for n in list(u.nodes) if not u.degree(n)])
    found = nx.community.greedy_modularity_communities(u, weight="weight")
    groups = sorted((sorted(c) for c in found), key=lambda c: (-len(c), c[0]))
    member = {n: i for i, c in enumerate(groups) for n in c}
    labelled = [n for n in sorted(member) if region.get(n)]
    return {
        "groups": [{"members": c, "regions": dict(Counter(region.get(n, "Other") for n in c).most_common())} for c in groups],
        "modularity": round(nx.community.modularity(u, found, weight="weight"), 3),
        "rand_vs_region": round(adjusted_rand_score([region[n] for n in labelled], [member[n] for n in labelled]), 3),
    }


def taiwan_allies() -> set[str]:
    with (REFERENCE_DIR / "taiwan_allies.csv").open(encoding="utf-8") as f:
        return {r["slug"] for r in csv.DictReader(f)}


def taiwan(rows: list[dict], edges: list[dict], blocs: list[dict]) -> dict:
    """Who named Taiwan, set against the states that recognise it, and the regions, leans and blocs of both."""
    allies = taiwan_allies()
    named = {e["from"] for e in edges if e["to"] == "TWN"}
    spoke = {r["slug"] for r in rows}
    bloc_of = {m: b["label"] for b in blocs for m in b["members"]}
    by_slug = {r["slug"]: r for r in rows}

    def profile(slugs: set[str]) -> dict:
        present = [by_slug[s] for s in sorted(slugs) if s in by_slug]  # sorted, so tied counts keep one order
        return {
            "regions": dict(Counter(r["region"] for r in present).most_common()),
            "leans": dict(Counter(r["lean"] for r in present).most_common()),
            "blocs": dict(Counter(bloc_of.get(r["slug"], "") for r in present).most_common()),
        }

    return {
        "named_by": sorted(named),
        "allies": sorted(allies),
        "allies_speaking": sorted(allies & spoke),
        "allies_naming": sorted(allies & named),
        "allies_silent": sorted((allies & spoke) - named),
        "non_allies_naming": sorted(named - allies),
        "named_by_profile": profile(named),
        "all_profile": profile(spoke),
        "source_url": "https://www.congress.gov/crs_external_products/IF/PDF/IF12646/IF12646.6.pdf",
    }


def build(rows: list[dict], edges: list[dict], blocs: list[dict]) -> dict:
    g = _graph(rows, edges)
    region = {r["slug"]: r["region"] for r in rows if r["status"] == "member_state" or r["slug"] in ("palestine-state", "holy-see")}
    lean = {r["slug"]: r["lean"] for r in rows if r.get("lean") and r["lean"] != "No clear lean"}
    bloc = {m: b["label"] for b in blocs for m in b["members"]}
    between = nx.betweenness_centrality(g)
    hubs = sorted(g.nodes, key=lambda n: (-g.in_degree(n), n))[:HUBS]
    return {
        "layout": layout(g),
        "edges": [{"from": a, "to": b, "times": d["weight"]} for a, b, d in sorted(g.edges(data=True))],
        "hubs": [{"slug": n, "named_by": g.in_degree(n), "names": g.out_degree(n), "betweenness": round(between[n], 3)} for n in hubs],
        "brokers": [{"slug": n, "betweenness": round(between[n], 3)} for n in sorted(g.nodes, key=lambda n: (-between[n], n))[:HUBS]],
        "homophily": {"region": homophily(g, region), "lean": homophily(g, lean), "bloc": homophily(g, bloc)},
        "communities": communities(g, region),
        "taiwan": taiwan(rows, edges, blocs),
    }
