"""Transactional, versioned application-database migrations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sqlite3
import tempfile


CURRENT_SCHEMA_VERSION = 1


class DatabaseMigrationError(RuntimeError):
    """Raised when an application database cannot be migrated safely."""


class LegacyDatabaseAdoptionError(RuntimeError):
    """Raised when a legacy database cannot be adopted without data risk."""


@dataclass(frozen=True, slots=True)
class LegacyAdoptionResult:
    status: str
    destination: Path


def _migration_001_foundation(connection: sqlite3.Connection) -> None:
    statements = (
        """CREATE TABLE IF NOT EXISTS history(
            word TEXT PRIMARY KEY,
            count INTEGER NOT NULL,
            last_time DATETIME
        )""",
        """CREATE TABLE IF NOT EXISTS setting(
            name TEXT PRIMARY KEY,
            value TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS wordbook(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS wordbook_entry(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wordbook_id INTEGER NOT NULL,
            word TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(wordbook_id) REFERENCES wordbook(id) ON DELETE CASCADE
        )""",
        "CREATE INDEX IF NOT EXISTS idx_wordbook_entry_word ON wordbook_entry(word)",
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_wordbook_entry_unique
            ON wordbook_entry(wordbook_id, word)""",
        """CREATE TABLE IF NOT EXISTS source_registry(
            source_id TEXT PRIMARY KEY,
            revision TEXT NOT NULL,
            relative_path TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
            sort_order INTEGER NOT NULL DEFAULT 0 CHECK(sort_order >= 0),
            available INTEGER NOT NULL DEFAULT 1 CHECK(available IN (0, 1)),
            unavailable_reason TEXT,
            legacy_uuid TEXT UNIQUE
        )""",
        """CREATE INDEX IF NOT EXISTS idx_source_registry_revision
            ON source_registry(revision)""",
        """CREATE INDEX IF NOT EXISTS idx_source_registry_order
            ON source_registry(sort_order, source_id)""",
        """CREATE TABLE IF NOT EXISTS migration_event(
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('started', 'completed', 'failed')),
            details_json TEXT NOT NULL DEFAULT '{}',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""",
    )
    for statement in statements:
        connection.execute(statement)


MIGRATIONS: tuple[tuple[int, Callable[[sqlite3.Connection], None]], ...] = (
    (1, _migration_001_foundation),
)


def migrate_application_database(database_path: str | os.PathLike[str]) -> int:
    """Apply every pending migration atomically and return the schema version."""

    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migration(
                version INTEGER PRIMARY KEY,
                applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        applied_versions = {
            row[0] for row in connection.execute("SELECT version FROM schema_migration")
        }
        future_versions = {
            version for version in applied_versions if version > CURRENT_SCHEMA_VERSION
        }
        if future_versions:
            raise DatabaseMigrationError(
                "database schema is newer than this application supports"
            )

        for version, migration in MIGRATIONS:
            if version in applied_versions:
                continue
            migration(connection)
            connection.execute(
                "INSERT INTO schema_migration(version) VALUES (?)", (version,)
            )

        connection.commit()
        return CURRENT_SCHEMA_VERSION
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _integrity_check(database_path: Path, *, read_only: bool) -> None:
    uri = database_path.resolve(strict=True).as_uri()
    if read_only:
        uri = f"{uri}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        rows = connection.execute("PRAGMA integrity_check").fetchall()
    finally:
        connection.close()
    if rows != [("ok",)]:
        raise LegacyDatabaseAdoptionError("legacy database integrity check failed")


def _copy_sqlite_database(source: Path, destination: Path) -> None:
    source_uri = f"{source.resolve(strict=True).as_uri()}?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as source_connection:
        with sqlite3.connect(destination) as destination_connection:
            source_connection.backup(destination_connection)


def _record_adoption_event(database_path: Path) -> None:
    details = json.dumps(
        {
            "legacy_filename": "flask_mdict.db",
            "destination_filename": database_path.name,
            "schema_version": CURRENT_SCHEMA_VERSION,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO migration_event(event_type, status, details_json)
            VALUES ('legacy_database_adoption', 'completed', ?)
            """,
            (details,),
        )


def adopt_legacy_database(
    legacy_database: str | os.PathLike[str],
    destination_database: str | os.PathLike[str],
) -> LegacyAdoptionResult:
    """Adopt legacy state through a checked temporary database.

    The legacy file is opened read-only and remains untouched. The destination
    is authoritative when already present. A small lock file serializes startup
    adopters so the final atomic replacement cannot overwrite another result.
    """

    source = Path(legacy_database)
    destination = Path(destination_database)
    if destination.exists():
        return LegacyAdoptionResult("destination_exists", destination)
    if not source.is_file():
        return LegacyAdoptionResult("legacy_absent", destination)

    destination.parent.mkdir(parents=True, exist_ok=True)
    lock_path = destination.with_name(f".{destination.name}.adoption.lock")
    temporary_path: Path | None = None
    lock_descriptor: int | None = None
    try:
        try:
            lock_descriptor = os.open(
                lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
            )
        except FileExistsError as error:
            raise LegacyDatabaseAdoptionError(
                "another legacy database adoption is already in progress"
            ) from error

        if destination.exists():
            return LegacyAdoptionResult("destination_exists", destination)

        _integrity_check(source, read_only=True)
        temporary_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        os.close(temporary_descriptor)
        temporary_path = Path(temporary_name)
        _copy_sqlite_database(source, temporary_path)
        migrate_application_database(temporary_path)
        _record_adoption_event(temporary_path)
        _integrity_check(temporary_path, read_only=False)

        with temporary_path.open("rb") as temporary_file:
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, destination)
        temporary_path = None
        directory_descriptor = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        return LegacyAdoptionResult("adopted", destination)
    except LegacyDatabaseAdoptionError:
        raise
    except Exception as error:
        raise LegacyDatabaseAdoptionError(
            "legacy database adoption failed without changing the source"
        ) from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        if lock_descriptor is not None:
            os.close(lock_descriptor)
            lock_path.unlink(missing_ok=True)
