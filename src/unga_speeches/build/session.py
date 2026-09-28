"""Build the speech dataset for one general debate session from gadebate.un.org."""

import csv
import json
import logging
from dataclasses import asdict

from unga_speeches.build.render import language_name, render
from unga_speeches.build.report import write_completeness_report
from unga_speeches.config import OUTPUT_DIR, REFERENCE_DIR, SPEECHES_DIR, UN_LANGUAGES, session_year
from unga_speeches.enrich import delivery, roles
from unga_speeches.extract import pdf
from unga_speeches.http import Client
from unga_speeches.model import Speech, TextVersion
from unga_speeches.sources import gadebate, national

log = logging.getLogger(__name__)

TESSERACT_LANGUAGE = {
    "ar": "ara",
    "bn": "ben",
    "de": "deu",
    "en": "eng",
    "es": "spa",
    "fr": "fra",
    "pt": "por",
    "ru": "rus",
    "uk": "ukr",
    "zh": "chi_sim",
}


def load_delegations() -> list[dict]:
    with (REFERENCE_DIR / "delegations.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _statement_version(client: Client, page: gadebate.SpeakerPage, statement: gadebate.Statement) -> TextVersion | None:
    fetched = gadebate.fetch_statement(client, page, statement)
    if not fetched:
        return None
    extracted = pdf.extract(fetched.path, TESSERACT_LANGUAGE.get(statement.language or "", "eng"))
    language = statement.language
    warnings = list(extracted.warnings)
    if extracted.detected_language and extracted.language_confidence and extracted.language_confidence >= 0.9:
        if language and extracted.detected_language != language:
            warnings.append(
                f"the site files this as {language_name(language)} but the text reads as {language_name(extracted.detected_language)}"
            )
        language = extracted.detected_language
    elif extracted.text:
        warnings.append("the text mixes languages or its language could not be detected reliably")
    if statement.floor_version:
        warnings.append("the delegation marked this as the floor version, the text as delivered")
    return TextVersion(
        kind="statement",
        floor_version=statement.floor_version,
        language=language,
        source_url=fetched.url,
        retrieved_at=fetched.retrieved_at,
        sha256=fetched.sha256,
        method=extracted.method,
        text=extracted.text,
        warnings=warnings,
    )


def _transcript_version(client: Client, page: gadebate.SpeakerPage, language: str) -> TextVersion | None:
    fetched = gadebate.fetch_transcript(client, page, language)
    if not fetched:
        return None
    return TextVersion(
        kind="transcript",
        language=language,
        source_url=fetched.url,
        retrieved_at=fetched.retrieved_at,
        sha256=fetched.sha256,
        method="ai_transcript",
        text=fetched.path.read_text(encoding="utf-8").strip(),
        warnings=["machine transcription of the meeting audio; it may mis-hear words and is not an official record"],
    )


def build_speech(client: Client, page: gadebate.SpeakerPage, delegation: dict, page_retrieved_at: str | None) -> Speech:
    official = [code for code in (delegation.get("official_languages") or "").split("|") if code]
    speech = Speech(
        session=page.session,
        year=session_year(page.session),
        slug=page.slug,
        delegation=delegation.get("name") or page.delegation,
        iso3=delegation.get("iso3") or None,
        status=delegation.get("status") or "unknown",
        page_url=page.url,
        page_retrieved_at=page_retrieved_at,
        honorific=page.honorific,
        speaker_name=page.speaker_name,
        speaker_title=page.speaker_title,
        role=roles.classify(page.speaker_title, page.slug),
        role_group="",
        date=page.date,
        daily_summary_url=page.daily_summary_url,
    )
    speech.role_group = roles.ROLE_GROUP[speech.role]

    statements = [v for s in page.statements if (v := _statement_version(client, page, s))]
    statements += [v for source in national.load(page.session, page.slug) if (v := national.fetch(client, page.session, page.slug, source))]
    # a statement's language marks the original even when its text layer is unusable
    languages = [v.language for v in statements if v.language]
    non_english = sorted({code for code in languages if code != "en"})
    floor = [v.language for v in statements if v.floor_version and v.language]

    if floor:
        speech.original_language = floor[0]
    elif len(non_english) > 1:
        speech.gaps.append(
            f"texts were filed in {len(set(languages))} languages and none is marked as delivered, so the spoken language is not known"
        )
    elif non_english:
        speech.original_language = non_english[0]
    elif "en" in languages and official and "en" not in official:
        # interpreters read from the english text a delegation supplies, so neither the pdf nor the audio shows what was spoken
        speech.gaps.append(
            f"only an English text was filed, and English is not an official language of {speech.delegation}, so the spoken language is not known; "
            "if it was not English, add the original from the delegation's own website to manual_sources.csv"
        )
    elif "en" in languages:
        speech.original_language = "en"
    elif official:
        speech.original_language = "en" if "en" in official else official[0]
        speech.gaps.append(
            f"no statement was filed, so the spoken language is assumed to be {language_name(speech.original_language)}, an official language of {speech.delegation}"
        )
    for v in statements:
        if not v.text and not any(w.text and w.language == v.language for w in statements):
            speech.gaps.append(f"the statement pdf <{v.source_url}> has no usable text layer; read the pdf itself")

    wanted = ["en"]
    if speech.original_language in UN_LANGUAGES and speech.original_language != "en":
        wanted.append(speech.original_language)
    transcripts = [v for lang in wanted if page.has_transcript and (v := _transcript_version(client, page, lang))]

    for v in statements + transcripts:
        v.role = "original" if v.language == speech.original_language else "english" if v.language == "en" else "other"
    kind_order = {"statement": 0, "national_source": 1, "transcript": 2}
    speech.texts = sorted(statements + transcripts, key=lambda v: (v.role != "original", kind_order[v.kind]))
    for i, v in enumerate(speech.texts):
        v.index = i

    filed = sorted(
        (v for v in speech.texts if v.role == "original" and v.kind != "transcript" and v.text), key=lambda v: not v.floor_version
    )
    said = [v for v in speech.texts if v.role == "original" and v.kind == "transcript" and v.text]
    if filed and said:
        speech.delivered_share, speech.unscripted_share = delivery.compare(filed[0].text, said[0].text, speech.original_language)

    def has(role: str, *kinds: str) -> bool:
        return any(v.role == role and v.kind in kinds and v.text for v in speech.texts)

    if speech.original_language == "en":
        speech.english_source = "original" if has("original", "statement", "national_source", "transcript") else "none"
    elif has("english", "statement", "national_source"):
        speech.english_source = "delegation_translation" if speech.original_language else "delegation_english_text"
    elif has("english", "transcript"):
        speech.english_source = "un_interpretation_transcript"
    else:
        speech.english_source = "none"
        speech.gaps.append("no English text is available")
    if not has("original", "statement", "national_source"):
        if has("original", "transcript"):
            speech.gaps.append("no usable statement pdf; the original-language text is the AI transcript only")
        elif speech.original_language and speech.original_language not in UN_LANGUAGES:
            speech.gaps.append(
                f"the UN transcribes only its six official languages, so no {language_name(speech.original_language)} text is held; "
                "check the delegation's own website"
            )
    return speech


def run_session(session: int, refresh: bool = False, only: set[str] | None = None, refresh_pages: bool = False) -> list[Speech]:
    client = Client(refresh=refresh)
    delegations = load_delegations()
    by_slug = {d["slug"]: d for d in delegations if d["slug"]}
    listed = gadebate.discover(client, {session}, force=refresh_pages)
    speeches, pending, failed = [], [], []
    for _, slug, _lastmod in listed:
        if only and slug not in only:
            continue
        path = gadebate.fetch_page(client, session, slug, force=refresh_pages)
        if path is None:
            pending.append(slug)
            log.info("%s: listed but not yet published", slug)
            continue
        page = gadebate.parse_page(path.read_text(encoding="utf-8"), session, slug)
        meta = json.loads(path.with_suffix(path.suffix + ".meta.json").read_text())
        try:
            speech = build_speech(client, page, by_slug.get(slug, {}), meta["retrieved_at"])
        except Exception:
            log.exception("%s: failed, rerun the session to retry", slug)
            failed.append(slug)
            continue
        render(speech, SPEECHES_DIR / str(session) / slug)
        speeches.append(speech)
        log.info(
            "%s: %s (%s), original %s, english %s", slug, speech.speaker_name, speech.role, speech.original_language, speech.english_source
        )
    if not only:
        write_outputs(session, speeches, pending, delegations)
    if failed:
        log.warning("%d speeches failed: %s", len(failed), ", ".join(failed))
    return speeches


SPEECH_COLUMNS = [
    "session",
    "year",
    "slug",
    "delegation",
    "iso3",
    "status",
    "date",
    "honorific",
    "speaker_name",
    "speaker_title",
    "role",
    "role_group",
    "original_language",
    "english_source",
    "delivered_share",
    "unscripted_share",
    "page_url",
    "daily_summary_url",
    "gaps",
]


def write_outputs(session: int, speeches: list[Speech], pending: list[str], delegations: list[dict]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUTPUT_DIR / f"speeches_{session}.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, SPEECH_COLUMNS)
        writer.writeheader()
        for s in sorted(speeches, key=lambda s: (s.date or "", s.slug)):
            row = {k: getattr(s, k) for k in SPEECH_COLUMNS if k != "gaps"}
            writer.writerow({**row, "gaps": " | ".join(s.gaps)})
    with (OUTPUT_DIR / f"texts_{session}.jsonl").open("w", encoding="utf-8") as f:
        for s in speeches:
            for v in s.texts:
                f.write(json.dumps({"session": session, "slug": s.slug, **asdict(v)}, ensure_ascii=False) + "\n")
    write_completeness_report(session, speeches, pending, delegations)
