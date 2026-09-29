import csv
from collections import Counter

from unga_speeches.config import REFERENCE_DIR

STATUSES = {
    "in_sample",
    "no_coverage_found",
    "search_blocked",
    "download_refused",
    "download_failed",
    "no_text",
    "outside_window",
    "not_english",
    "video_only",
    "excluded",
}
REGIONS = {"Africa", "Americas", "Asia", "Europe", "Oceania", "UN", "Reference"}


def _read(name: str) -> list[dict]:
    with (REFERENCE_DIR / name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_every_outlet_in_the_sample_is_registered_with_its_report_count():
    registry = {r["outlet"]: r for r in _read("outlets.csv")}
    sampled = Counter(r["outlet"] for r in _read("news_81.csv"))
    for outlet, n in sampled.items():
        assert registry[outlet]["status"] == "in_sample", outlet
        assert int(registry[outlet]["reports"]) == n, outlet
    assert {o for o, r in registry.items() if r["status"] == "in_sample"} == set(sampled)


def test_registry_uses_known_statuses_and_regions_once_per_outlet():
    rows = _read("outlets.csv")
    assert len({r["outlet"] for r in rows}) == len(rows)
    assert {r["status"] for r in rows} <= STATUSES
    assert {r["region"] for r in rows} <= REGIONS


def test_sample_regions_match_the_registry():
    registry = {r["outlet"]: r["region"] for r in _read("outlets.csv")}
    for r in _read("news_81.csv"):
        assert r["base_region"] == registry[r["outlet"]], r["url"]


def test_every_big_brand_named_in_the_registry_is_in_the_report_list():
    brands = {(r["country"], r["brand"]) for r in _read("dnr_brands_2026.csv")}
    for r in _read("outlets.csv"):
        if r["dnr_brand"]:
            assert (r["country"], r["dnr_brand"]) in brands, r["outlet"]
