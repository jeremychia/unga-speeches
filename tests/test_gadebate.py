from pathlib import Path

from unga.gadebate import parse_page, parse_sitemap
from unga.render import escape_markdown

FIXTURES = Path(__file__).parent / "fixtures"


def test_sitemap_keeps_only_english_speaker_pages_for_the_session():
    found = parse_sitemap((FIXTURES / "sitemap_page5.xml").read_bytes(), {81})
    assert set(found) == {(81, "singapore"), (81, "france")}


def test_page_with_english_and_portuguese_statements():
    page = parse_page((FIXTURES / "81_brazil.html").read_text(), 81, "brazil")
    assert page.speaker_name == "Luiz Inácio Lula Da Silva"
    assert page.speaker_title == "President"
    assert page.date == "2026-09-22"
    assert [(s.language, s.url.rsplit("/", 1)[-1]) for s in page.statements] == [("en", "br_en.pdf"), ("pt", "br_pt.pdf")]
    assert page.has_transcript


def test_page_with_no_statement_pdf():
    page = parse_page((FIXTURES / "81_united-states-america.html").read_text(), 81, "united-states-america")
    assert page.speaker_name == "Donald Trump"
    assert page.statements == []
    assert page.node_id == "81193"


def test_escape_markdown_keeps_characters_visible():
    assert escape_markdown("1. *Mr* President_ #") == "1\\. \\*Mr\\* President\\_ \\#"


def test_word_opening_with_a_combining_mark_flags_a_broken_indic_font():
    from unga.pdftext import _misordered_mark_share

    assert _misordered_mark_share("বিসমিল্লাহির রাহমানির রাহিম") == 0
    assert _misordered_mark_share("েসতমল্লাতহর রাহমাতের") == 0.5
