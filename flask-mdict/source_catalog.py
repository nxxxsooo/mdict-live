"""Source discovery, content revisions, and stable registry matching."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import datetime as dt
import hashlib
import os
from pathlib import Path
import secrets
import sqlite3
import unicodedata
import uuid


HASH_CHUNK_BYTES = 1024 * 1024
REVISION_DOMAIN = b"mdict-live-source-revision-v1\0"


@dataclass(frozen=True, slots=True)
class ScannedSource:
    relative_path: str
    title: str
    revision: str
    legacy_uuid: str
    mdx_path: Path
    mdd_paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class RegisteredSource:
    source_id: str
    revision: str
    relative_path: str
    title: str
    enabled: bool
    sort_order: int
    available: bool
    unavailable_reason: str | None
    legacy_uuid: str | None


def normalize_relative_path(path: Path) -> str:
    return unicodedata.normalize("NFC", path.as_posix())


def stream_file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        while chunk := source_file.read(HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_digest(records: Iterable[tuple[str, str, str]]) -> str:
    digest = hashlib.sha256(REVISION_DOMAIN)
    for kind, relative_name, content_digest in records:
        for value in (kind, relative_name, content_digest):
            encoded = value.encode("utf-8")
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
    return f"rev_{digest.hexdigest()}"


def _legacy_uuid(mdx_path: Path) -> str:
    normalized_path = os.fspath(mdx_path.resolve(strict=False)).replace("\\", "/")
    return str(uuid.uuid3(uuid.NAMESPACE_URL, normalized_path)).upper()


def _associated_mdds(mdx_path: Path, sibling_files: Iterable[Path]) -> tuple[Path, ...]:
    stem = mdx_path.stem.casefold()
    matches = []
    for candidate in sibling_files:
        candidate_name = candidate.name.casefold()
        if not candidate.is_file() or not candidate_name.endswith(".mdd"):
            continue
        if candidate_name == f"{stem}.mdd" or (
            candidate_name.startswith(f"{stem}.") and candidate_name.endswith(".mdd")
        ):
            matches.append(candidate)
    return tuple(
        sorted(
            matches,
            key=lambda path: (
                normalize_relative_path(path.relative_to(mdx_path.parent)).casefold(),
                normalize_relative_path(path.relative_to(mdx_path.parent)),
            ),
        )
    )


def discover_source_files(
    library_dir: str | os.PathLike[str],
    *,
    file_digest: Callable[[Path], str] = stream_file_sha256,
) -> tuple[ScannedSource, ...]:
    """Hash every MDX source and its ordered MDD manifest for one scan cycle."""

    library = Path(library_dir).resolve(strict=False)
    digest_cache: dict[tuple[int, int, int, int, int], str] = {}

    def digest_once_per_scan(path: Path) -> str:
        stat = path.stat()
        signature = (
            stat.st_dev,
            stat.st_ino,
            stat.st_size,
            stat.st_mtime_ns,
            stat.st_ctime_ns,
        )
        if signature not in digest_cache:
            digest_cache[signature] = file_digest(path)
        return digest_cache[signature]

    mdx_paths = sorted(
        (
            path
            for path in library.rglob("*")
            if path.is_file() and path.suffix.casefold() == ".mdx"
        ),
        key=lambda path: (
            normalize_relative_path(path.relative_to(library)).casefold(),
            normalize_relative_path(path.relative_to(library)),
        ),
    )
    directory_files: dict[Path, tuple[Path, ...]] = {}
    scanned_sources = []
    for mdx_path in mdx_paths:
        siblings = directory_files.setdefault(
            mdx_path.parent, tuple(mdx_path.parent.iterdir())
        )
        mdd_paths = _associated_mdds(mdx_path, siblings)
        manifest_records = [("mdx", "", digest_once_per_scan(mdx_path))]
        manifest_records.extend(
            (
                "mdd",
                normalize_relative_path(mdd_path.relative_to(mdx_path.parent)),
                digest_once_per_scan(mdd_path),
            )
            for mdd_path in mdd_paths
        )
        scanned_sources.append(
            ScannedSource(
                relative_path=normalize_relative_path(mdx_path.relative_to(library)),
                title=mdx_path.stem,
                revision=_manifest_digest(manifest_records),
                legacy_uuid=_legacy_uuid(mdx_path),
                mdx_path=mdx_path,
                mdd_paths=mdd_paths,
            )
        )
    return tuple(scanned_sources)


def _new_source_id() -> str:
    return f"src_{secrets.token_urlsafe(18)}"


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _row_to_source(row: sqlite3.Row) -> RegisteredSource:
    return RegisteredSource(
        source_id=row["source_id"],
        revision=row["revision"],
        relative_path=row["relative_path"],
        title=row["title"],
        enabled=bool(row["enabled"]),
        sort_order=row["sort_order"],
        available=bool(row["available"]),
        unavailable_reason=row["unavailable_reason"],
        legacy_uuid=row["legacy_uuid"],
    )


def list_registered_sources(
    database_path: str | os.PathLike[str],
) -> tuple[RegisteredSource, ...]:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM source_registry ORDER BY sort_order, source_id"
        ).fetchall()
    return tuple(_row_to_source(row) for row in rows)


def resolve_legacy_source_alias(
    database_path: str | os.PathLike[str], legacy_uuid: str
) -> str | None:
    """Resolve the historical path-derived UUID without exposing its path."""

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT source_id FROM source_registry WHERE legacy_uuid = ?",
            (legacy_uuid.upper(),),
        ).fetchone()
    return row[0] if row else None


def sync_source_registry(
    database_path: str | os.PathLike[str],
    scanned_sources: Iterable[ScannedSource],
    *,
    source_id_factory: Callable[[], str] = _new_source_id,
    now: Callable[[], str] = _utc_now,
) -> tuple[RegisteredSource, ...]:
    """Match one complete scan to stable identities in a single transaction."""

    scans = sorted(
        scanned_sources,
        key=lambda item: (item.relative_path.casefold(), item.relative_path),
    )
    current_paths = {item.relative_path for item in scans}
    timestamp = now()
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing_rows = connection.execute("SELECT * FROM source_registry").fetchall()
        by_path = {row["relative_path"]: row for row in existing_rows}
        reserved_ids = {
            by_path[scan.relative_path]["source_id"]
            for scan in scans
            if scan.relative_path in by_path
        }
        move_candidates: dict[str, list[sqlite3.Row]] = {}
        for row in existing_rows:
            if row["relative_path"] in current_paths or row["source_id"] in reserved_ids:
                continue
            move_candidates.setdefault(row["revision"], []).append(row)
        for candidates in move_candidates.values():
            candidates.sort(key=lambda row: (row["sort_order"], row["source_id"]))

        seen_ids: set[str] = set()
        next_order = (
            max((row["sort_order"] for row in existing_rows), default=-1) + 1
        )
        for scan in scans:
            matched = by_path.get(scan.relative_path)
            if matched is None:
                candidates = move_candidates.get(scan.revision, [])
                matched = candidates.pop(0) if candidates else None

            if matched is None:
                source_id = source_id_factory()
                connection.execute(
                    """
                    INSERT INTO source_registry(
                        source_id, revision, relative_path, title, created_at,
                        last_seen_at, enabled, sort_order, available,
                        unavailable_reason, legacy_uuid
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, 1, NULL, ?)
                    """,
                    (
                        source_id,
                        scan.revision,
                        scan.relative_path,
                        scan.title,
                        timestamp,
                        timestamp,
                        next_order,
                        scan.legacy_uuid,
                    ),
                )
                next_order += 1
            else:
                source_id = matched["source_id"]
                connection.execute(
                    """
                    UPDATE source_registry
                    SET revision = ?, relative_path = ?, title = ?,
                        last_seen_at = ?, available = 1,
                        unavailable_reason = NULL
                    WHERE source_id = ?
                    """,
                    (
                        scan.revision,
                        scan.relative_path,
                        scan.title,
                        timestamp,
                        source_id,
                    ),
                )
            seen_ids.add(source_id)

        if seen_ids:
            placeholders = ",".join("?" for _ in seen_ids)
            connection.execute(
                f"""
                UPDATE source_registry
                SET available = 0, unavailable_reason = 'not_found'
                WHERE source_id NOT IN ({placeholders})
                """,
                tuple(sorted(seen_ids)),
            )
        else:
            connection.execute(
                "UPDATE source_registry SET available = 0, unavailable_reason = 'not_found'"
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return list_registered_sources(database_path)


def update_source_preferences(
    database_path: str | os.PathLike[str],
    source_id: str,
    *,
    enabled: bool | None = None,
    sort_order: int | None = None,
) -> tuple[bool, RegisteredSource]:
    if enabled is None and sort_order is None:
        raise ValueError("at least one source preference is required")
    if sort_order is not None and sort_order < 0:
        raise ValueError("sort_order must be non-negative")

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("BEGIN IMMEDIATE")
        current = connection.execute(
            "SELECT * FROM source_registry WHERE source_id = ?", (source_id,)
        ).fetchone()
        if current is None:
            raise KeyError(source_id)
        resulting_enabled = bool(current["enabled"]) if enabled is None else enabled
        resulting_order = current["sort_order"] if sort_order is None else sort_order
        changed = (
            bool(current["enabled"]) != resulting_enabled
            or current["sort_order"] != resulting_order
        )
        connection.execute(
            "UPDATE source_registry SET enabled = ?, sort_order = ? WHERE source_id = ?",
            (int(resulting_enabled), resulting_order, source_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    source = next(
        source
        for source in list_registered_sources(database_path)
        if source.source_id == source_id
    )
    return changed, source


def update_source_availability(
    database_path: str | os.PathLike[str],
    source_id: str,
    *,
    available: bool,
    reason: str | None = None,
) -> RegisteredSource:
    if available and reason is not None:
        raise ValueError("an available source cannot have an unavailable reason")
    if not available and not reason:
        raise ValueError("an unavailable source requires a reason")
    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            """
            UPDATE source_registry
            SET available = ?, unavailable_reason = ?
            WHERE source_id = ?
            """,
            (int(available), reason, source_id),
        )
        if cursor.rowcount != 1:
            raise KeyError(source_id)
    return next(
        source
        for source in list_registered_sources(database_path)
        if source.source_id == source_id
    )
