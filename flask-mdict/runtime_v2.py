"""Compose existing parser objects into the v2 domain and HTTP dependencies."""

from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import sqlite3
from typing import Mapping

from domain import SourceRecord
from legacy_source_adapter import LegacyMdictSourceAdapter
from lookup_services import LookupService, MetadataService, SourceCatalog, SuggestionService
from metadata_providers import ECDICTMetadataProvider
from private_service import PrivateServiceSettings
from source_catalog import (
    discover_source_files,
    list_registered_sources,
    normalize_relative_path,
    sync_source_registry,
    update_source_availability,
    update_source_preferences,
)
from v2_api import V2Dependencies


def _record_history(database_path: Path, word: str) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO history(word, count, last_time)
            VALUES (?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(word) DO UPDATE SET
                count = count + 1,
                last_time = CURRENT_TIMESTAMP
            """,
            (word,),
        )


def _domain_source(source) -> SourceRecord:
    return SourceRecord(
        source_id=source.source_id,
        revision=source.revision,
        title=source.title,
        enabled=source.enabled,
        sort_order=source.sort_order,
        available=source.available,
        unavailable_reason=source.unavailable_reason,
    )


def build_v2_dependencies(
    config: Mapping[str, object],
    legacy_items: Mapping[str, dict[str, object]],
    settings: PrivateServiceSettings,
) -> V2Dependencies:
    library_dir = Path(os.fspath(config["MDICT_LIBRARY_DIR"])).resolve(strict=False)
    database_path = Path(os.fspath(config["APP_DB"])).resolve(strict=False)

    items_by_path: dict[str, dict[str, object]] = {}
    for item in legacy_items.values():
        source_path_value = item.get("source_path")
        if not source_path_value:
            continue
        source_path = Path(os.fspath(source_path_value)).resolve(strict=False)
        try:
            relative_path = normalize_relative_path(source_path.relative_to(library_dir))
        except ValueError:
            continue
        items_by_path[relative_path] = item

    scans = tuple(
        replace(
            scan,
            title=str(items_by_path[scan.relative_path].get("title") or scan.title),
        )
        if scan.relative_path in items_by_path
        else scan
        for scan in discover_source_files(library_dir)
    )
    registered = sync_source_registry(database_path, scans)

    adapters: dict[str, LegacyMdictSourceAdapter] = {}
    legacy_source_ids: dict[str, str] = {}
    by_relative_path = {source.relative_path: source for source in registered}
    for relative_path, item in items_by_path.items():
        registered_source = by_relative_path.get(relative_path)
        if registered_source is not None and registered_source.available:
            adapters[registered_source.source_id] = LegacyMdictSourceAdapter(item)
            legacy_uuid = item.get("uuid")
            if legacy_uuid:
                legacy_source_ids[str(legacy_uuid)] = registered_source.source_id

    # A present file without a usable adapter stays visible as unavailable.
    for source in registered:
        if source.available and source.source_id not in adapters:
            update_source_availability(
                database_path,
                source.source_id,
                available=False,
                reason="source_adapter_unavailable",
            )
    registered = list_registered_sources(database_path)
    catalog = SourceCatalog.from_registered_sources(registered, adapters)
    metadata_provider = ECDICTMetadataProvider(config.get("WFD_DB"))
    lookup_service = LookupService(
        catalog,
        citation_signing_key=settings.citation_signing_key,
        asset_signing_key=settings.asset_signing_key,
        history_recorder=lambda word: _record_history(database_path, word),
    )
    suggestion_service = SuggestionService(catalog)
    metadata_service = MetadataService(metadata_provider)

    def update_source(
        source_id: str, enabled: bool | None, order: int | None
    ) -> tuple[bool, SourceRecord]:
        changed, registered_source = update_source_preferences(
            database_path,
            source_id,
            enabled=enabled,
            sort_order=order,
        )
        updated = _domain_source(registered_source)
        catalog.replace_source(updated)
        return changed, updated

    def resolve_citation(target):
        if target.headword is None or target.record_ordinal is None:
            return None
        try:
            result = lookup_service.lookup(
                target.headword,
                source_ids=[target.source_id],
                representations=("text",),
            )
        except Exception:
            return None
        entry = next(
            (entry for entry in result.entries if entry.entry_id == target.entry_id), None
        )
        if entry is None:
            return None
        block = None
        if target.block_id is not None:
            matching = next(
                (
                    item
                    for item in entry.text_blocks
                    if item.block_id == target.block_id
                ),
                None,
            )
            if matching is None:
                return None
            block = {
                "block_id": matching.block_id,
                "order": matching.order,
                "text": matching.text,
                "citation": {
                    "uri": matching.citation.uri,
                    "token": matching.citation.token,
                },
            }
        source = next(
            item for item in catalog.list_sources() if item.source_id == target.source_id
        )
        return {
            "source": {
                "source_id": source.source_id,
                "revision": source.revision,
                "title": source.title,
            },
            "entry_id": entry.entry_id,
            "headword": entry.headword,
            "representation_version": target.representation_version,
            "text_block": block,
        }

    def load_asset(target):
        adapter = catalog.adapter(target.source_id)
        if adapter is None or not hasattr(adapter, "read_resource"):
            return None
        return adapter.read_resource(target.resource_path)

    def status():
        sources = catalog.list_sources()
        return {
            "state": "ready",
            "sources": {
                "available": sum(source.available for source in sources),
                "unavailable": sum(not source.available for source in sources),
                "scan_state": "idle",
            },
            "storage": {
                "library_readable": library_dir.is_dir(),
                "data_writable": os.access(database_path.parent, os.W_OK),
                "index_writable": os.access(
                    Path(os.fspath(config["MDICT_INDEX_DIR"])), os.W_OK
                ),
            },
            "capabilities": {
                "metadata": metadata_provider.available,
                "external_cache": bool(os.environ.get("REDIS_URL")),
            },
        }

    return V2Dependencies(
        catalog=catalog,
        lookup_service=lookup_service,
        suggestion_service=suggestion_service,
        metadata_service=metadata_service,
        source_updater=update_source,
        citation_resolver=resolve_citation,
        asset_loader=load_asset,
        readiness=lambda: True,
        status_provider=status,
        legacy_source_ids=legacy_source_ids,
    )
