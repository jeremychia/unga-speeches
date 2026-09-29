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
