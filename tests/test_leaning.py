import csv

from unga_speeches.config import REFERENCE_DIR
from unga_speeches.sources import leaning


def test_site_keeps_the_registered_name_under_shared_suffixes():
    assert leaning._site("www.abc.net.au") == "abc.net.au"
    assert leaning._site("news.com.au") == "news.com.au"
    assert leaning._site("english.news.cn") == "news.cn"
    assert leaning._site("www.malaymail.com") == "malaymail.com"


def test_labels_fold_mbfc_values_into_five_positions():
    assert leaning.LABELS["least biased"] == "Centre"
    assert leaning.LABELS["extreme right"] == "Right"
    assert leaning.LABELS.get("pro-science", leaning.NOT_RATED) == leaning.NOT_RATED  # no left-right position


def test_a_page_without_a_source_line_rates_the_site_it_links_to_most():
    page = (
        '<a href="https://mediabiasfactcheck.com/x/">x</a>'
        + '<a href="https://www.malaymail.com/news/1">a</a>' * 3
        + '<a href="https://www.reuters.com/y">r</a>'
    )
    assert leaning._most_linked(page) == "malaymail.com"


def test_every_sampled_outlet_has_a_known_leaning_and_rated_ones_link_their_page():
    with (REFERENCE_DIR / "outlets.csv").open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["status"] == "in_sample" and r["country"] not in ("United Nations", "—")]
    for r in rows:
        assert r["leaning"] in leaning.LEANINGS, r["outlet"]
        assert r["state_media"] in ("yes", "no"), r["outlet"]
        if r["leaning"] != leaning.NOT_RATED:
            assert r["mbfc_url"].startswith(leaning.MBFC), r["outlet"]


def _row(leaning_label="Left-centre", bias="Left-Center"):
    return {"outlet": "Paper", "domain": "paper.com", "mbfc_url": "https://mediabiasfactcheck.com/paper/", "mbfc_bias": bias,
            "factual_reporting": "High", "leaning": leaning_label, "state_media": "no"}  # fmt: skip


def test_history_opens_a_version_on_change_and_only_refreshes_dates_otherwise(tmp_path, monkeypatch):
    monkeypatch.setattr(leaning, "HISTORY", tmp_path / "history.json")
    leaning.update_history([_row()], {"Paper": "2026-01-01"}, "2026-09-29")
    leaning.update_history([_row()], {"Paper": "2026-02-01"}, "2026-10-06")
    history = leaning.update_history([_row("Centre", "Least Biased")], {"Paper": "2026-10-10"}, "2026-10-13")
    assert [(h["leaning"], h["valid_from"], h["valid_to"], h["is_current"]) for h in history] == [
        ("Left-centre", "2026-09-29", "2026-10-13", False),
        ("Centre", "2026-10-13", None, True),
    ]
    assert history[0]["last_checked"] == "2026-10-06" and history[0]["mbfc_updated"] == "2026-02-01"


def test_committed_history_has_one_current_version_per_outlet_matching_the_registry():
    history = leaning.load_history()
    by_outlet = {}
    for h in history:
        by_outlet.setdefault(h["outlet"], []).append(h)
    with (REFERENCE_DIR / "outlets.csv").open(encoding="utf-8") as f:
        registry = {r["outlet"]: r for r in csv.DictReader(f)}
    for outlet, versions in by_outlet.items():
        current = [v for v in versions if v["is_current"]]
        assert len(current) == 1 and current[0]["valid_to"] is None, outlet
        for earlier, later in zip(versions, versions[1:], strict=False):
            assert earlier["valid_to"] == later["valid_from"], outlet  # no gaps, no overlaps
        if registry[outlet]["status"] == "in_sample":
            assert all(current[0][k] == registry[outlet][k] for k in leaning.TRACKED), outlet
