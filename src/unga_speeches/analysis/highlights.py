"""Speeches worth reading in full: an editorial choice, each with a quote the build checks against the source text."""

from dataclasses import dataclass


@dataclass
class Highlight:
    slug: str
    headline: str
    note: str  # why it is worth reading; figures are added by the page from the data
    quote: str  # verbatim from the speech's English text


HIGHLIGHTS_81 = [
    Highlight(
        "palestine-state",
        "Palestine spoke by video, for the second year running",
        "The State of Palestine is an observer, not a member. Its president addressed the debate by pre-recorded video, "
        "after the delegation was refused the visas it needed to reach New York.",
        "For the second consecutive year, the Palestinian delegation was denied the entry visas required to reach New York "
        "and participate in the meetings of the United Nations General Assembly in person.",
    ),
    Highlight(
        "united-states-america",
        "The longest speech, and a claim to be reforming the UN",
        "The United States used more words than any other delegation. It presented itself as the UN's reformer, "
        "citing what it called the most sweeping reforms in the organisation's history.",
        "Two and a half centuries after the cause of liberty found its home on this continent, I can report to you with pride "
        "that America is back And our country is stronger today than ever before.",
    ),
    Highlight(
        "ukraine",
        "Ukraine quoted Washington back to the room",
        "President Zelensky built a passage around a post by the US President calling the war “ridiculous and never-ending”, "
        "and closed it with a pointed exception.",
        "I do not know anyone who is openly for this war… Except one man.",
    ),
    Highlight(
        "iran-islamic-republic",
        "Iran's account of the Gulf war",
        "Mentions of Iran and the Gulf war doubled this year. Iran's president told it as a war of aggression against his country.",
        "America and Israel attacked us, equipped with the latest technology and weapons systems, and our people stood steadfast.",
    ),
    Highlight(
        "secretary-general-united-nations",
        "The Secretary-General said what few members would",
        "In his last general debate before his term ends in December 2026, António Guterres treated a multipolar world as a fact "
        "and argued over the shape it should take. Few member states used the word at all.",
        "We are clearly moving towards a multipolar world.",
    ),
    Highlight(
        "tuvalu",
        "A small island that calls itself a large ocean state",
        "Tuvalu's statement is the clearest case of the Pacific's agenda: land lost to the sea, reclaimed metre by metre, "
        "and a claim to matter by the ocean it holds.",
        "Tuvalu may have only 26 square kilometres of land, but we are custodians of some 750,000 square kilometres of ocean, "
        "which makes Tuvalu a large ocean state.",
    ),
    Highlight(
        "burkina-faso",
        "The Sahel states spoke as a confederation",
        "Burkina Faso's foreign minister spoke for the Confederation of Sahel States it forms with Mali and Niger. "
        "The two speeches closest to it in vocabulary are Mali's and Niger's, its partners in the confederation.",
        "This blind and sustained violence has been sustained, armed, financed and instrumentalized by criminal networks "
        "and their supporters intent on subjugating the Sahel through fear.",
    ),
    Highlight(
        "china",
        "China sent its Vice President, and a pitch to the Global South",
        "China was represented by its Vice President, a step down from its Premier last year. The speech cast China as the advocate of developing countries.",
        "China has always spoken up for the global South, stood up for the legitimate rights and interests of developing countries, "
        "and continued to work toward a more just and equitable global governance system.",
    ),
]

HIGHLIGHTS = {81: HIGHLIGHTS_81}
