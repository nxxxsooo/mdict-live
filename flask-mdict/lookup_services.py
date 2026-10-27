"""Bounded catalog, lookup, suggestion, metadata, and cache-key services."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import asdict, replace
import difflib
import hashlib
import json
import threading
import time
from typing import Protocol
import unicodedata

from citations import cite_rendered_record
from domain import (
    API_SCHEMA_VERSION,
    EntryRecord,
    LookupBounds,
    LookupProgress,
    LookupResult,
    MetadataResult,
    SourceLookupError,
    SourceRecord,
    SuggestionRecord,
    SuggestionResult,
    TextBlockRecord,
)
from representation import (
    RawSourceRecord,
    ResolvedSourceRecord,
    build_resolved_record_representations,
    resolve_mdict_links,
)
from resource_capabilities import issue_resource_capability


class LookupValidationError(ValueError):
    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


class UnknownSourceSelection(LookupValidationError):
    def __init__(self, source_ids: Sequence[str]):
        self.source_ids = tuple(source_ids)
        super().__init__("source_ids", "one or more selected sources are unknown")


class AllSourcesFailed(RuntimeError):
    def __init__(self, progress: LookupProgress):
        super().__init__("every selected dictionary source failed")
        self.progress = progress


class SourceAdapter(Protocol):
    def lookup(self, query: str) -> Sequence[object]: ...

    def suggest(self, prefix: str, limit: int) -> Sequence[str]: ...


class MetadataProvider(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def unavailable_reason(self) -> str | None: ...

    def lookup(self, query: str) -> Sequence[object]: ...


class ResultCache(Protocol):
    def get(self, key: str) -> object | None: ...

    def set(self, key: str, value: object) -> None: ...


def normalize_query(query: str, maximum_characters: int = 256) -> str:
    if not isinstance(query, str):
        raise LookupValidationError("query", "query must be a string")
    normalized = unicodedata.normalize("NFC", query.strip())
    if not normalized:
        raise LookupValidationError("query", "query must not be empty")
    if len(normalized) > maximum_characters:
        raise LookupValidationError(
            "query", f"query must not exceed {maximum_characters} Unicode scalar values"
        )
    return normalized


class SourceCatalog:
    def __init__(
        self,
        sources: Iterable[SourceRecord],
        adapters: Mapping[str, SourceAdapter],
    ) -> None:
        ordered = sorted(sources, key=lambda source: (source.sort_order, source.source_id))
        if len({source.source_id for source in ordered}) != len(ordered):
            raise ValueError("source_id values must be unique")
        self._sources = tuple(ordered)
        self._by_id = {source.source_id: source for source in ordered}
        self._adapters = dict(adapters)

    @classmethod
    def from_registered_sources(
        cls,
        registered_sources: Iterable[object],
        adapters: Mapping[str, SourceAdapter],
    ) -> "SourceCatalog":
        return cls(
            (
                SourceRecord(
                    source_id=str(source.source_id),
                    revision=str(source.revision),
                    title=str(source.title),
                    enabled=bool(source.enabled),
                    sort_order=int(source.sort_order),
                    available=bool(source.available),
                    unavailable_reason=source.unavailable_reason,
                )
                for source in registered_sources
            ),
            adapters,
        )

    def list_sources(self) -> tuple[SourceRecord, ...]:
        return self._sources

    def replace_source(self, updated: SourceRecord) -> None:
        if updated.source_id not in self._by_id:
            raise KeyError(updated.source_id)
        sources = [
            updated if source.source_id == updated.source_id else source
            for source in self._sources
        ]
        self._sources = tuple(
            sorted(sources, key=lambda source: (source.sort_order, source.source_id))
        )
        self._by_id = {source.source_id: source for source in self._sources}

    def adapter(self, source_id: str) -> SourceAdapter | None:
        return self._adapters.get(source_id)

    def select(
        self,
        source_ids: Sequence[str] | None,
        source_limit: int,
    ) -> tuple[tuple[SourceRecord, ...], tuple[str, ...]]:
        if source_ids is None:
            candidates = [source for source in self._sources if source.enabled]
        else:
            unknown = sorted(set(source_ids) - self._by_id.keys())
            if unknown:
                raise UnknownSourceSelection(unknown)
            selected_set = set(source_ids)
            candidates = [
                source for source in self._sources if source.source_id in selected_set
            ]
        selected = tuple(candidates[:source_limit])
        omitted = tuple(source.source_id for source in candidates[source_limit:])
        return selected, omitted


def _raw_record(record: object, fallback_headword: str, ordinal: int) -> RawSourceRecord:
    if isinstance(record, RawSourceRecord):
        return record
    headword = str(getattr(record, "headword", fallback_headword))
    html = getattr(record, "html", None)
    if not isinstance(html, str):
        if isinstance(record, str):
            html = record
        else:
            raise TypeError("source lookup record must contain HTML text")
    record_ordinal = getattr(record, "record_ordinal", getattr(record, "ordinal", ordinal))
    return RawSourceRecord(headword, int(record_ordinal), html)


def build_lookup_cache_key(
    normalized_query: str,
    sources: Sequence[SourceRecord],
    representations: Sequence[str],
    bounds: LookupBounds,
) -> str:
    payload = {
        "api": API_SCHEMA_VERSION,
        "bounds": asdict(bounds),
        "query": normalized_query,
        "representations": list(representations),
        "sources": [
            {"source_id": source.source_id, "revision": source.revision}
            for source in sources
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "v2:lookup:" + hashlib.sha256(canonical).hexdigest()


class LookupService:
    def __init__(
        self,
        catalog: SourceCatalog,
        *,
        citation_signing_key: bytes,
        asset_signing_key: bytes,
        bounds: LookupBounds | None = None,
        source_timeout_seconds: float = 2.0,
        max_workers: int = 4,
        queue_capacity: int = 32,
        history_recorder: Callable[[str], None] | None = None,
        cache: ResultCache | None = None,
        clock: Callable[[], float] = time.monotonic,
        epoch_clock: Callable[[], int] = lambda: int(time.time()),
    ) -> None:
        if source_timeout_seconds <= 0:
            raise ValueError("source timeout must be positive")
        if max_workers < 1 or queue_capacity < 0:
            raise ValueError("executor bounds are invalid")
        self.catalog = catalog
        self.citation_signing_key = citation_signing_key
        self.asset_signing_key = asset_signing_key
        self.bounds = bounds or LookupBounds()
        self.source_timeout_seconds = source_timeout_seconds
        self.history_recorder = history_recorder
        self.cache = cache
        self.clock = clock
        self.epoch_clock = epoch_clock
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="mdict-source"
        )
        self._slots = threading.BoundedSemaphore(max_workers + queue_capacity)

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _lookup_source(
        self, source: SourceRecord, normalized_query: str
    ) -> tuple[ResolvedSourceRecord, ...]:
        adapter = self.catalog.adapter(source.source_id)
        if adapter is None:
            raise RuntimeError("source adapter is unavailable")
        raw_records = tuple(
            _raw_record(record, normalized_query, ordinal)
            for ordinal, record in enumerate(adapter.lookup(normalized_query))
        )

        def linked_lookup(target: str) -> tuple[RawSourceRecord, ...]:
            return tuple(
                _raw_record(record, target, ordinal)
                for ordinal, record in enumerate(adapter.lookup(target))
            )

        return resolve_mdict_links(raw_records, linked_lookup)

    def _submit(
        self, source: SourceRecord, normalized_query: str
    ) -> Future[tuple[ResolvedSourceRecord, ...]] | None:
        if not self._slots.acquire(blocking=False):
            return None
        try:
            future = self._executor.submit(
                self._lookup_source, source, normalized_query
            )
        except Exception:
            self._slots.release()
            raise
        future.add_done_callback(lambda _future: self._slots.release())
        return future

    def lookup(
        self,
        query: str,
        *,
        source_ids: Sequence[str] | None = None,
        representations: Sequence[str] = ("html", "text"),
        entry_limit: int | None = None,
        record_history: bool = False,
    ) -> LookupResult:
        started = self.clock()
        normalized_query = normalize_query(query, self.bounds.query_characters)
        requested_representations = tuple(dict.fromkeys(representations))
        if not requested_representations or not set(requested_representations) <= {
            "html",
            "text",
        }:
            raise LookupValidationError(
                "representations", "representations must contain html and/or text"
            )
        effective_entry_limit = self.bounds.entry_limit
        if entry_limit is not None:
            if entry_limit < 1:
                raise LookupValidationError("limit", "entry limit must be positive")
            effective_entry_limit = min(entry_limit, self.bounds.entry_limit)
        applied_bounds = LookupBounds(
            query_characters=self.bounds.query_characters,
            source_limit=self.bounds.source_limit,
            entry_limit=effective_entry_limit,
            text_response_bytes=self.bounds.text_response_bytes,
            text_entry_bytes=self.bounds.text_entry_bytes,
            html_response_bytes=self.bounds.html_response_bytes,
        )
        selected, omitted = self.catalog.select(source_ids, applied_bounds.source_limit)
        cache_key = build_lookup_cache_key(
            normalized_query, selected, requested_representations, applied_bounds
        )
        if self.cache is not None:
            cached = self.cache.get(cache_key)
            if isinstance(cached, LookupResult):
                history_recorded = False
                if record_history and cached.entries and self.history_recorder is not None:
                    self.history_recorder(normalized_query)
                    history_recorded = True
                return replace(cached, history_recorded=history_recorded)

        failures: dict[str, SourceLookupError] = {}
        futures: dict[str, Future[tuple[ResolvedSourceRecord, ...]]] = {}
        for source in selected:
            if not source.available:
                failures[source.source_id] = SourceLookupError(
                    source.source_id,
                    source.unavailable_reason or "source_unavailable",
                    "The source is unavailable.",
                )
                continue
            future = self._submit(source, normalized_query)
            if future is None:
                failures[source.source_id] = SourceLookupError(
                    source.source_id,
                    "executor_saturated",
                    "The bounded source executor is saturated.",
                )
            else:
                futures[source.source_id] = future

        done, not_done = wait(
            tuple(futures.values()), timeout=self.source_timeout_seconds
        ) if futures else (set(), set())
        for source_id, future in futures.items():
            if future in not_done:
                future.cancel()
                failures[source_id] = SourceLookupError(
                    source_id,
                    "source_timeout",
                    "The source did not complete within its configured bound.",
                )
            elif future.exception() is not None:
                failures[source_id] = SourceLookupError(
                    source_id,
                    "source_error",
                    "The source lookup failed.",
                )

        completed_sources = tuple(
            source
            for source in selected
            if source.source_id in futures
            and futures[source.source_id] in done
            and source.source_id not in failures
        )
        progress = LookupProgress(
            selected_source_ids=tuple(source.source_id for source in selected),
            completed_source_ids=tuple(source.source_id for source in completed_sources),
            failed_sources=tuple(
                failures[source.source_id]
                for source in selected
                if source.source_id in failures
            ),
            omitted_source_ids=omitted,
        )
        if selected and not completed_sources:
            raise AllSourcesFailed(progress)

        entries: list[EntryRecord] = []
        truncation_causes: list[str] = []
        text_response_bytes = 0
        html_response_bytes = 0
        now_epoch = self.epoch_clock()
        stop_entries = False
        for source in completed_sources:
            def resource_url(path: str, _kind: str) -> str:
                return issue_resource_capability(
                    source.source_id,
                    source.revision,
                    path,
                    self.asset_signing_key,
                    now=now_epoch,
                ).url

            rendered_records = build_resolved_record_representations(
                futures[source.source_id].result(), resource_url
            )
            for rendered in rendered_records:
                if len(entries) >= applied_bounds.entry_limit:
                    if "entry_limit" not in truncation_causes:
                        truncation_causes.append("entry_limit")
                    stop_entries = True
                    break
                cited = cite_rendered_record(
                    source.source_id,
                    source.revision,
                    rendered,
                    self.citation_signing_key,
                )
                html_value = cited.html if "html" in requested_representations else None
                html_bytes = len(html_value.encode("utf-8")) if html_value else 0
                if html_response_bytes + html_bytes > applied_bounds.html_response_bytes:
                    if "html_response_bytes" not in truncation_causes:
                        truncation_causes.append("html_response_bytes")
                    stop_entries = True
                    break

                blocks: list[TextBlockRecord] = []
                entry_text_bytes = 0
                if "text" in requested_representations:
                    for block in cited.text_blocks:
                        block_bytes = len(block.text.encode("utf-8"))
                        if entry_text_bytes + block_bytes > applied_bounds.text_entry_bytes:
                            if "text_entry_bytes" not in truncation_causes:
                                truncation_causes.append("text_entry_bytes")
                            break
                        if text_response_bytes + block_bytes > applied_bounds.text_response_bytes:
                            if "text_response_bytes" not in truncation_causes:
                                truncation_causes.append("text_response_bytes")
                            break
                        blocks.append(
                            TextBlockRecord(
                                block.block_id,
                                block.order,
                                block.text,
                                block.citation,
                            )
                        )
                        entry_text_bytes += block_bytes
                        text_response_bytes += block_bytes
                entries.append(
                    EntryRecord(
                        source_id=source.source_id,
                        revision=source.revision,
                        entry_id=cited.entry_id,
                        headword=cited.headword,
                        record_ordinal=cited.record_ordinal,
                        citation=cited.citation,
                        html=html_value,
                        text_blocks=tuple(blocks),
                    )
                )
                html_response_bytes += html_bytes
            if stop_entries:
                break

        if omitted and "source_limit" not in truncation_causes:
            truncation_causes.insert(0, "source_limit")
        history_recorded = False
        if record_history and entries and self.history_recorder is not None:
            self.history_recorder(normalized_query)
            history_recorded = True
        result = LookupResult(
            query=query,
            normalized_query=normalized_query,
            representations=requested_representations,
            entries=tuple(entries),
            partial=bool(failures),
            truncated=bool(truncation_causes),
            truncation_causes=tuple(truncation_causes),
            progress=progress,
            bounds=applied_bounds,
            elapsed_ms=max(0.0, (self.clock() - started) * 1000),
            history_recorded=history_recorded,
        )
        if self.cache is not None and not result.partial and not record_history:
            self.cache.set(cache_key, result)
        return result


class SuggestionService:
    def __init__(
        self,
        catalog: SourceCatalog,
        *,
        default_limit: int = 20,
        maximum_limit: int = 100,
        candidate_limit: int = 300,
    ) -> None:
        self.catalog = catalog
        self.default_limit = default_limit
        self.maximum_limit = maximum_limit
        self.candidate_limit = candidate_limit

    def suggest(
        self,
        prefix: str,
        *,
        source_ids: Sequence[str] | None = None,
        limit: int | None = None,
        fuzzy: bool = False,
    ) -> SuggestionResult:
        normalized = normalize_query(prefix)
        effective_limit = self.default_limit if limit is None else min(limit, self.maximum_limit)
        if effective_limit < 1:
            raise LookupValidationError("limit", "suggestion limit must be positive")
        selected, _omitted = self.catalog.select(source_ids, 32)
        by_headword: dict[str, tuple[str, list[str]]] = {}
        candidate_prefix = normalized if not fuzzy else normalized[:1]
        for source in selected:
            if not source.available:
                continue
            adapter = self.catalog.adapter(source.source_id)
            if adapter is None:
                continue
            for headword in adapter.suggest(candidate_prefix, self.candidate_limit):
                key = headword.casefold()
                if key not in by_headword:
                    by_headword[key] = (headword, [])
                by_headword[key][1].append(source.source_id)

        suggestions = []
        if fuzzy:
            for headword, sources in by_headword.values():
                score = difflib.SequenceMatcher(
                    None, normalized.casefold(), headword.casefold()
                ).ratio()
                suggestions.append(
                    SuggestionRecord(headword, tuple(sources), "fuzzy", round(score, 6))
                )
            suggestions.sort(
                key=lambda item: (
                    -(item.score or 0),
                    item.headword.casefold(),
                    item.headword,
                )
            )
        else:
            suggestions = [
                SuggestionRecord(headword, tuple(sources), "prefix")
                for headword, sources in by_headword.values()
                if headword.casefold().startswith(normalized.casefold())
            ]
            suggestions.sort(key=lambda item: (item.headword.casefold(), item.headword))
        truncated = len(suggestions) > effective_limit
        return SuggestionResult(
            prefix=normalized,
            suggestions=tuple(suggestions[:effective_limit]),
            fuzzy=fuzzy,
            limit=effective_limit,
            truncated=truncated,
        )


class MetadataService:
    def __init__(self, provider: MetadataProvider | None) -> None:
        self.provider = provider

    def lookup(self, query: str) -> MetadataResult:
        normalized = normalize_query(query)
        if self.provider is None or not self.provider.available:
            reason = (
                self.provider.unavailable_reason
                if self.provider is not None
                else "metadata_not_configured"
            )
            return MetadataResult(False, normalized, (), reason)
        return MetadataResult(
            True, normalized, tuple(self.provider.lookup(normalized)), None
        )
