import pytest

from unga_speeches.analysis import mentions
from unga_speeches.sources import news


def test_extract_keeps_story_inside_a_nav_wrapper():
    body = "<p>" + "A long paragraph about the General Assembly debate and its speakers. " * 3 + "</p>"
    html = f"<html><head><title>T</title></head><body><nav><article>{body * 20}</article></nav><footer><p>{'x' * 80}</p></footer></body></html>"
    title, paragraphs = news.extract(html)
    assert title == "T"
    assert len(paragraphs) == 1  # repeats are dropped, the footer is furniture


def test_extract_prefers_the_article_with_the_most_text():
    teaser = "<article><p>" + "Teaser text that is long enough to count as a paragraph here. " + "</p></article>"
    story = (
        "<article>"
        + "".join(f"<p>Story paragraph number {i} with enough words to pass the length filter.</p>" for i in range(10))
        + "</article>"
    )
    _, paragraphs = news.extract(f"<html><body>{teaser}{story}</body></html>")
    assert paragraphs[0].startswith("Story paragraph number 0")


def test_named_takes_the_longest_name_and_skips_places():
    counts = mentions.named("Papua New Guinea and South Sudan met in the Gulf of Guinea; Russian forces and the Congo.")
    assert counts == {"PNG": 1, "SSD": 1, "RUS": 1}


def test_tone_takes_the_first_reporting_verb():
    pytest.importorskip("sklearn")  # press imports the topic model, which ships in the analysis group
    from unga_speeches.analysis import press

    assert press.tone("Kuwait calls out Iranian aggression, urges talks") == ("Alarm", "calls out")
    assert press.tone("Eswatini urges fair African representation now") == ("Appeal", "urges")
    assert press.tone("Bhutan: come build with us") == (press.NO_VERB, None)


def test_extract_skips_menus_and_link_only_items():
    story = "".join(f"<p>Paragraph {i} of the story, long enough to pass the length filter easily.</p>" for i in range(5))
    menu = "<li>Business News Reports Financial Inclusion Analysis and Data Trade Insights</li>"
    related = "<li><a href='/x'>Kicillof admits he is working to beat Milei in the 2027 election</a></li>"
    _, paragraphs = news.extract(f"<html><body><article>{story}<ul>{menu}{related}</ul></article></body></html>")
    assert len(paragraphs) == 5


def test_extract_reads_structured_data_when_the_page_has_no_story():
    body = " ".join(f"Speaker {i} took the floor. The speech lasted {i} minutes. Delegates listened closely." for i in range(10))
    ld = '{"@graph": [{"@type": "NewsArticle", "articleBody": "' + body + '"}]}'
    html = f"<html><head><script type='application/ld+json'>{ld}</script></head><body><p>Short.</p></body></html>"
    _, paragraphs = news.extract(html)
    assert sum(len(p.split()) for p in paragraphs) > 100
    assert all(len(p.split()) <= 3 * 8 for p in paragraphs)  # cut into three-sentence chunks


def test_panel_keeps_the_outlet_with_most_words_per_country_and_folds_territories():
    pytest.importorskip("sklearn")
    from unga_speeches.analysis import press

    def report(outlet, words):
        return {"outlet": outlet, "words": words, "paragraphs": [], "base_region": "Asia", "url": outlet + str(words)}

    news = [report("Big", 500), report("Big", 500), report("Small", 900), report("Hong Kong paper", 2000), report("UN News", 5000)]
    articles, table = press.panel(news, {"Big": "Japan", "Small": "Japan", "Hong Kong paper": "Hong Kong", "UN News": "United Nations"})
    chosen = {t["country"]: t["outlet"] for t in table}
    assert chosen == {
        "Japan": "Big",
        "China": "Hong Kong paper",
    }  # 1,000 words beat 900; Hong Kong counts as China; UN News is not national press
    assert {a["outlet"] for a in articles} == {"Big", "Hong Kong paper"}
