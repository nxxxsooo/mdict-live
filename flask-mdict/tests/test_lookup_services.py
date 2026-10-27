from __future__ import annotations

from dataclasses import replace
import time
import unicodedata

import pytest

from citations import derive_purpose_key
from domain import LookupBounds, MetadataDataset, MetadataRecord, SourceRecord
from lookup_services import (
    AllSourcesFailed,
    LookupService,
    LookupValidationError,
    MetadataService,
    SourceCatalog,
    SuggestionService,
    UnknownSourceSelection,
    build_lookup_cache_key,
    normalize_query,
)
from tests.support.source_fakes import FakeDictionarySource, FakeEntryRecord


SECRET = b"synthetic-test-secret-that-is-at-least-32-bytes"
CITATION_KEY = derive_purpose_key(SECRET, "citations")
ASSET_KEY = derive_purpose_key(SECRET, "assets")


def descriptor(source: FakeDictionarySource) -> SourceRecord:
    return SourceRecord(
        source_id=source.source_id,
        revision=source.revision,
        title=source.title,
        enabled=source.enabled,
        sort_order=source.sort_order,
        available=source.available,
        unavailable_reason=source.unavailable_reason,
    )


def catalog(*sources: FakeDictionarySource) -> SourceCatalog:
    return SourceCatalog(
        (descriptor(source) for source in sources),
        {source.source_id: source for source in sources},
    )


def source(
    source_id: str,
    *,
    records: dict[str, tuple[FakeEntryRecord, ...]] | None = None,
    enabled: bool = True,
    available: bool = True,
    sort_order: int = 0,
    revision: str = "rev_fixture_0001",
    lookup_error: Exception | None = None,
    delay: float = 0.0,
) -> FakeDictionarySource:
    return FakeDictionarySource(
        source_id=source_id,
        revision=revision,
        title=source_id,
        records=records or {},
        enabled=enabled,
        available=available,
        unavailable_reason=None if available else "parser_initialization_failed",
        sort_order=sort_order,
        lookup_error=lookup_error,
        lookup_delay_seconds=delay,
    )


def service(source_catalog: SourceCatalog, **kwargs) -> LookupService:
    return LookupService(
        source_catalog,
        citation_signing_key=CITATION_KEY,
        asset_signing_key=ASSET_KEY,
        **kwargs,
    )


def test_query_normalization_is_nfc_and_preserves_internal_punctuation() -> None:
    query = " \u3000cafe\u0301 / au lait\u3000 "

    normalized = normalize_query(query)

    assert normalized == unicodedata.normalize("NFC", "cafe\u0301 / au lait")
    assert "/" in normalized


def test_query_validation_has_field_specific_empty_and_length_errors() -> None:
    with pytest.raises(LookupValidationError) as empty:
        normalize_query(" \u3000 ")
    with pytest.raises(LookupValidationError) as long:
        normalize_query("x" * 257)

    assert empty.value.field == "query"
    assert long.value.field == "query"


def test_catalog_orders_sources_and_allows_explicit_disabled_selection() -> None:
    later = source("src_later", enabled=True, sort_order=2)
    disabled = source("src_disabled", enabled=False, sort_order=1)
    source_catalog = catalog(later, disabled)

    defaults, _ = source_catalog.select(None, 32)
    explicit, _ = source_catalog.select([disabled.source_id], 32)

    assert [item.source_id for item in source_catalog.list_sources()] == [
        "src_disabled",
        "src_later",
    ]
    assert [item.source_id for item in defaults] == ["src_later"]
    assert [item.source_id for item in explicit] == ["src_disabled"]


def test_unknown_explicit_source_is_rejected_before_lookup() -> None:
    lookup_service = service(catalog(source("src_known")))
    try:
        with pytest.raises(UnknownSourceSelection) as captured:
            lookup_service.lookup("right", source_ids=["src_missing"])
    finally:
        lookup_service.close()

    assert captured.value.source_ids == ("src_missing",)


def test_lookup_returns_same_record_html_text_and_citations() -> None:
    primary = source(
        "src_primary",
        records={
            "right": (
                FakeEntryRecord(
                    "right",
                    '<style>.sense{color:teal}</style><p class="sense">Correct as a fact.</p>',
                    ordinal=4,
                ),
            )
        },
    )
    lookup_service = service(catalog(primary), epoch_clock=lambda: 1_800_000_000)
    try:
        result = lookup_service.lookup(" right ")
    finally:
        lookup_service.close()

    assert result.normalized_query == "right"
    assert result.partial is False
    assert result.truncated is False
    assert len(result.entries) == 1
    entry = result.entries[0]
    assert entry.record_ordinal == 4
    assert ".sense{color:teal}" in entry.html
    assert [block.text for block in entry.text_blocks] == ["Correct as a fact."]
    assert entry.citation.uri.startswith("mdict://src_primary/")
    assert entry.text_blocks[0].citation.uri.endswith(
        f"#{entry.text_blocks[0].block_id}"
    )


def test_history_is_explicit_and_records_normalized_query_once_after_match() -> None:
    primary = source(
        "src_primary",
        records={"café": (FakeEntryRecord("café", "<p>Coffee.</p>"),)},
    )
    recorded: list[str] = []
    lookup_service = service(catalog(primary), history_recorder=recorded.append)
    try:
        ordinary = lookup_service.lookup(" cafe\u0301 ")
        explicit = lookup_service.lookup(" cafe\u0301 ", record_history=True)
        missing = lookup_service.lookup("missing", record_history=True)
    finally:
        lookup_service.close()

    assert ordinary.history_recorded is False
    assert explicit.history_recorded is True
    assert missing.history_recorded is False
    assert recorded == ["café"]


def test_source_and_entry_bounds_report_complete_omissions() -> None:
    first = source(
        "src_first",
        records={
            "word": (
                FakeEntryRecord("word", "<p>first</p>", ordinal=0),
                FakeEntryRecord("word", "<p>second</p>", ordinal=1),
            )
        },
        sort_order=0,
    )
    second = source(
        "src_second",
        records={"word": (FakeEntryRecord("word", "<p>third</p>"),)},
        sort_order=1,
    )
    lookup_service = service(
        catalog(first, second),
        bounds=LookupBounds(source_limit=1, entry_limit=1),
    )
    try:
        result = lookup_service.lookup("word")
    finally:
        lookup_service.close()

    assert len(result.entries) == 1
    assert result.truncated is True
    assert result.truncation_causes == ("source_limit", "entry_limit")
    assert result.progress.omitted_source_ids == ("src_second",)


def test_text_bounds_stop_between_blocks_and_keep_complete_entry() -> None:
    primary = source(
        "src_primary",
        records={"word": (FakeEntryRecord("word", "<p>alpha</p><p>bravo</p>"),)},
    )
    lookup_service = service(
        catalog(primary),
        bounds=LookupBounds(text_entry_bytes=5, text_response_bytes=100),
    )
    try:
        result = lookup_service.lookup("word", representations=("text",))
    finally:
        lookup_service.close()

    assert result.entries[0].html is None
    assert [block.text for block in result.entries[0].text_blocks] == ["alpha"]
    assert result.truncation_causes == ("text_entry_bytes",)


def test_html_bound_omits_oversized_complete_entry() -> None:
    primary = source(
        "src_primary",
        records={"word": (FakeEntryRecord("word", "<p>larger than ten bytes</p>"),)},
    )
    lookup_service = service(
        catalog(primary),
        bounds=LookupBounds(html_response_bytes=10),
    )
    try:
        result = lookup_service.lookup("word", representations=("html",))
    finally:
        lookup_service.close()

    assert result.entries == ()
    assert result.truncation_causes == ("html_response_bytes",)


def test_one_failed_source_returns_deterministic_partial_evidence() -> None:
    healthy = source(
        "src_healthy",
        records={"word": (FakeEntryRecord("word", "<p>evidence</p>"),)},
        sort_order=0,
    )
    failing = source(
        "src_failing",
        lookup_error=RuntimeError("private detail"),
        sort_order=1,
    )
    lookup_service = service(catalog(healthy, failing))
    try:
        result = lookup_service.lookup("word")
    finally:
        lookup_service.close()

    assert result.partial is True
    assert [entry.source_id for entry in result.entries] == ["src_healthy"]
    assert result.progress.completed_source_ids == ("src_healthy",)
    assert result.progress.failed_sources[0].code == "source_error"
    assert "private detail" not in result.progress.failed_sources[0].message


def test_empty_success_plus_failure_is_still_http_200_domain_partial() -> None:
    empty = source("src_empty", sort_order=0)
    unavailable = source("src_unavailable", available=False, sort_order=1)
    lookup_service = service(catalog(empty, unavailable))
    try:
        result = lookup_service.lookup("word")
    finally:
        lookup_service.close()

    assert result.entries == ()
    assert result.partial is True
    assert result.progress.completed_source_ids == ("src_empty",)
    assert result.progress.failed_sources[0].source_id == "src_unavailable"


def test_every_failed_source_raises_structured_unavailable_result() -> None:
    failing = source("src_failing", lookup_error=RuntimeError("failure"))
    lookup_service = service(catalog(failing))
    try:
        with pytest.raises(AllSourcesFailed) as captured:
            lookup_service.lookup("word")
    finally:
        lookup_service.close()

    assert captured.value.progress.completed_source_ids == ()
    assert captured.value.progress.failed_sources[0].code == "source_error"


def test_slow_source_times_out_without_unbounded_wait() -> None:
    slow = source("src_slow", delay=0.05)
    lookup_service = service(
        catalog(slow), source_timeout_seconds=0.001, max_workers=1, queue_capacity=0
    )
    started = time.monotonic()
    try:
        with pytest.raises(AllSourcesFailed) as captured:
            lookup_service.lookup("word")
    finally:
        lookup_service.close()

    assert time.monotonic() - started < 0.04
    assert captured.value.progress.failed_sources[0].code == "source_timeout"


def test_bounded_executor_reports_saturation_in_source_order() -> None:
    first = source(
        "src_first",
        records={"word": (FakeEntryRecord("word", "<p>one</p>"),)},
        delay=0.01,
        sort_order=0,
    )
    second = source("src_second", sort_order=1)
    lookup_service = service(
        catalog(first, second), max_workers=1, queue_capacity=0, source_timeout_seconds=1
    )
    try:
        result = lookup_service.lookup("word")
    finally:
        lookup_service.close()

    assert result.partial is True
    assert result.progress.completed_source_ids == ("src_first",)
    assert result.progress.failed_sources[0].source_id == "src_second"
    assert result.progress.failed_sources[0].code == "executor_saturated"


def test_link_indirection_lookup_is_inside_the_same_source_timeout() -> None:
    linked = source(
        "src_linked",
        records={
            "word": (FakeEntryRecord("word", "@@@LINK=target"),),
            "target": (FakeEntryRecord("target", "<p>resolved</p>"),),
        },
        delay=0.04,
    )
    lookup_service = service(
        catalog(linked),
        max_workers=1,
        queue_capacity=0,
        source_timeout_seconds=0.06,
    )
    try:
        with pytest.raises(AllSourcesFailed) as captured:
            lookup_service.lookup("word")
    finally:
        lookup_service.close()

    assert captured.value.progress.failed_sources[0].code == "source_timeout"


def test_suggestions_are_deduplicated_deterministic_and_optionally_fuzzy() -> None:
    first = source(
        "src_first",
        records={
            "right": (FakeEntryRecord("right", "<p/>"),),
            "rigid": (FakeEntryRecord("rigid", "<p/>"),),
        },
        sort_order=0,
    )
    second = source(
        "src_second",
        records={
            "right": (FakeEntryRecord("right", "<p/>"),),
            "rite": (FakeEntryRecord("rite", "<p/>"),),
        },
        sort_order=1,
    )
    suggestion_service = SuggestionService(catalog(first, second))

    prefix = suggestion_service.suggest("ri")
    fuzzy = suggestion_service.suggest("rigt", fuzzy=True)

    assert [item.headword for item in prefix.suggestions] == ["right", "rigid", "rite"]
    right = next(item for item in prefix.suggestions if item.headword == "right")
    assert right.source_ids == ("src_first", "src_second")
    assert fuzzy.suggestions[0].headword == "right"
    assert fuzzy.suggestions[0].kind == "fuzzy"


class FakeMetadataProvider:
    def __init__(self, available: bool) -> None:
        self.available = available
        self.unavailable_reason = None if available else "dataset_missing"

    def lookup(self, query: str):
        return (
            MetadataRecord(
                query=query,
                dataset=MetadataDataset("fixture", "Fixture metadata", "1"),
                definition="synthetic definition",
            ),
        )


def test_missing_metadata_is_nonfatal_and_named_dataset_stays_separate() -> None:
    missing = MetadataService(FakeMetadataProvider(False)).lookup("right")
    available = MetadataService(FakeMetadataProvider(True)).lookup("right")

    assert missing.available is False
    assert missing.records == ()
    assert missing.unavailable_reason == "dataset_missing"
    assert available.records[0].dataset.dataset_id == "fixture"
    assert available.records[0].definition == "synthetic definition"


def test_cache_key_changes_with_revision_order_representation_and_bounds() -> None:
    first = SourceRecord("src_first", "rev_000000000001", "First", True, 0)
    second = SourceRecord("src_second", "rev_000000000002", "Second", True, 1)
    base = build_lookup_cache_key("right", (first, second), ("text",), LookupBounds())

    assert base != build_lookup_cache_key(
        "right", (replace(first, revision="rev_changed_0001"), second), ("text",), LookupBounds()
    )
    assert base != build_lookup_cache_key(
        "right", (second, first), ("text",), LookupBounds()
    )
    assert base != build_lookup_cache_key(
        "right", (first, second), ("html",), LookupBounds()
    )
    assert base != build_lookup_cache_key(
        "right", (first, second), ("text",), LookupBounds(entry_limit=1)
    )


def test_default_source_state_change_cannot_reuse_old_aggregate_cache_key() -> None:
    first = source("src_first", sort_order=0)
    second = source("src_second", sort_order=1)
    enabled_catalog = catalog(first, second)
    enabled_selection, _ = enabled_catalog.select(None, 32)
    first_key = build_lookup_cache_key(
        "right", enabled_selection, ("text",), LookupBounds()
    )
    second.enabled = False
    disabled_catalog = catalog(first, second)
    disabled_selection, _ = disabled_catalog.select(None, 32)
    second_key = build_lookup_cache_key(
        "right", disabled_selection, ("text",), LookupBounds()
    )

    assert [item.source_id for item in disabled_selection] == ["src_first"]
    assert first_key != second_key


class MemoryCache:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    def get(self, key: str) -> object | None:
        return self.values.get(key)

    def set(self, key: str, value: object) -> None:
        self.values[key] = value


def test_complete_lookup_cache_never_contains_or_keys_on_credentials() -> None:
    primary = source(
        "src_primary",
        records={"right": (FakeEntryRecord("right", "<p>correct</p>"),)},
    )
    result_cache = MemoryCache()
    lookup_service = service(catalog(primary), cache=result_cache)
    try:
        first = lookup_service.lookup("right")
        primary.records.clear()
        cached = lookup_service.lookup("right")
    finally:
        lookup_service.close()

    assert cached.entries == first.entries
    assert all(SECRET.decode() not in key for key in result_cache.values)
