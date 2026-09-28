"""Write one folder per speech: a readable README.md and the exact source texts beside it."""

import re
from pathlib import Path

from .model import Speech, TextVersion

LANGUAGE_NAMES = {
    "ar": "Arabic", "bn": "Bengali", "cs": "Czech", "de": "German", "en": "English", "es": "Spanish",
    "fr": "French", "it": "Italian", "ja": "Japanese", "ko": "Korean", "lv": "Latvian", "pt": "Portuguese",
    "ro": "Romanian", "ru": "Russian", "uk": "Ukrainian", "zh": "Chinese", "fa": "Persian", "fil": "Filipino",
    "ti": "Tigrinya", "tg": "Tajik", "tk": "Turkmen", "da": "Danish", "bi": "Bislama", "tl": "Tagalog", "hi": "Hindi", "tr": "Turkish", "nl": "Dutch", "el": "Greek",
    "he": "Hebrew", "hy": "Armenian", "ka": "Georgian", "ky": "Kyrgyz", "kk": "Kazakh", "mn": "Mongolian", "sq": "Albanian",
}

KIND_LABEL = {
    "statement": "Official statement, as filed by the delegation (pdf)",
    "transcript": "AI transcript of the audio channel in this language (not an official record)",
    "national_source": "Text published by the delegation's government",
}

RIGHT_TO_LEFT = {"ar", "fa", "he", "ps", "ur", "dv"}

MARKDOWN_SPECIAL = re.compile(r"([\\`*_\[\]<>#|~])")
BULLET_START = re.compile(r"^(\s*)([-+=])(\s)", re.M)
ORDERED_START = re.compile(r"^(\s*)(\d+)([.)])(\s)", re.M)


def language_name(code: str | None) -> str:
    return LANGUAGE_NAMES.get(code or "", code or "not known")


def escape_markdown(text: str) -> str:
    """Escape so the rendered page shows the source characters exactly; the .txt beside it is the unescaped source."""
    text = MARKDOWN_SPECIAL.sub(r"\\\1", text)
    return ORDERED_START.sub(r"\1\2\\\3\4", BULLET_START.sub(r"\1\\\2\3", text))


def text_filename(version: TextVersion) -> str:
    return f"{version.kind}_{version.language or 'unknown'}_{version.index}.txt"


def _section(version: TextVersion) -> str:
    lines = [f"### {KIND_LABEL[version.kind]}", "", f"Source: <{version.source_url}>  "]
    if version.text:
        lines.append(f"Exact text: [{text_filename(version)}]({text_filename(version)})")
    lines.append("")
    lines += [f"> **Note:** {w}" for w in version.warnings]
    if version.warnings:
        lines.append("")
    if not version.text:
        lines.append("_No text could be taken from this source; open the link above._")
    elif version.language in RIGHT_TO_LEFT:
        lines += ['<div dir="rtl">', "", escape_markdown(version.text), "", "</div>"]
    else:
        lines.append(escape_markdown(version.text))
    return "\n".join(lines) + "\n"


def render(speech: Speech, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("*.txt"):
        stale.unlink()
    for version in speech.texts:
        if version.text:
            (out_dir / text_filename(version)).write_text(version.text + "\n", encoding="utf-8")

    front = {
        "session": speech.session,
        "year": speech.year,
        "delegation": speech.delegation,
        "iso3": speech.iso3 or "",
        "status": speech.status,
        "speaker": speech.speaker_name or "",
        "speaker_title": speech.speaker_title or "",
        "role": speech.role,
        "date": speech.date or "",
        "original_language": speech.original_language or "unknown",
        "english_source": speech.english_source,
        "source_page": speech.page_url,
    }
    frontmatter = "\n".join(f"{k}: {_yaml_scalar(v)}" for k, v in front.items())

    sources = ["| Text | Language | Source | Retrieved | SHA-256 |", "| --- | --- | --- | --- | --- |"]
    sources.append(f"| Speaker page (metadata, video) | English | <{speech.page_url}> | {speech.page_retrieved_at or ''} | |")
    for v in speech.texts:
        sources.append(f"| {v.kind} | {language_name(v.language)} | <{v.source_url}> | {v.retrieved_at} | `{v.sha256[:12]}` |")
    if speech.daily_summary_url:
        sources.append(f"| UN meetings coverage (summary, not verbatim) | English | <{speech.daily_summary_url}> | | |")

    original = [v for v in speech.texts if v.role == "original"]
    english = [v for v in speech.texts if v.role == "english"]
    body = [
        f"---\n{frontmatter}\n---\n",
        f"# {speech.delegation}: {speech.speaker_name or 'unknown speaker'}\n",
        f"**{speech.honorific or ''} {speech.speaker_name or ''}**, {speech.speaker_title or 'title not given'} · {speech.date or 'date not given'} · general debate of the {ordinal(speech.session)} session ({speech.year})\n",
        f"Role: `{speech.role}` · Original language: {language_name(speech.original_language)} · English from: `{speech.english_source}`\n",
    ]
    body += [f"> **Gap:** {g}\n" for g in speech.gaps]
    body += ["## Sources\n", "\n".join(sources) + "\n"]
    body.append(f"## Original language: {language_name(speech.original_language)}\n")
    body += [_section(v) for v in original] or [
        "_The spoken language is not known; see the gap above._\n" if speech.original_language is None else "_No original-language text is held by the UN for this speech._\n"
    ]
    if speech.original_language != "en":
        body.append("## English\n")
        body += [_section(v) for v in english] or ["_No English text is available for this speech._\n"]
    path = out_dir / "README.md"
    path.write_text("\n".join(body), encoding="utf-8")
    return path


def _yaml_scalar(value) -> str:
    if isinstance(value, int):
        return str(value)
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
