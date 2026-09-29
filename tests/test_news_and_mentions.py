from unga_speeches.analysis import mentions, press
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
    assert press.tone("Kuwait calls out Iranian aggression, urges talks") == ("Alarm", "calls out")
    assert press.tone("Eswatini urges fair African representation now") == ("Appeal", "urges")
    assert press.tone("Bhutan: come build with us") == (press.NO_VERB, None)
