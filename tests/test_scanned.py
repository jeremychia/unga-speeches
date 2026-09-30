from unga_speeches.enrich import countries
from unga_speeches.sources import scanned

FILLER = " ".join(["The Assembly must act together for peace and development in every region of the world."] * 20)


def test_labels_survive_ocr_bullets_and_heads_of_state_named_by_office():
    text = (
        "AGENDA ITEM 9\nGENERAL DEBATE\n"
        f"Mr• BRAHIMI (Algeria) (interpretation from Arabic): {FILLER}\n"
        f"President ENDARA GALIMANY (Panama) (interpretation from Spanish): {FILLER}\n"
        "The PRESIDENT: I thank the speaker.\n"
    )
    speeches = scanned.parse_text(text, 47, "A/47/PV.14")
    assert [(s.iso3, s.spoken_language) for s in speeches] == [("DZA", "ar"), ("PAN", "es")]


def test_turns_under_another_agenda_item_are_left_out_but_addresses_count():
    text = (
        "AGENDA ITEM 8\nADOPTION OF THE AGENDA\n"
        f"Mr. PANIC (Yugoslavia): {FILLER}\n"
        "ADDRESS BY MR. MILAN KUCAN, PRESIDENT OF THE REPUBLIC OF SLOVENIA\n"
        f"President KUCAN (spoke in Slovenian; English text furnished by the delegation): {FILLER}\n"
    )
    speeches = scanned.parse_text(text, 47, "A/47/PV.11")
    assert [s.iso3 for s in speeches] == ["SVN"]
    assert speeches[0].heading_title == "President"


def test_former_states_resolve_to_the_corpus_codes():
    assert countries.resolve("Czechoslovakia") == "CSK"
    assert countries.resolve("Union of Soviet Socialist Republics") == "RUS"
    assert countries.resolve("Byelorussian Soviet Socialist Republic") == "BLR"
    assert scanned._country("Czechoslovakla") == "CSK"  # an ocr slip is still close enough


def test_meeting_numbers_run_across_sessions_until_1976():
    assert scanned.symbol(25, 1843) == "A/PV.1843"
    assert scanned.symbol(31, 7) == "A/31/PV.7"


def test_the_meeting_date_is_the_one_that_names_its_weekday():
    front = "resolution adopted on 13 February 1946 ... Held on Thursday, 24 October 1946, at 11 a.m."
    m = scanned.DATE.search(front)
    assert (m.group(1), m.group(2), m.group(3)) == ("24", "October", "1946")


def test_a_special_session_is_recognised_by_its_heading_not_a_mention():
    assert scanned.SPECIAL.search("THIRD SPECIAL SESSION  New York")
    assert not scanned.SPECIAL.search("as the special session on disarmament decided")
