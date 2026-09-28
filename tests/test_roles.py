import pytest

from unga.roles import classify


@pytest.mark.parametrize(
    "title, expected",
    [
        ("President", "head_of_state"),
        ("Constitutional President", "head_of_state"),
        ("Amir", "head_of_state"),
        ("Grand Duke", "head_of_state"),
        ("Chairman of the Presidency", "head_of_state"),
        ("Prime Minister", "head_of_government"),
        ("Taoiseach", "head_of_government"),
        ("President of the Government", "head_of_government"),
        ("President of the Council of Ministers", "head_of_government"),
        ("Prime Minister and Minister for Foreign Affairs", "head_of_government"),
        ("Vice President", "deputy_head"),
        ("Crown Prince", "deputy_head"),
        ("Deputy Prime Minister and Minister for Foreign Affairs", "deputy_head"),
        ("Minister for Foreign Affairs", "foreign_minister"),
        ("Minister for External Affairs", "foreign_minister"),
        ("Minister for International Relations and Cooperation", "foreign_minister"),
        ("Minister of State and for Foreign Affairs, Cooperation and Communities", "foreign_minister"),
        ("Vice Minister for Foreign Affairs", "junior_minister"),
        ("Minister of State", "junior_minister"),
        ("Minister of Public Health and Prevention", "other_minister"),
        ("Permanent Representative to the United Nations", "diplomat"),
        ("President of the European Council", "regional_organisation"),
        ("Head of Administration of the President", "other_official"),
        ("Secretary-General", "un_official"),
        ("President of the General Assembly", "un_official"),
        (None, "unclassified"),
    ],
)
def test_classify(title, expected):
    assert classify(title) == expected


def test_holy_see_secretary_of_state_heads_government():
    assert classify("Secretary of State", "holy-see") == "head_of_government"
    assert classify("Secretary of State") == "unclassified"
