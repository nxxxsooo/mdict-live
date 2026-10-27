"""Framework-independent records shared by API, CLI, and agent adapters."""

from __future__ import annotations

from dataclasses import dataclass

from citations import CitationReference


API_SCHEMA_VERSION = "2.0"


@dataclass(frozen=True, slots=True)
class SourceRecord:
    source_id: str
    revision: str
    title: str
    enabled: bool
    sort_order: int
    available: bool = True
    unavailable_reason: str | None = None
    supported_representations: tuple[str, ...] = ("html", "text")


@dataclass(frozen=True, slots=True)
class TextBlockRecord:
    block_id: str
    order: int
    text: str
    citation: CitationReference


@dataclass(frozen=True, slots=True)
class EntryRecord:
    source_id: str
    revision: str
    entry_id: str
    headword: str
    record_ordinal: int
    citation: CitationReference
    html: str | None
    text_blocks: tuple[TextBlockRecord, ...]


@dataclass(frozen=True, slots=True)
class MetadataDataset:
    dataset_id: str
    title: str
    version: str | None = None


@dataclass(frozen=True, slots=True)
class MetadataRecord:
    query: str
    dataset: MetadataDataset
    phonetic: str | None = None
    frequency: float | None = None
    tags: tuple[str, ...] = ()
    inflections: tuple[tuple[str, str], ...] = ()
    definition: str | None = None
    translation: str | None = None
    legacy_fields: tuple[tuple[str, object], ...] = ()


@dataclass(frozen=True, slots=True)
class MetadataResult:
    available: bool
    query: str
    records: tuple[MetadataRecord, ...]
    unavailable_reason: str | None = None


@dataclass(frozen=True, slots=True)
class LookupBounds:
    query_characters: int = 256
    source_limit: int = 32
    entry_limit: int = 50
    text_response_bytes: int = 64 * 1024
    text_entry_bytes: int = 24 * 1024
    html_response_bytes: int = 4 * 1024 * 1024

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            if getattr(self, field_name) < 1:
                raise ValueError(f"{field_name} must be positive")


@dataclass(frozen=True, slots=True)
class SourceLookupError:
    source_id: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class LookupProgress:
    selected_source_ids: tuple[str, ...]
    completed_source_ids: tuple[str, ...]
    failed_sources: tuple[SourceLookupError, ...]
    omitted_source_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LookupResult:
    query: str
    normalized_query: str
    representations: tuple[str, ...]
    entries: tuple[EntryRecord, ...]
    partial: bool
    truncated: bool
    truncation_causes: tuple[str, ...]
    progress: LookupProgress
    bounds: LookupBounds
    elapsed_ms: float
    history_recorded: bool


@dataclass(frozen=True, slots=True)
class SuggestionRecord:
    headword: str
    source_ids: tuple[str, ...]
    kind: str
    score: float | None = None


@dataclass(frozen=True, slots=True)
class SuggestionResult:
    prefix: str
    suggestions: tuple[SuggestionRecord, ...]
    fuzzy: bool
    limit: int
    truncated: bool
