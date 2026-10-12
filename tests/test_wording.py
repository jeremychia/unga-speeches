from unga_speeches.analysis.wording import GAZA_CLASSES, UKRAINE_CLASSES, gaza, ukraine

BLAMES, TALKS, RUSSIAS, MENTIONS, SILENT = UKRAINE_CLASSES
GENOCIDE, CONDUCT, HUMANITARIAN, NO_GAZA = GAZA_CLASSES


def test_russia_as_the_one_waging_war_is_blame():
    assert ukraine("In Ukraine, for almost five years now, Russia has been waging a cruel war on civilians.")[0] == BLAMES
    assert ukraine("Ukraine matters. We are raising the cost for Russia of continuing this senseless and illegal war.")[0] == BLAMES


def test_even_handed_wording_is_not_blame():
    assert ukraine("The war between Russia and Ukraine has dragged on for five years.")[0] == TALKS
    assert ukraine("We call for an end to the Russia-Ukraine war.")[0] == TALKS


def test_responsibility_and_war_by_russia_are_blame():
    assert ukraine("Ukraine suffers. But Russia alone bears responsibility for this war.")[0] == BLAMES
    assert ukraine("We face an illegal war of conquest brought, without provocation, by Russia against Ukraine.")[0] == BLAMES


def test_russia_winning_is_not_russia_blamed():
    assert ukraine("In Ukraine, everyone thought Russia would win this war in three days, but it didn't work out that way.")[0] == TALKS
    assert ukraine("Ukraine fights on. Russia's brutal war against Ukraine is a reminder.")[0] == BLAMES


def test_a_war_reaching_russia_is_not_russia_acting():
    assert ukraine("We have had this devastating war in Ukraine, a war that now has backfired into Russia.")[0] == TALKS


def test_praise_for_russian_support_is_not_blame():
    assert (
        ukraine("Ukraine supports terrorists. Our forces, with the support of the Russian Federation, are on the front line.")[0]
        == MENTIONS
    )


def test_aggression_counts_without_naming_russia():
    assert ukraine("In Ukraine, the aggression has now lasted longer than World War I.")[0] == BLAMES


def test_russias_own_framing():
    assert ukraine("The West is pumping the Ukrainian regime full of weapons.")[0] == RUSSIAS


def test_a_list_of_places_is_a_mention():
    assert ukraine("Armed conflicts in Ukraine, Iran, Sudan and Palestine demand our attention.")[0] == MENTIONS
    assert ukraine("Peace is the goal.")[0] == SILENT


def test_ligatures_are_unfolded():
    assert ukraine("The conﬂict in Ukraine, now in its ﬁfth year, is concerning.")[0] == TALKS


def test_genocide_counts_only_when_it_is_not_history_or_a_denial():
    assert gaza("What has happened in Gaza is genocide in every sense of the word.")["class"] == GENOCIDE
    assert gaza("In Gaza we grieve. What genocidal regime gives a million polio vaccinations to the enemy?")["class"] == HUMANITARIAN
    assert gaza("We remember the Srebrenica genocide. Palestine needs peace.")["class"] == HUMANITARIAN


def test_israel_as_the_one_acting_is_criticism_but_israelis_as_victims_are_not():
    assert gaza("In Gaza, Israel has murdered savagely over 70,000 innocents.")["class"] == CONDUCT
    assert gaza("Gaza suffers. The targeting of civilians by Israeli occupation must end.")["class"] == CONDUCT
    assert (
        gaza("Our soldier was killed while clearing a booby trapped building in Gaza. Israel's oldest son was killed.")["class"]
        == HUMANITARIAN
    )


def test_a_peaceful_settlement_is_not_a_settlement():
    assert gaza("We call for a peaceful settlement to the conflict between Israel and Palestine.")["class"] == HUMANITARIAN
    assert gaza("Israel's settlements in the West Bank are illegal under international law.")["class"] == CONDUCT


def test_hamas_and_the_hostages_are_flagged_separately():
    result = gaza("The terrorist attack on Israel on 7th October 2023 was horrific. Gaza needs aid.")
    assert result["hamas"] and result["class"] == HUMANITARIAN
    assert gaza("Peace is the goal.")["class"] == NO_GAZA


def test_a_general_responsibility_is_not_blame():
    assert ukraine("On Ukraine, Russia has a special responsibility as a permanent member of the Council.")[0] == MENTIONS
