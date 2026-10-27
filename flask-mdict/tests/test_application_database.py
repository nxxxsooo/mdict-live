from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from application_database import (
    CURRENT_SCHEMA_VERSION,
    DatabaseMigrationError,
    LegacyDatabaseAdoptionError,
    adopt_legacy_database,
    migrate_application_database,
)


EXPECTED_TABLES = {
    "history",
    "migration_event",
    "schema_migration",
    "setting",
    "source_registry",
    "wordbook",
    "wordbook_entry",
}


def table_names(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        return {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }


def test_new_database_is_created_at_the_current_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "nested" / "mdict-live.db"

    version = migrate_application_database(database_path)

    assert version == CURRENT_SCHEMA_VERSION
    assert EXPECTED_TABLES <= table_names(database_path)
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT version FROM schema_migration").fetchall() == [
            (CURRENT_SCHEMA_VERSION,)
        ]


def test_migration_preserves_existing_legacy_rows_and_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE history(word TEXT PRIMARY KEY, count INT, last_time DATETIME)"
        )
        connection.execute(
            "CREATE TABLE setting(name TEXT PRIMARY KEY, value TEXT)"
        )
        connection.execute(
            "INSERT INTO history(word, count, last_time) VALUES ('right', 4, '2026-08-04')"
        )
        connection.execute("INSERT INTO setting(name, value) VALUES ('theme', 'dark')")

    migrate_application_database(database_path)
    migrate_application_database(database_path)

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT word, count FROM history").fetchall() == [
            ("right", 4)
        ]
        assert connection.execute("SELECT name, value FROM setting").fetchall() == [
            ("theme", "dark")
        ]
        assert connection.execute("SELECT COUNT(*) FROM schema_migration").fetchone() == (
            1,
        )


def test_source_registry_records_stable_identity_and_ordering_fields(tmp_path: Path) -> None:
    database_path = tmp_path / "mdict-live.db"
    migrate_application_database(database_path)

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(source_registry)")
        }

    assert {
        "source_id",
        "revision",
        "relative_path",
        "title",
        "created_at",
        "last_seen_at",
        "enabled",
        "sort_order",
        "available",
        "unavailable_reason",
        "legacy_uuid",
    } <= columns


def test_wordbook_entries_retain_foreign_key_cascade(tmp_path: Path) -> None:
    database_path = tmp_path / "mdict-live.db"
    migrate_application_database(database_path)

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        wordbook_id = connection.execute(
            "INSERT INTO wordbook(name) VALUES ('Review')"
        ).lastrowid
        connection.execute(
            "INSERT INTO wordbook_entry(wordbook_id, word) VALUES (?, 'right')",
            (wordbook_id,),
        )
        connection.execute("DELETE FROM wordbook WHERE id = ?", (wordbook_id,))
        assert connection.execute("SELECT COUNT(*) FROM wordbook_entry").fetchone() == (
            0,
        )


def test_newer_database_version_fails_without_applying_changes(tmp_path: Path) -> None:
    database_path = tmp_path / "future.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE schema_migration(version INTEGER PRIMARY KEY, applied_at DATETIME)"
        )
        connection.execute(
            "INSERT INTO schema_migration(version, applied_at) VALUES (?, CURRENT_TIMESTAMP)",
            (CURRENT_SCHEMA_VERSION + 1,),
        )

    with pytest.raises(DatabaseMigrationError, match="newer"):
        migrate_application_database(database_path)

    assert "source_registry" not in table_names(database_path)


def create_legacy_database(database_path: Path, word: str = "right") -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE history(word TEXT PRIMARY KEY, count INT, last_time DATETIME)"
        )
        connection.execute(
            "CREATE TABLE setting(name TEXT PRIMARY KEY, value TEXT)"
        )
        connection.execute(
            "INSERT INTO history(word, count, last_time) VALUES (?, 2, '2026-08-04')",
            (word,),
        )


def test_legacy_database_is_adopted_without_modifying_source(tmp_path: Path) -> None:
    legacy_database = tmp_path / "library" / "flask_mdict.db"
    destination = tmp_path / "data" / "mdict-live.db"
    legacy_database.parent.mkdir()
    create_legacy_database(legacy_database)
    source_bytes = legacy_database.read_bytes()

    result = adopt_legacy_database(legacy_database, destination)

    assert result.status == "adopted"
    assert legacy_database.read_bytes() == source_bytes
    assert EXPECTED_TABLES <= table_names(destination)
    with sqlite3.connect(destination) as connection:
        assert connection.execute("SELECT word, count FROM history").fetchall() == [
            ("right", 2)
        ]
        event = connection.execute(
            "SELECT event_type, status, details_json FROM migration_event"
        ).fetchone()
    assert event[0:2] == ("legacy_database_adoption", "completed")
    assert '"legacy_filename":"flask_mdict.db"' in event[2]
    assert str(tmp_path) not in event[2]


def test_existing_destination_is_authoritative_and_is_not_merged(tmp_path: Path) -> None:
    legacy_database = tmp_path / "library" / "flask_mdict.db"
    destination = tmp_path / "data" / "mdict-live.db"
    legacy_database.parent.mkdir()
    destination.parent.mkdir()
    create_legacy_database(legacy_database, word="legacy")
    create_legacy_database(destination, word="authoritative")

    result = adopt_legacy_database(legacy_database, destination)

    assert result.status == "destination_exists"
    with sqlite3.connect(destination) as connection:
        assert connection.execute("SELECT word FROM history").fetchall() == [
            ("authoritative",)
        ]


def test_absent_legacy_database_does_not_create_destination(tmp_path: Path) -> None:
    destination = tmp_path / "data" / "mdict-live.db"

    result = adopt_legacy_database(
        tmp_path / "library" / "flask_mdict.db", destination
    )

    assert result.status == "legacy_absent"
    assert not destination.exists()


def test_corrupt_legacy_database_rolls_back_all_destination_artifacts(
    tmp_path: Path,
) -> None:
    legacy_database = tmp_path / "library" / "flask_mdict.db"
    destination = tmp_path / "data" / "mdict-live.db"
    legacy_database.parent.mkdir()
    legacy_database.write_bytes(b"not a sqlite database")

    with pytest.raises(LegacyDatabaseAdoptionError, match="adoption failed"):
        adopt_legacy_database(legacy_database, destination)

    assert legacy_database.read_bytes() == b"not a sqlite database"
    assert not destination.exists()
    assert not list(destination.parent.glob(".*.tmp"))
    assert not list(destination.parent.glob("*.lock"))


def test_failed_schema_migration_removes_temporary_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy_database = tmp_path / "library" / "flask_mdict.db"
    destination = tmp_path / "data" / "mdict-live.db"
    legacy_database.parent.mkdir()
    create_legacy_database(legacy_database)

    def fail_migration(_database_path: Path) -> int:
        raise DatabaseMigrationError("synthetic migration failure")

    monkeypatch.setattr("application_database.migrate_application_database", fail_migration)

    with pytest.raises(LegacyDatabaseAdoptionError, match="adoption failed"):
        adopt_legacy_database(legacy_database, destination)

    assert legacy_database.exists()
    assert not destination.exists()
    assert not list(destination.parent.glob(".*.tmp"))
    assert not list(destination.parent.glob("*.lock"))
