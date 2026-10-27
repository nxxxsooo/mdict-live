from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from flask import Blueprint, Flask
import pytest

from citations import derive_purpose_key
from domain import MetadataDataset, MetadataRecord, SourceRecord
from flask_mdict import api as legacy_api
from lookup_services import LookupService, MetadataService, SourceCatalog, SuggestionService
from tests.support.source_fakes import FakeDictionarySource, FakeEntryRecord
from v2_api import V2Dependencies


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "legacy-api"
MANIFEST = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))


class FakeLegacyQuery:
    def mdx_lookup(self, _connection, word: str, ignorecase: bool = True):
        if word == "right":
            return ["<p>Correct as a fact.</p>"]
        return []

    def get_mdx_keys(self, _connection, query: str):
        return [word for word in ("right", "rigid", "other") if word.startswith(query)]


def create_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE wordbook(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE wordbook_entry(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wordbook_id INTEGER NOT NULL,
            word TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE UNIQUE INDEX idx_wordbook_entry_unique
            ON wordbook_entry(wordbook_id, word);
        """
    )
    return connection


def create_metadata_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE ecdict(
            word TEXT PRIMARY KEY,
            phonetic TEXT,
            definition TEXT,
            translation TEXT,
            oxford INTEGER,
            collins INTEGER,
            tag TEXT,
            bnc INTEGER,
            frq INTEGER,
            exchange TEXT
        )
        """
    )
    connection.execute(
        """
        INSERT INTO ecdict VALUES(
            'right', 'raɪt', 'correct or suitable', '正确的；合适的',
            1, 3, 'cet4 core', 123, 492, 'p:righted/3:rights/'
        )
        """
    )
    connection.commit()
    return connection


def build_legacy_client(
    monkeypatch: pytest.MonkeyPatch, setup: str, *, shared: bool
):
    query = FakeLegacyQuery()
    dictionaries = {
        "LEGACY-UUID": {
            "uuid": "LEGACY-UUID",
            "title": "Fixture Dictionary",
            "logo": "logo.ico",
            "type": "mdict",
            "enable": True,
            "query": query,
        }
    }
    application_database = create_database()
    metadata_database = create_metadata_database()
    if setup in {"wordbook", "wordbook_entry"}:
        application_database.execute(
            """
            INSERT INTO wordbook(id, name, created_at)
            VALUES (1, 'Fixture words', '2026-08-04 09:00:00')
            """
        )
    if setup == "wordbook_entry":
        application_database.execute(
            """
            INSERT INTO wordbook_entry(id, wordbook_id, word, created_at)
            VALUES (1, 1, 'right', '2026-08-04 09:05:00')
            """
        )
    application_database.commit()
    history = (
        [{"word": "right", "count": 2, "last_time": "2026-08-04 09:00:00"}]
        if setup == "history"
        else []
    )

    monkeypatch.setattr(legacy_api, "get_mdict", lambda: dictionaries)
    monkeypatch.setattr(legacy_api, "get_cache", lambda: None)
    monkeypatch.setattr(
        legacy_api,
        "get_db",
        lambda name: metadata_database if name == "wfd_db" else application_database,
    )
    monkeypatch.setattr(legacy_api.helper, "get_history", lambda max_num=500: history[:max_num])
    monkeypatch.setattr(legacy_api.helper, "add_history", lambda word: None)
    monkeypatch.setattr(legacy_api.helper, "clear_history", history.clear)
    monkeypatch.setattr(legacy_api.helper, "mdict_enable", lambda *_args: None)

    app = Flask(f"legacy-golden-{setup}-{id(application_database)}")
    resources = Blueprint("mdict", __name__)

    @resources.get("/uuid_<uuid>/resource/<path:resource>")
    def query_resource(uuid: str, resource: str):
        return f"{uuid}:{resource}"

    app.register_blueprint(resources, url_prefix="/mdict")
    app.register_blueprint(legacy_api.api, url_prefix="/api")
    lookup_service = None
    if shared:
        shared_source = FakeDictionarySource(
            "src_fixture_primary",
            "rev_fixture_0001",
            "Fixture Dictionary",
            records={
                "right": (FakeEntryRecord("right", "<p>Correct as a fact.</p>"),),
                "rigid": (FakeEntryRecord("rigid", "<p>Rigid.</p>"),),
            },
        )
        source_record = SourceRecord(
            shared_source.source_id,
            shared_source.revision,
            shared_source.title,
            True,
            0,
        )
        catalog = SourceCatalog(
            (source_record,), {shared_source.source_id: shared_source}
        )
        signing_secret = b"legacy-shared-test-secret-at-least-32-bytes"
        lookup_service = LookupService(
            catalog,
            citation_signing_key=derive_purpose_key(signing_secret, "citations"),
            asset_signing_key=derive_purpose_key(signing_secret, "assets"),
        )

        class SharedMetadataProvider:
            available = True
            unavailable_reason = None

            def lookup(self, word: str):
                if word != "right":
                    return ()
                return (
                    MetadataRecord(
                        query=word,
                        dataset=MetadataDataset("ecdict", "ECDICT lexical metadata"),
                        phonetic="raɪt",
                        tags=("cet4", "core"),
                        inflections=(("past_tense", "righted"), ("third_person", "rights")),
                        definition="correct or suitable",
                        translation="正确的；合适的",
                        legacy_fields=(
                            ("oxford", 1),
                            ("collins", 3),
                            ("bnc", 123),
                            ("frq", 492),
                        ),
                    ),
                )

        dependencies = V2Dependencies(
            catalog,
            lookup_service,
            SuggestionService(catalog),
            MetadataService(SharedMetadataProvider()),
            legacy_source_ids={"LEGACY-UUID": shared_source.source_id},
        )

        def shared_update(source_id: str, enabled: bool | None, order: int | None):
            current = dependencies.catalog.list_sources()[0]
            updated = SourceRecord(
                current.source_id,
                current.revision,
                current.title,
                current.enabled if enabled is None else enabled,
                current.sort_order if order is None else order,
            )
            dependencies.catalog.replace_source(updated)
            return updated != current, updated

        dependencies.source_updater = shared_update
        app.extensions["mdict_v2_dependencies"] = dependencies
    return app.test_client(), application_database, metadata_database, lookup_service


@pytest.mark.parametrize("scenario", MANIFEST, ids=lambda item: item["file"])
@pytest.mark.parametrize("shared", (False, True), ids=("legacy-path", "shared-path"))
def test_current_spa_legacy_endpoint_matches_golden(
    scenario: dict, shared: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, application_database, metadata_database, lookup_service = build_legacy_client(
        monkeypatch, scenario["setup"], shared=shared
    )
    try:
        response = client.open(
            scenario["path"],
            method=scenario["method"],
            json=scenario.get("json"),
        )
    finally:
        if lookup_service is not None:
            lookup_service.close()
        application_database.close()
        metadata_database.close()

    expected = json.loads((FIXTURE_DIR / scenario["file"]).read_text(encoding="utf-8"))
    assert response.status_code == 200
    assert response.get_json() == expected


def test_manifest_covers_every_spa_api_operation() -> None:
    operations = {(item["method"], item["path"].split("?", 1)[0]) for item in MANIFEST}

    assert operations == {
        ("GET", "/api/dicts"),
        ("GET", "/api/dicts/LEGACY-UUID/lookup/right"),
        ("GET", "/api/dicts/LEGACY-UUID/lookup/missing"),
        ("GET", "/api/lookup/right"),
        ("GET", "/api/lookup/missing"),
        ("GET", "/api/suggest/ri"),
        ("GET", "/api/history"),
        ("POST", "/api/history/clear"),
        ("GET", "/api/meta/right"),
        ("POST", "/api/dicts/LEGACY-UUID/toggle"),
        ("GET", "/api/wordbooks"),
        ("POST", "/api/wordbooks"),
        ("DELETE", "/api/wordbooks/1"),
        ("PUT", "/api/wordbooks/1"),
        ("GET", "/api/wordbooks/1/entries"),
        ("POST", "/api/wordbooks/1/entries"),
        ("DELETE", "/api/wordbooks/1/entries/1"),
        ("GET", "/api/wordbooks/entries"),
    }
