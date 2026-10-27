#!/usr/bin/env python3
"""Measure bounded v2 behavior using deterministic synthetic fixtures.

Run from the repository root with the backend test environment:

    PYTHONPATH=flask-mdict python tools/measure-v2-acceptance.py
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import time

from citations import derive_purpose_key
from domain import LookupBounds, SourceRecord
from lookup_services import (
    AllSourcesFailed,
    LookupService,
    SourceCatalog,
    build_lookup_cache_key,
)
from source_catalog import discover_source_files
from tests.support.source_fakes import FakeDictionarySource, FakeEntryRecord


SECRET = b"synthetic-acceptance-secret-at-least-32-bytes"
CITATION_KEY = derive_purpose_key(SECRET, "citations")
ASSET_KEY = derive_purpose_key(SECRET, "assets")


class MemoryCache:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    def get(self, key: str) -> object | None:
        return self.values.get(key)

    def set(self, key: str, value: object) -> None:
        self.values[key] = value


def descriptor(source: FakeDictionarySource) -> SourceRecord:
    return SourceRecord(
        source.source_id,
        source.revision,
        source.title,
        source.enabled,
        source.sort_order,
        source.available,
        source.unavailable_reason,
    )


def service(
    *sources: FakeDictionarySource,
    bounds: LookupBounds | None = None,
    cache: MemoryCache | None = None,
    max_workers: int = 4,
    queue_capacity: int = 8,
    source_timeout_seconds: float = 2.0,
) -> LookupService:
    catalog = SourceCatalog(
        (descriptor(source) for source in sources),
        {source.source_id: source for source in sources},
    )
    return LookupService(
        catalog,
        citation_signing_key=CITATION_KEY,
        asset_signing_key=ASSET_KEY,
        bounds=bounds,
        cache=cache,
        max_workers=max_workers,
        queue_capacity=queue_capacity,
        source_timeout_seconds=source_timeout_seconds,
    )


def measured_call(callable_):
    started = time.perf_counter()
    result = callable_()
    return result, round((time.perf_counter() - started) * 1_000, 3)


def main() -> None:
    metrics: dict[str, object] = {}

    with tempfile.TemporaryDirectory(prefix="mdict-live-acceptance-") as temporary:
        library = Path(temporary) / "library"
        library.mkdir()
        fixture_bytes = b"mdict-fixture-block" * (8 * 1024 * 1024 // 19)
        (library / "measured.mdx").write_bytes(fixture_bytes)
        first, initial_hash_ms = measured_call(lambda: discover_source_files(library))
        second, repeat_hash_ms = measured_call(lambda: discover_source_files(library))
        assert first[0].revision == second[0].revision
        metrics["hashing"] = {
            "fixture_bytes": len(fixture_bytes),
            "initial_ms": initial_hash_ms,
            "repeat_full_verification_ms": repeat_hash_ms,
            "stable_revision": True,
        }

    cached_source = FakeDictionarySource(
        "src_cached",
        "rev_fixture_0001",
        "Cached fixture",
        records={
            "right": (
                FakeEntryRecord(
                    "right",
                    "<p>Correct, suitable, or on the side opposite left.</p>",
                ),
            )
        },
    )
    memory_cache = MemoryCache()
    lookup = service(cached_source, cache=memory_cache)
    try:
        cold, cold_ms = measured_call(lambda: lookup.lookup("right"))
        warm, warm_ms = measured_call(lambda: lookup.lookup("right"))
    finally:
        lookup.close()
    assert cold.entries == warm.entries
    assert cached_source.lookup_calls == ["right"]
    metrics["lookup_cache"] = {
        "cold_ms": cold_ms,
        "warm_ms": warm_ms,
        "source_calls": len(cached_source.lookup_calls),
        "warm_cache_hit": True,
    }

    healthy = FakeDictionarySource(
        "src_healthy",
        "rev_fixture_0001",
        "Healthy fixture",
        records={"word": (FakeEntryRecord("word", "<p>evidence</p>"),)},
        sort_order=0,
    )
    failing = FakeDictionarySource(
        "src_failing",
        "rev_fixture_0002",
        "Failing fixture",
        lookup_error=RuntimeError("private fixture detail"),
        sort_order=1,
    )
    lookup = service(healthy, failing)
    try:
        partial, partial_ms = measured_call(lambda: lookup.lookup("word"))
    finally:
        lookup.close()
    assert partial.partial and len(partial.entries) == 1
    metrics["partial_failure"] = {
        "elapsed_ms": partial_ms,
        "evidence_entries": len(partial.entries),
        "failure_code": partial.progress.failed_sources[0].code,
    }

    oversized = FakeDictionarySource(
        "src_oversized",
        "rev_fixture_0001",
        "Oversized fixture",
        records={"word": (FakeEntryRecord("word", "<p>oversized entry</p>"),)},
    )
    lookup = service(oversized, bounds=LookupBounds(html_response_bytes=10))
    try:
        bounded = lookup.lookup("word", representations=("html",))
    finally:
        lookup.close()
    assert bounded.entries == () and bounded.truncated
    metrics["response_bounds"] = {
        "html_response_bytes": 10,
        "returned_entries": 0,
        "causes": list(bounded.truncation_causes),
    }

    slow = FakeDictionarySource(
        "src_slow",
        "rev_fixture_0001",
        "Slow fixture",
        lookup_delay_seconds=0.05,
    )
    lookup = service(
        slow,
        max_workers=1,
        queue_capacity=0,
        source_timeout_seconds=0.005,
    )
    started = time.perf_counter()
    try:
        try:
            lookup.lookup("word")
            raise AssertionError("slow fixture should time out")
        except AllSourcesFailed as error:
            timeout_code = error.progress.failed_sources[0].code
    finally:
        timeout_ms = round((time.perf_counter() - started) * 1_000, 3)
        lookup.close()
    assert timeout_code == "source_timeout"
    metrics["source_timeout"] = {
        "configured_ms": 5,
        "returned_ms": timeout_ms,
        "failure_code": timeout_code,
    }

    occupied = FakeDictionarySource(
        "src_occupied",
        "rev_fixture_0001",
        "Occupied fixture",
        records={"word": (FakeEntryRecord("word", "<p>first</p>"),)},
        lookup_delay_seconds=0.01,
        sort_order=0,
    )
    rejected = FakeDictionarySource(
        "src_rejected",
        "rev_fixture_0002",
        "Rejected fixture",
        sort_order=1,
    )
    lookup = service(occupied, rejected, max_workers=1, queue_capacity=0)
    try:
        saturated, saturated_ms = measured_call(lambda: lookup.lookup("word"))
    finally:
        lookup.close()
    assert saturated.partial
    assert saturated.progress.failed_sources[0].code == "executor_saturated"
    metrics["executor_saturation"] = {
        "workers": 1,
        "queue_capacity": 0,
        "elapsed_ms": saturated_ms,
        "failure_code": saturated.progress.failed_sources[0].code,
    }

    source_record = descriptor(cached_source)
    original_key = build_lookup_cache_key(
        "right", (source_record,), ("text",), LookupBounds()
    )
    changed_key = build_lookup_cache_key(
        "right",
        (replace(source_record, revision="rev_fixture_0002"),),
        ("text",),
        LookupBounds(),
    )
    assert original_key != changed_key
    metrics["cache_invalidation"] = {
        "revision_change_changes_key": True,
        "keys_include_secret": SECRET.decode() in original_key + changed_key,
    }

    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
