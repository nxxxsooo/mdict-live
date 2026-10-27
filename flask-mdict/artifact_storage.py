"""Keep generated dictionary artifacts out of an explicit v2 corpus."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sqlite3
import tempfile


@dataclass(frozen=True, slots=True)
class SourceArtifactPaths:
    index_dir: Path | None
    description_file: Path


@dataclass(frozen=True, slots=True)
class LegacyIndexAdoptionResult:
    copied: tuple[str, ...]
    reused: tuple[str, ...]
    rejected: tuple[str, ...]


def resolve_source_artifact_paths(
    *,
    source_root: str | os.PathLike[str],
    source_name: str,
    source_uuid: str,
    index_root: str | os.PathLike[str] | None,
    description_root: str | os.PathLike[str] | None,
) -> SourceArtifactPaths:
    """Resolve legacy-compatible or explicitly separated artifact paths."""

    source_directory = Path(source_root)
    if index_root is None:
        index_dir = None
    else:
        index_dir = Path(index_root) / source_uuid

    if description_root is None:
        description_file = source_directory / f"about_{source_name}.html"
    else:
        description_file = Path(description_root) / source_uuid / "about.html"
    return SourceArtifactPaths(index_dir=index_dir, description_file=description_file)


def persist_description(description_file: Path, content: str) -> None:
    """Persist a derived description once at its resolved writable location."""

    if description_file.exists():
        return
    description_file.parent.mkdir(parents=True, exist_ok=True)
    description_file.write_text(content, encoding="utf-8")


def _legacy_index_candidates(mdx_file: Path) -> tuple[Path, ...]:
    source_name = mdx_file.stem.casefold()
    mdx_index_name = f"{mdx_file.name.casefold()}.db"
    return tuple(
        sorted(
            (
                candidate
                for candidate in mdx_file.parent.iterdir()
                if candidate.is_file()
                and (
                    candidate.name.casefold() == mdx_index_name
                    or (
                        candidate.name.casefold().startswith(f"{source_name}.")
                        and candidate.name.casefold().endswith(".mdd.db")
                    )
                )
            ),
            key=lambda path: (path.name.casefold(), path.name),
        )
    )


def _validate_reusable_index(index_file: Path) -> None:
    uri = f"{index_file.resolve(strict=True).as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise sqlite3.DatabaseError("index integrity check failed")
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if not {"MDX_INDEX", "META"} <= tables:
            raise sqlite3.DatabaseError("index schema is incomplete")
        if connection.execute(
            "SELECT 1 FROM META WHERE key = 'm_time' LIMIT 1"
        ).fetchone() is None:
            raise sqlite3.DatabaseError("index modification time is missing")


def _copy_sqlite_index(source: Path, destination: Path) -> None:
    source_uri = f"{source.resolve(strict=True).as_uri()}?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as source_connection:
        with sqlite3.connect(destination) as destination_connection:
            source_connection.backup(destination_connection)


def adopt_legacy_index_files(
    mdx_file: str | os.PathLike[str], destination_index_dir: Path | None
) -> LegacyIndexAdoptionResult:
    """Copy reusable legacy indexes out of the corpus; reject failures safely."""

    if destination_index_dir is None:
        return LegacyIndexAdoptionResult((), (), ())
    destination_index_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    reused: list[str] = []
    rejected: list[str] = []
    for source in _legacy_index_candidates(Path(mdx_file)):
        destination = destination_index_dir / source.name
        if destination.exists():
            reused.append(source.name)
            continue
        temporary_path: Path | None = None
        try:
            _validate_reusable_index(source)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{source.name}.", suffix=".tmp", dir=destination_index_dir
            )
            os.close(descriptor)
            temporary_path = Path(temporary_name)
            _copy_sqlite_index(source, temporary_path)
            _validate_reusable_index(temporary_path)
            os.replace(temporary_path, destination)
            temporary_path = None
            copied.append(source.name)
        except (OSError, sqlite3.DatabaseError):
            rejected.append(source.name)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
    return LegacyIndexAdoptionResult(
        tuple(copied), tuple(reused), tuple(rejected)
    )
