from __future__ import annotations

from pathlib import Path

from application_database import migrate_application_database
from citations import decode_citation_token
from private_service import load_private_service_settings
from resource_capabilities import ResourceTarget
from runtime_v2 import build_v2_dependencies


TOKEN = "private-test-token-0123456789abcdef"


class FakeLegacyQuery:
    def __init__(self) -> None:
        self.records = {
            "right": ("<p>Correct as a fact.</p>",),
            "rigid": ("<p>Not flexible.</p>",),
        }

    def mdx_lookup(self, _connection, query: str, ignorecase: bool = True):
        return self.records.get(query, ())

    def get_mdx_keys(self, _connection, prefix: str):
        return sorted(key for key in self.records if key.startswith(prefix))

    def mdd_lookup(self, _connection, resource: str, ignorecase: bool = True):
        if resource == "\\images\\packed.png":
            return b"packed-png"
        return None


def test_runtime_composes_existing_parser_into_v2_services(tmp_path: Path) -> None:
    library = tmp_path / "library"
    data = tmp_path / "data"
    indexes = data / "index"
    library.mkdir()
    indexes.mkdir(parents=True)
    mdx_file = library / "fixture.mdx"
    mdx_file.write_bytes(b"synthetic mdx bytes")
    (library / "images").mkdir()
    (library / "images" / "local.png").write_bytes(b"local-png")
    database = data / "mdict-live.db"
    migrate_application_database(database)
    query = FakeLegacyQuery()
    legacy_item = {
        "title": "Parser Fixture Dictionary",
        "uuid": "LEGACY-UUID",
        "root_path": str(library),
        "source_path": str(mdx_file),
        "database_path": None,
        "query": query,
        "type": "mdict",
        "enable": True,
    }
    settings = load_private_service_settings({"MDICT_LIVE_TOKEN": TOKEN})
    dependencies = build_v2_dependencies(
        {
            "MDICT_LIBRARY_DIR": str(library),
            "MDICT_DATA_DIR": str(data),
            "MDICT_INDEX_DIR": str(indexes),
            "APP_DB": str(database),
            "WFD_DB": None,
        },
        {"LEGACY-UUID": legacy_item},
        settings,
    )
    try:
        sources = dependencies.catalog.list_sources()
        lookup = dependencies.lookup_service.lookup("right")
        suggestions = dependencies.suggestion_service.suggest("ri")
        target = decode_citation_token(
            lookup.entries[0].text_blocks[0].citation.token,
            settings.citation_signing_key,
        )
        resolved = dependencies.citation_resolver(target)
        local_asset = dependencies.asset_loader(
            ResourceTarget(
                sources[0].source_id,
                sources[0].revision,
                "images/local.png",
                2_000_000_000,
            )
        )
        packed_asset = dependencies.asset_loader(
            ResourceTarget(
                sources[0].source_id,
                sources[0].revision,
                "images/packed.png",
                2_000_000_000,
            )
        )
        changed, updated = dependencies.source_updater(
            sources[0].source_id, False, 5
        )
        status = dependencies.status_provider()
    finally:
        dependencies.lookup_service.close()

    assert len(sources) == 1
    assert sources[0].title == "Parser Fixture Dictionary"
    assert [block.text for block in lookup.entries[0].text_blocks] == [
        "Correct as a fact."
    ]
    assert [item.headword for item in suggestions.suggestions] == ["right", "rigid"]
    assert resolved["text_block"]["text"] == "Correct as a fact."
    assert local_asset == b"local-png"
    assert packed_asset == b"packed-png"
    assert changed is True
    assert updated.enabled is False
    assert updated.sort_order == 5
    assert dependencies.catalog.list_sources()[0] == updated
    assert status["sources"] == {"available": 1, "unavailable": 0, "scan_state": "idle"}


def test_runtime_reports_present_file_without_parser_adapter_as_unavailable(
    tmp_path: Path,
) -> None:
    library = tmp_path / "library"
    data = tmp_path / "data"
    indexes = data / "index"
    library.mkdir()
    indexes.mkdir(parents=True)
    (library / "unreadable-by-parser.mdx").write_bytes(b"synthetic")
    database = data / "mdict-live.db"
    migrate_application_database(database)
    settings = load_private_service_settings({"MDICT_LIVE_TOKEN": TOKEN})

    dependencies = build_v2_dependencies(
        {
            "MDICT_LIBRARY_DIR": str(library),
            "MDICT_DATA_DIR": str(data),
            "MDICT_INDEX_DIR": str(indexes),
            "APP_DB": str(database),
            "WFD_DB": None,
        },
        {},
        settings,
    )
    try:
        source = dependencies.catalog.list_sources()[0]
    finally:
        dependencies.lookup_service.close()

    assert source.available is False
    assert source.unavailable_reason == "source_adapter_unavailable"
