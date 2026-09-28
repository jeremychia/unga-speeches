from dataclasses import dataclass, field


@dataclass
class TextVersion:
    kind: str  # statement or transcript
    language: str | None
    source_url: str
    retrieved_at: str
    sha256: str
    method: str  # text_layer, ocr, none, or ai_transcript
    text: str
    role: str = ""  # original or english
    index: int = 0
    floor_version: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class Speech:
    session: int
    year: int
    slug: str
    delegation: str
    iso3: str | None
    status: str
    page_url: str
    page_retrieved_at: str | None
    honorific: str | None
    speaker_name: str | None
    speaker_title: str | None
    role: str
    role_group: str
    date: str | None
    daily_summary_url: str | None
    original_language: str | None = None
    english_source: str = "none"
    # filed statement against the transcript in the spoken language; none when either is missing
    delivered_share: float | None = None
    unscripted_share: float | None = None
    texts: list[TextVersion] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
