from __future__ import annotations

from pathlib import Path

import pytest

from storage_config import StorageConfigurationError, resolve_storage_paths


def test_legacy_content_layout_remains_the_default(tmp_path: Path) -> None:
    paths = resolve_storage_paths({}, environ={}, cwd=tmp_path)

    assert paths.legacy_layout is True
    assert paths.library_dir == tmp_path / "content"
    assert paths.data_dir == paths.library_dir
    assert paths.index_dir is None
    assert paths.application_database == tmp_path / "content" / "flask_mdict.db"


def test_legacy_mdict_and_index_configuration_are_preserved(tmp_path: Path) -> None:
    paths = resolve_storage_paths(
        {"MDICT_DIR": "legacy-corpus", "INDEX_DIR": "legacy-index"},
        environ={},
        cwd=tmp_path,
    )

    assert paths.legacy_layout is True
    assert paths.library_dir == tmp_path / "legacy-corpus"
    assert paths.data_dir == paths.library_dir
    assert paths.index_dir == tmp_path / "legacy-index"


def test_any_v2_key_enables_separated_writable_defaults(tmp_path: Path) -> None:
    paths = resolve_storage_paths(
        {"MDICT_LIBRARY_DIR": "library"}, environ={}, cwd=tmp_path
    )

    assert paths.legacy_layout is False
    assert paths.library_dir == tmp_path / "library"
    assert paths.data_dir == tmp_path / "data"
    assert paths.index_dir == tmp_path / "data" / "index"
    assert paths.config_dir == tmp_path / "config"
    assert paths.application_database == tmp_path / "data" / "mdict-live.db"


def test_environment_overrides_application_directory_configuration(tmp_path: Path) -> None:
    paths = resolve_storage_paths(
        {
            "MDICT_LIBRARY_DIR": "config-library",
            "MDICT_DATA_DIR": "config-data",
            "MDICT_INDEX_DIR": "config-index",
            "MDICT_CONFIG_DIR": "config-config",
        },
        environ={
            "MDICT_LIBRARY_DIR": "env-library",
            "MDICT_DATA_DIR": "env-data",
            "MDICT_INDEX_DIR": "env-index",
            "MDICT_CONFIG_DIR": "env-config",
        },
        cwd=tmp_path,
    )

    assert paths.library_dir == tmp_path / "env-library"
    assert paths.data_dir == tmp_path / "env-data"
    assert paths.index_dir == tmp_path / "env-index"
    assert paths.config_dir == tmp_path / "env-config"


@pytest.mark.parametrize(
    ("data_dir", "index_dir", "role"),
    [
        ("library/data", "indexes", "data"),
        ("data", "library/indexes", "index"),
    ],
)
def test_explicit_v2_layout_rejects_corpus_writes(
    tmp_path: Path, data_dir: str, index_dir: str, role: str
) -> None:
    with pytest.raises(StorageConfigurationError, match=rf"{role} directory"):
        resolve_storage_paths(
            {
                "MDICT_LIBRARY_DIR": "library",
                "MDICT_DATA_DIR": data_dir,
                "MDICT_INDEX_DIR": index_dir,
            },
            environ={},
            cwd=tmp_path,
        )
