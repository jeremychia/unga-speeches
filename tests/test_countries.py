import pytest

from unga_speeches.enrich.countries import find, resolve


@pytest.mark.parametrize(
    "text, expected",
    [
        ("President of the United Mexican States", "MEX"),
        ("President of the Plurinational State of Bolivia", "BOL"),
        ("President of the Republic of Guinea-Bissau", "GNB"),
        ("President of the Republic of Guinea", "GIN"),
        ("Prime Minister of Papua New Guinea", "PNG"),
        ("President of the Republic of Côte d’Ivoire", "CIV"),
        ("President of the Republic of Malawi and Commander-in-Chief of the Malawi Defence Force", "MWI"),
        ("His Serene Highness Prince Albert II of Monaco", "MCO"),
        ("President of the European Council", "EU"),
    ],
)
def test_find_country_in_a_title(text, expected):
    assert find(text) == expected


@pytest.mark.parametrize(
    "label, expected",
    [("Russian Federation", "RUS"), ("Democratic Republic of the Congo", "COD"), ("Congo", "COG"), ("Niger", "NER"), ("Dominica", "DMA")],
)
def test_resolve_label_country(label, expected):
    assert resolve(label) == expected
