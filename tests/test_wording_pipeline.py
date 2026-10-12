import pandas as pd
import pytest

from unga_speeches.analysis import wording, wording_check
from unga_speeches.sources import votes

LONG = " filler" * wording.MIN_WORDS


def test_classify_drops_short_texts_and_leaves_gaza_empty_before_2024():
    frame = pd.DataFrame(
        {
            "year": [2022, 2023, 2026],
            "iso3": ["AAA", "BBB", "CCC"],
            "delegation": ["A", "B", "C"],
            "english_text_clean": [
                "Russia's war of aggression against Ukraine." + LONG,
                "I introduce the pre-recorded statement of the President.",
                "In Gaza, Israeli strikes continue." + LONG,
            ],
        }
    )
    out = wording.classify(frame)
    assert list(out.iso3) == ["AAA", "CCC"]
    assert out.ukraine.tolist() == [wording.UKRAINE_CLASSES[0], wording.UKRAINE_CLASSES[3]]
    assert out.gaza.isna().tolist() == [True, False]
    assert out.gaza.iloc[1] == wording.GAZA_CLASSES[1]


def test_passage_marks_topic_sentences_and_gaps():
    text = "Ukraine suffers. We met. A. B. C. Russia attacked."
    lines = wording_check.passage(text, "ukraine").splitlines()
    assert lines[0] == "  ..." and lines[1].startswith("  >> Ukraine")
    assert "  ..." in lines[2:] and lines[-1].startswith("  >> Russia")


def test_score_reports_agreement_and_the_strong_calls():
    labels = pd.DataFrame({"sample": ["s", "s"], "war": ["gaza", "gaza"], "year": [2026, 2026], "iso3": ["A", "B"],
                           "label": [wording.GAZA_CLASSES[1], wording.GAZA_CLASSES[2]]})  # fmt: skip
    classified = pd.DataFrame({"year": [2026, 2026], "iso3": ["A", "B"], "gaza": [wording.GAZA_CLASSES[1], wording.GAZA_CLASSES[1]]})
    row = wording_check.score(labels, classified).iloc[0]
    assert row.agree == 1 and row["strong, rules right"] == "1 of 2" and row["strong, rules caught"] == "1 of 1"


WIKITEXT = """{| class="wikitable"
|-
| {{yes|Approve}}
| 2
| [[Albania]], [[Republic of Ireland|Ireland]]
|-
| {{no|Against}}
| 1
| [[Russia]]
|-
| {{maybe|Abstain}}
| 1
| [[India]]
|-
| {{tba|Absent}}
| 1
| [[National Unity Government of Myanmar|Myanmar]],{{efn|[[State Administration Council]] cannot vote}}
|-
! Total
|}"""


def test_votes_parse_maps_names_and_skips_footnote_links():
    assert votes.parse(WIKITEXT) == {"ALB": "yes", "IRL": "yes", "RUS": "no", "IND": "abstain", "MMR": "absent"}


def test_votes_parse_refuses_an_unknown_name():
    with pytest.raises(ValueError):
        votes.parse(WIKITEXT.replace("[[India]]", "[[Atlantis]]"))


FLAG_TABLE = """== Voting ==
{| class="wikitable"
!In favour (3)<br />''sponsors''!!Abstaining (1)!!Against (1)
!'''Absent (1)'''
|- style="vertical-align: top;"
|
{| <!-- Nested table -->
|- style="vertical-align: top;"
|{{flag|Albania}}<br /> {{flag|Guinea Bissau}}
|{{flagdeco|ROK}} [[South Korea|Republic of Korea]]
|}<!-- End of nested table -->
|{{flag|India}}
|{{flag|Israel}}
|{{flag|Hungary}}
|- style="text-align: center;"
| colspan="4" |Observer States: {{flag|Holy See}}
|}"""


def test_votes_parse_reads_the_flag_table_layout():
    # the in-favour column is split by a nested table, one state is a decorative flag and a link, and the observer row is not a vote
    assert votes.parse(FLAG_TABLE) == {"ALB": "yes", "GNB": "yes", "KOR": "yes", "IND": "abstain", "ISR": "no", "HUN": "absent"}
