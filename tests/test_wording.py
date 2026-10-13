from unga_speeches.analysis.wording import GAZA_CLASSES, UKRAINE_CLASSES, gaza, ukraine

BLAMES, NO_BLAME, RUSSIAS, SILENT = UKRAINE_CLASSES
GENOCIDE, CONDUCT, BOTH, ISRAELS_SIDE, NEITHER, NO_GAZA = GAZA_CLASSES
CRITICAL = (CONDUCT, BOTH)  # criticises Israel, whether or not it also blames Hamas
NOT_CRITICAL = (ISRAELS_SIDE, NEITHER)


def test_russia_as_the_one_waging_war_is_blame():
    assert ukraine("In Ukraine, for almost five years now, Russia has been waging a cruel war on civilians.")[0] == BLAMES
    assert ukraine("Ukraine matters. We are raising the cost for Russia of continuing this senseless and illegal war.")[0] == BLAMES


def test_even_handed_wording_is_not_blame():
    assert ukraine("The war between Russia and Ukraine has dragged on for five years.")[0] == NO_BLAME
    assert ukraine("We call for an end to the Russia-Ukraine war.")[0] == NO_BLAME


def test_responsibility_and_war_by_russia_are_blame():
    assert ukraine("Ukraine suffers. But Russia alone bears responsibility for this war.")[0] == BLAMES
    assert ukraine("We face an illegal war of conquest brought, without provocation, by Russia against Ukraine.")[0] == BLAMES


def test_russia_winning_is_not_russia_blamed():
    assert ukraine("In Ukraine, everyone thought Russia would win this war in three days, but it didn't work out that way.")[0] == NO_BLAME
    assert ukraine("Ukraine fights on. Russia's brutal war against Ukraine is a reminder.")[0] == BLAMES


def test_a_war_reaching_russia_is_not_russia_acting():
    assert ukraine("We have had this devastating war in Ukraine, a war that now has backfired into Russia.")[0] == NO_BLAME


def test_praise_for_russian_support_is_not_blame():
    assert (
        ukraine("Ukraine supports terrorists. Our forces, with the support of the Russian Federation, are on the front line.")[0]
        == NO_BLAME
    )


def test_aggression_counts_without_naming_russia():
    assert ukraine("In Ukraine, the aggression has now lasted longer than World War I.")[0] == BLAMES


def test_russias_own_framing():
    assert ukraine("The West is pumping the Ukrainian regime full of weapons.")[0] == RUSSIAS


def test_a_list_of_places_is_a_mention():
    assert ukraine("Armed conflicts in Ukraine, Iran, Sudan and Palestine demand our attention.")[0] == NO_BLAME
    assert ukraine("Peace is the goal.")[0] == SILENT


def test_ligatures_are_unfolded():
    assert ukraine("The conﬂict in Ukraine, now in its ﬁfth year, is concerning.")[0] == NO_BLAME


def test_genocide_counts_only_when_it_is_not_history_or_a_denial():
    assert gaza("What has happened in Gaza is genocide in every sense of the word.")["class"] == GENOCIDE
    assert gaza("In Gaza we grieve. What genocidal regime gives a million polio vaccinations to the enemy?")["class"] in NOT_CRITICAL
    assert gaza("We remember the Srebrenica genocide. Palestine needs peace.")["class"] in NOT_CRITICAL


def test_israel_as_the_one_acting_is_criticism_but_israelis_as_victims_are_not():
    assert gaza("In Gaza, Israel has murdered savagely over 70,000 innocents.")["class"] in CRITICAL
    assert gaza("Gaza suffers. The targeting of civilians by Israeli occupation must end.")["class"] in CRITICAL
    assert (
        gaza("Our soldier was killed while clearing a booby trapped building in Gaza. Israel's oldest son was killed.")["class"]
        in NOT_CRITICAL
    )


def test_a_peaceful_settlement_is_not_a_settlement():
    assert gaza("We call for a peaceful settlement to the conflict between Israel and Palestine.")["class"] in NOT_CRITICAL
    assert gaza("Israel's settlements in the West Bank are illegal under international law.")["class"] in CRITICAL


def test_hamas_and_the_hostages_are_flagged_separately():
    result = gaza("The terrorist attack on Israel on 7th October 2023 was horrific. Gaza needs aid.")
    assert result["hamas"] and result["class"] in NOT_CRITICAL
    assert gaza("Peace is the goal.")["class"] == NO_GAZA


def test_a_general_responsibility_is_not_blame():
    assert ukraine("On Ukraine, Russia has a special responsibility as a permanent member of the Council.")[0] == NO_BLAME


# cases from the independent review


def test_russia_counts_only_near_ukraine():
    text = "We stand with Ukraine, Sudan and Haiti. Peace matters to us. Twenty per cent of our territory remains under Russian occupation."
    assert ukraine(text)[0] != BLAMES


def test_russians_as_victims_are_not_blame():
    assert (
        ukraine("Ukraine and Gaza need peace. Dozens of Russians died in the terrorist attack on the Crocus concert hall.")[0] == NO_BLAME
    )


def test_aggression_by_someone_else_is_not_blame_of_russia():
    assert ukraine("Regarding the case of the Ukrainian aggression against our country, we are vigilant.")[0] != BLAMES
    assert ukraine("The conflict in Ukraine is the result of NATO aggression against Russia.")[0] != BLAMES
    assert ukraine("We condemn the aggression against Mali and the Ukrainian authorities' support for terrorism.")[0] != BLAMES


def test_russias_framing_quoted_to_reject_it_is_not_framing():
    assert ukraine("Russia's lies about a so-called special military operation in Ukraine fool no one.")[0] != RUSSIAS
    assert ukraine("Finland's accession marked NATO's enlargement. We stand with Ukraine.")[0] != RUSSIAS
    assert ukraine("They will fight down to the last Ukrainian.")[0] == RUSSIAS


def test_peace_is_a_call_for_talks_and_one_region_is_one_place():
    assert ukraine("We support a just and lasting peace in Ukraine.")[0] == NO_BLAME
    assert ukraine("We call for negotiations to end the war in Ukraine and a ceasefire in Gaza and Palestine.")[0] == NO_BLAME
    assert ukraine("Armed conflicts, including those in Ukraine and the Middle East, threaten humanity.")[0] == NO_BLAME


def test_kyiv_names_ukraine():
    assert ukraine("I was in Kyiv last month, and it gave me a glimpse of life under Russian attack.")[0] == BLAMES


def test_more_criticism_of_israel_is_recognised():
    assert gaza("In Gaza, Israeli strikes continue and aid is blocked.")["class"] in CRITICAL
    assert gaza("The Israeli occupation of Palestinian territory is unlawful.")["class"] in CRITICAL
    assert gaza("Israel must stop starving Gaza and Hamas must release the hostages.")["class"] in CRITICAL
    assert gaza("Gaza has suffered from Israel's state terrorism and its bombardment.")["class"] in CRITICAL
    assert gaza("We oppose the illegal settlements in the West Bank.")["class"] in CRITICAL
    assert gaza("This does not justify the Israeli government's actions in Gaza.")["class"] in CRITICAL


def test_israel_suffering_or_sharing_the_blame_is_not_criticism():
    assert gaza("In Gaza we grieve. Israeli families have been brutally murdered.")["class"] in NOT_CRITICAL
    assert gaza("Gaza needs calm. Israel's sovereignty, violated by Iranian missiles, must be respected.")["class"] in NOT_CRITICAL
    assert gaza("Israel and Palestine must both commit to peace in Gaza, and all parties must end violations.")["class"] in NOT_CRITICAL


def test_other_genocides_and_the_case_title_are_not_gaza_genocide():
    assert gaza("In El Fasher, genocide is under way. In Gaza, aid must flow.")["class"] != GENOCIDE
    case = "The Court ruled in Application of the Convention on the Prevention and Punishment of the Crime of Genocide in the Gaza Strip."
    assert gaza(case)["class"] != GENOCIDE
    assert gaza("In Gaza, Israel is committing genocide, and we accuse it before the world.")["class"] == GENOCIDE
    comparison = "The world did not respond to the genocide against Palestinians in Gaza, just as it did not at Srebrenica."
    assert gaza(comparison)["class"] == GENOCIDE


def test_gazans_and_bullets():
    assert gaza("The Gazans are dying under Israeli bombardment.")["class"] in CRITICAL
    assert ukraine("• We meet in hard times. • Russia's war of aggression against Ukraine is a dire threat.")[0] == BLAMES


# cases from the audit of every 2026 speech


def test_the_war_against_ukraine_names_no_aggressor():
    assert ukraine("The main challenge remains the war against Ukraine.")[0] == NO_BLAME


def test_the_kremlins_formulas_and_nato_as_the_seed_of_the_war():
    belarus = "We want peace in Ukraine. But any lasting peace is not possible without addressing the root causes, which have been ignored for years."
    assert ukraine(belarus)[0] == RUSSIAS
    assert ukraine("Peace in Ukraine needs talks that address the symptoms and root causes of hotspot issues.")[0] == NO_BLAME
    timor = "The seeds of future wars were sown as NATO began its fast eastbound expansion. As expected, we have had this war in Ukraine."
    assert ukraine(timor)[0] == RUSSIAS


def test_criticism_that_names_no_actor():
    for sentence in [
        "There are clear violations of international law in Gaza and the West Bank.",
        "Palestine has suffered decades of occupation and repression.",
        "We call for an end to the violence in the West Bank, particularly home demolitions.",
        "Nowhere is this more painful than in the ongoing persecution of the Palestinian people in Gaza.",
        "We welcome sanctions on Israeli settlers implicated in violent acts in the West Bank.",
    ]:
        assert gaza(sentence)["class"] in CRITICAL, sentence


def test_a_genocide_sentence_beside_a_list_of_wars_is_not_gaza_genocide():
    angola = "We see no peace in sight between Russia and Ukraine, in the Israeli-Palestinian conflict and in the Gulf. We condemn the genocide against defenceless populations."
    assert gaza(angola)["class"] != GENOCIDE
    belize = "In Palestine, a settler state continues its campaign. The genocide must end."
    assert gaza(belize)["class"] == GENOCIDE


def test_israel_attacked_or_accused_is_not_israel_acting():
    hamas = "Thousands of Hamas terrorists from Gaza burst into Israel, and they committed unimaginable atrocities."
    assert gaza(hamas)["class"] in NOT_CRITICAL
    denial = "Israel is accused of deliberately starving the people of Gaza when Israel is deliberately feeding the people of Gaza."
    assert gaza(denial)["class"] in NOT_CRITICAL
    assert gaza("Israel must stop starving Gaza and Hamas must release the hostages.")["class"] in CRITICAL


def test_hamass_attack_named_after_the_act_is_not_israel_acting():
    sentence = "In Gaza he wants peace with Israel, yet he still refuses to condemn the horrific massacre of 7 October."
    assert gaza(sentence)["class"] in NOT_CRITICAL


def test_blaming_hamas_or_defending_israel_is_its_own_class():
    assert gaza("In Gaza, Hamas must release the hostages and disarm.")["class"] == ISRAELS_SIDE
    assert gaza("Israel has the right to defend itself against Hamas. Gaza must be rebuilt.")["class"] == ISRAELS_SIDE
    assert gaza("We condemn the horrific attack of 7 October. In Gaza, Israeli strikes continue.")["class"] == BOTH


def test_naming_the_hostages_or_disputing_the_right_is_not_taking_a_side():
    assert gaza("We call for a ceasefire in Gaza and the release of all hostages.")["class"] == NEITHER
    assert gaza("Israel has the right to defend itself, but not as a pretext to bomb Gaza.")["class"] == NEITHER


def test_more_ways_of_blaming_hamas():
    for sentence in [
        "Palestinians in Gaza need peace, with Hamas disarmed.",
        "In Gaza, we must ensure that Hamas surrenders its arms.",
        "We call on Hamas and other armed groups in Gaza to disarm.",
        "Nothing can ever justify the acts of terror of the 7th of October, but Gaza needs aid.",
    ]:
        assert gaza(sentence)["israels_side"], sentence
