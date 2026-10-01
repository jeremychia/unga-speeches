import pandas as pd

from unga_speeches.analysis import network, years


def _rows(regions):
    return [{"slug": s, "region": r, "status": "member_state", "lean": ""} for s, r in regions.items()]


def test_states_that_only_name_their_own_region_score_above_chance():
    regions = {f"a{i}": "Africa" for i in range(6)} | {f"e{i}": "Europe" for i in range(6)}
    edges = [{"from": f"{p}{i}", "to": f"{p}{(i + 1) % 6}", "times": 1} for p in "ae" for i in range(6)]
    edges.append({"from": "a0", "to": "e0", "times": 1})  # one pair across regions, so chance is not zero
    h = network.homophily(network._graph(_rows(regions), edges), regions)
    assert h["observed"] == round(12 / 13, 3)
    assert h["ratio"] > 1.5 and h["p"] < 0.01


def test_taiwan_splits_allies_into_namers_and_silent_and_lists_any_other_namer():
    rows = _rows({"palau": "Oceania", "haiti": "Americas", "france": "Europe"})
    edges = [{"from": "palau", "to": "TWN", "times": 2}, {"from": "france", "to": "TWN", "times": 1}]
    tw = network.taiwan(rows, edges, blocs=[])
    assert tw["allies_naming"] == ["palau"]
    assert tw["allies_silent"] == ["haiti"]
    assert tw["non_allies_naming"] == ["france"]
    assert "guatemala" in tw["allies"] and "guatemala" not in tw["allies_speaking"]


def test_a_far_outlier_is_pinned_to_the_edge_instead_of_squeezing_the_rest():
    spread = network._spread([i / 100 for i in range(100)] + [50.0])
    assert spread[-1] == 1.0
    assert spread[50] > 0.4  # without the clip, the middle state would sit near 0.01


def test_years_count_taiwan_namers_and_leave_the_leaders_share_blank_when_ranks_are_unknown(tmp_path, monkeypatch):
    text = "We support the people of Taiwan. Climate change threatens us all."
    pd.DataFrame(
        {
            "session": [26, 26, 26],
            "year": [1971, 1971, 1971],
            "iso3": ["PRY", "FRA", "KEN"],
            "role_group": ["unclassified", "unclassified", "head_of_state_or_government"],
            "english_text_clean": [text, "Climate change threatens us all.", "Peace and development."],
        }
    ).to_parquet(tmp_path / "speeches.parquet")
    monkeypatch.setattr(years, "OUTPUT_DIR", tmp_path)
    (year,) = years.build()
    assert year["taiwan"] == ["PRY"]
    assert year["heads_share"] is None  # 2 of 3 ranks unknown
    assert year["issues"]["Climate change"] == round(2 / 3, 3)
    assert year["frames"].keys() == {"Americas", "Europe", "Africa"}
