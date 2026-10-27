from __future__ import annotations

from pathlib import Path

from artifact_storage import persist_description, resolve_source_artifact_paths


def snapshot_tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_v2_artifacts_resolve_only_to_writable_data_and_index_roots(
    tmp_path: Path,
) -> None:
    library = tmp_path / "library"
    data = tmp_path / "data"
    indexes = data / "index"
    source_root = library / "nested"
    source_root.mkdir(parents=True)
    (source_root / "fixture.mdx").write_bytes(b"read-only corpus bytes")
    before = snapshot_tree(library)

    paths = resolve_source_artifact_paths(
        source_root=source_root,
        source_name="fixture",
        source_uuid="LEGACY-UUID",
        index_root=indexes,
        description_root=data / "descriptions",
    )
    paths.index_dir.mkdir(parents=True)
    (paths.index_dir / "fixture.mdx.db").write_bytes(b"generated index")
    persist_description(paths.description_file, "<p>Synthetic description</p>")

    assert paths.index_dir == data / "index" / "LEGACY-UUID"
    assert paths.description_file == data / "descriptions" / "LEGACY-UUID" / "about.html"
    assert snapshot_tree(library) == before
    assert not list(library.rglob("*.db"))
    assert not list(library.rglob("about_*.html"))


def test_legacy_layout_keeps_historical_artifact_locations(tmp_path: Path) -> None:
    source_root = tmp_path / "content" / "nested"
    paths = resolve_source_artifact_paths(
        source_root=source_root,
        source_name="fixture",
        source_uuid="LEGACY-UUID",
        index_root=None,
        description_root=None,
    )

    assert paths.index_dir is None
    assert paths.description_file == source_root / "about_fixture.html"


def test_existing_derived_description_is_not_overwritten(tmp_path: Path) -> None:
    description_file = tmp_path / "data" / "descriptions" / "source" / "about.html"

    persist_description(description_file, "first")
    persist_description(description_file, "second")

    assert description_file.read_text(encoding="utf-8") == "first"
