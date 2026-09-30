from unga_speeches import history
from unga_speeches.sources import news


def _article(text_sha, page_sha, words=500):
    return {"url": "https://paper.com/a", "outlet": "Paper", "title": "Leaders speak", "published": "2026-09-22", "words": words,
            "paragraph_count": 10, "text_sha256": text_sha, "page_sha256": page_sha, "retrieved_at": "t"}  # fmt: skip


def test_an_edited_article_opens_a_version_and_a_new_advert_does_not(tmp_path):
    path = tmp_path / "news_history.json"
    track = dict(key="url", tracked=news.HISTORY_TRACKED, overwrite=["page_sha256", "retrieved_at"])
    history.record(path, [_article("text-a", "page-1")], observed="2026-09-22", **track)
    history.record(path, [_article("text-a", "page-2")], observed="2026-09-23", **track)  # same text, new page bytes
    versions = history.record(path, [_article("text-b", "page-3", words=620)], observed="2026-09-25", **track)
    assert [(v["text_sha256"], v["valid_from"], v["valid_to"], v["is_current"]) for v in versions] == [
        ("text-a", "2026-09-22", "2026-09-25", False),
        ("text-b", "2026-09-25", None, True),
    ]
    assert versions[0]["page_sha256"] == "page-2" and versions[0]["last_checked"] == "2026-09-23"


def test_an_unobserved_article_keeps_its_open_version(tmp_path):
    path = tmp_path / "news_history.json"
    track = dict(key="url", tracked=news.HISTORY_TRACKED, overwrite=["page_sha256", "retrieved_at"])
    history.record(path, [_article("text-a", "page-1")], observed="2026-09-22", **track)
    versions = history.record(path, [], observed="2026-09-30", **track)
    assert versions[0]["is_current"] and versions[0]["last_checked"] == "2026-09-22"
