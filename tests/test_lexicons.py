from unga_speeches.analysis.lexicons import densest_sentence, frame_rates, issues, markers


def test_ai_counts_only_in_capitals_or_in_full():
    assert issues("Artificial Intelligence will change work.")["Artificial intelligence"]
    assert issues("AI governance needs rules.")["Artificial intelligence"]
    assert not issues("The minister Ai Wen spoke.")["Artificial intelligence"]


def test_sudan_excludes_south_sudan():
    assert not issues("Peace in South Sudan.")["Sudan"]
    assert issues("The war in Sudan.")["Sudan"]


def test_frame_rates_are_per_thousand_words():
    rates = frame_rates("security " * 10 + "word " * 990)
    assert rates["Realism"] == 10.0


def test_trust_is_not_constructivist_vocabulary():
    assert frame_rates("trust trust trust")["Constructivism"] == 0


def test_markers():
    assert markers("A multipolar world with double standards.") == ["Multipolar", "Double standards"]


def test_densest_sentence_skips_salutations_and_rejoins_line_break_hyphens():
    text = "Madam President, Excellencies, our security and defence matter. We must strength‐ en our military and security posture against every threat now."
    assert densest_sentence(text, "Realism") == "We must strengthen our military and security posture against every threat now."


def test_gaza_and_palestinian_statehood_are_separate_issues():
    found = issues("We call for a ceasefire in Gaza.")
    assert found["Gaza"] and not found["Palestinian statehood"]
    found = issues("We support the two-state solution and recognise the State of Palestine.")
    assert found["Palestinian statehood"] and not found["Gaza"]


def test_gaza_or_palestine_covers_any_mention():
    assert issues("The Palestinian people deserve peace.")["Gaza or Palestine"]
    assert not issues("The Palestinian people deserve peace.")["Gaza"]
