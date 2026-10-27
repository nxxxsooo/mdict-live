from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from application_database import migrate_application_database
from source_catalog import (
    discover_source_files,
    list_registered_sources,
    resolve_legacy_source_alias,
    sync_source_registry,
    update_source_availability,
    update_source_preferences,
)


def write_source(
    library: Path,
    relative_mdx: str,
    mdx_bytes: bytes,
    mdds: dict[str, bytes] | None = None,
) -> Path:
    mdx_path = library / relative_mdx
    mdx_path.parent.mkdir(parents=True, exist_ok=True)
    mdx_path.write_bytes(mdx_bytes)
    for name, content in (mdds or {}).items():
        (mdx_path.parent / name).write_bytes(content)
    return mdx_path


def source_ids() -> Iterator[str]:
    counter = 0
    while True:
        counter += 1
        yield f"src_test_{counter:04d}"


def test_every_discovery_cycle_rehashes_full_source_bytes(tmp_path: Path) -> None:
    library = tmp_path / "library"
    write_source(
        library,
        "Oxford/Fixture.MDX",
        b"mdx-content",
        {
            "fixture.MDD": b"primary-resource",
            "Fixture.2.mDd": b"secondary-resource",
            "unrelated.mdd": b"ignored",
        },
    )
    hashed_paths: list[str] = []

    def recording_digest(path: Path) -> str:
        hashed_paths.append(path.name)
        from source_catalog import stream_file_sha256

        return stream_file_sha256(path)

    first = discover_source_files(library, file_digest=recording_digest)
    first_calls = list(hashed_paths)
    hashed_paths.clear()
    second = discover_source_files(library, file_digest=recording_digest)

    assert first[0].revision == second[0].revision
    assert first_calls == ["Fixture.MDX", "Fixture.2.mDd", "fixture.MDD"]
    assert hashed_paths == first_calls
    assert [path.name for path in first[0].mdd_paths] == [
        "Fixture.2.mDd",
        "fixture.MDD",
    ]


def test_move_preserves_revision_but_updates_legacy_path_alias(tmp_path: Path) -> None:
    first_library = tmp_path / "first"
    second_library = tmp_path / "second"
    write_source(first_library, "old/fixture.mdx", b"same bytes")
    write_source(second_library, "new/renamed.mdx", b"same bytes")

    before = discover_source_files(first_library)[0]
    after = discover_source_files(second_library)[0]

    assert before.revision == after.revision
    assert before.legacy_uuid != after.legacy_uuid


def test_mdx_or_associated_mdd_change_advances_revision(tmp_path: Path) -> None:
    library = tmp_path / "library"
    mdx_path = write_source(
        library,
        "fixture.mdx",
        b"mdx-v1",
        {"fixture.mdd": b"mdd-v1"},
    )
    revision_v1 = discover_source_files(library)[0].revision

    mdx_path.write_bytes(b"mdx-v2")
    revision_v2 = discover_source_files(library)[0].revision
    (library / "fixture.mdd").write_bytes(b"mdd-v2")
    revision_v3 = discover_source_files(library)[0].revision

    assert len({revision_v1, revision_v2, revision_v3}) == 3


def test_simultaneous_identical_sources_share_revision_not_identity(tmp_path: Path) -> None:
    library = tmp_path / "library"
    write_source(library, "a/fixture.mdx", b"identical")
    write_source(library, "b/fixture-copy.mdx", b"identical")

    scans = discover_source_files(library)

    assert len(scans) == 2
    assert scans[0].revision == scans[1].revision
    assert scans[0].relative_path != scans[1].relative_path


def test_registry_preserves_id_for_unchanged_moved_and_updated_sources(
    tmp_path: Path,
) -> None:
    library = tmp_path / "library"
    database = tmp_path / "data" / "mdict-live.db"
    migrate_application_database(database)
    ids = source_ids()
    id_factory = lambda: next(ids)
    mdx_path = write_source(library, "old/fixture.mdx", b"v1")

    first = sync_source_registry(
        database, discover_source_files(library), source_id_factory=id_factory
    )[0]
    unchanged = sync_source_registry(
        database, discover_source_files(library), source_id_factory=id_factory
    )[0]
    moved_path = library / "new" / "fixture.mdx"
    moved_path.parent.mkdir()
    mdx_path.rename(moved_path)
    moved = sync_source_registry(
        database, discover_source_files(library), source_id_factory=id_factory
    )[0]
    moved_path.write_bytes(b"v2")
    updated = sync_source_registry(
        database, discover_source_files(library), source_id_factory=id_factory
    )[0]

    assert first.source_id == unchanged.source_id == moved.source_id == updated.source_id
    assert moved.relative_path == "new/fixture.mdx"
    assert first.revision == moved.revision
    assert updated.revision != moved.revision
    assert moved.legacy_uuid == first.legacy_uuid
    assert resolve_legacy_source_alias(database, first.legacy_uuid.lower()) == first.source_id


def test_move_and_change_in_one_scan_creates_conservative_new_identity(
    tmp_path: Path,
) -> None:
    library = tmp_path / "library"
    database = tmp_path / "data" / "mdict-live.db"
    migrate_application_database(database)
    ids = source_ids()
    id_factory = lambda: next(ids)
    old_path = write_source(library, "old/fixture.mdx", b"v1")
    old_source = sync_source_registry(
        database, discover_source_files(library), source_id_factory=id_factory
    )[0]

    new_path = library / "new" / "fixture.mdx"
    new_path.parent.mkdir()
    old_path.rename(new_path)
    new_path.write_bytes(b"v2")
    sources = sync_source_registry(
        database, discover_source_files(library), source_id_factory=id_factory
    )

    current = next(source for source in sources if source.available)
    missing = next(source for source in sources if not source.available)
    assert current.source_id != old_source.source_id
    assert missing.source_id == old_source.source_id
    assert missing.unavailable_reason == "not_found"


def test_simultaneous_duplicate_registry_rows_receive_distinct_ids(tmp_path: Path) -> None:
    library = tmp_path / "library"
    database = tmp_path / "data" / "mdict-live.db"
    migrate_application_database(database)
    write_source(library, "a/fixture.mdx", b"same")
    write_source(library, "b/fixture.mdx", b"same")
    ids = source_ids()

    sources = sync_source_registry(
        database,
        discover_source_files(library),
        source_id_factory=lambda: next(ids),
    )

    assert len({source.source_id for source in sources}) == 2
    assert len({source.revision for source in sources}) == 1


def test_preferences_and_unavailable_reason_survive_rescan(tmp_path: Path) -> None:
    library = tmp_path / "library"
    database = tmp_path / "data" / "mdict-live.db"
    migrate_application_database(database)
    write_source(library, "fixture.mdx", b"same")
    source = sync_source_registry(
        database,
        discover_source_files(library),
        source_id_factory=lambda: "src_test_primary",
    )[0]

    changed, preferred = update_source_preferences(
        database, source.source_id, enabled=False, sort_order=7
    )
    unavailable = update_source_availability(
        database,
        source.source_id,
        available=False,
        reason="parser_initialization_failed",
    )
    rescanned = sync_source_registry(database, discover_source_files(library))[0]

    assert changed is True
    assert preferred.enabled is False
    assert preferred.sort_order == 7
    assert unavailable.unavailable_reason == "parser_initialization_failed"
    assert rescanned.enabled is False
    assert rescanned.sort_order == 7
    assert rescanned.available is True
    assert rescanned.unavailable_reason is None


def test_preference_and_availability_validation_is_explicit(tmp_path: Path) -> None:
    database = tmp_path / "mdict-live.db"
    migrate_application_database(database)

    with pytest.raises(ValueError, match="at least one"):
        update_source_preferences(database, "src_missing")
    with pytest.raises(ValueError, match="requires a reason"):
        update_source_availability(database, "src_missing", available=False)
    with pytest.raises(KeyError):
        update_source_preferences(database, "src_missing", enabled=True)


def test_registry_listing_uses_configured_order_then_source_id(tmp_path: Path) -> None:
    library = tmp_path / "library"
    database = tmp_path / "data" / "mdict-live.db"
    migrate_application_database(database)
    write_source(library, "b.mdx", b"b")
    write_source(library, "a.mdx", b"a")
    ids = iter(("src_test_b", "src_test_a"))
    sources = sync_source_registry(
        database,
        discover_source_files(library),
        source_id_factory=lambda: next(ids),
    )
    update_source_preferences(database, sources[0].source_id, sort_order=2)
    update_source_preferences(database, sources[1].source_id, sort_order=1)

    ordered = list_registered_sources(database)

    assert [source.sort_order for source in ordered] == [1, 2]
