"""Resolve legacy and v2 storage roles without touching the filesystem."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping


V2_DIRECTORY_KEYS = (
    "MDICT_LIBRARY_DIR",
    "MDICT_DATA_DIR",
    "MDICT_INDEX_DIR",
    "MDICT_CONFIG_DIR",
)


class StorageConfigurationError(ValueError):
    """Raised when explicit v2 paths would allow writes into the corpus."""


@dataclass(frozen=True, slots=True)
class StoragePaths:
    """Resolved storage roles for one application process."""

    library_dir: Path
    data_dir: Path
    index_dir: Path | None
    config_dir: Path
    legacy_layout: bool

    @property
    def application_database(self) -> Path:
        filename = "flask_mdict.db" if self.legacy_layout else "mdict-live.db"
        return self.data_dir / filename


def _configured_value(
    name: str,
    config: Mapping[str, object],
    environ: Mapping[str, str],
) -> str | None:
    environment_value = environ.get(name)
    if environment_value and environment_value.strip():
        return environment_value
    config_value = config.get(name)
    if config_value is None:
        return None
    text = os.fspath(config_value).strip()
    return text or None


def _absolute_path(value: str | os.PathLike[str], base_dir: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve(strict=False)


def _is_within(candidate: Path, parent: Path) -> bool:
    try:
        candidate.relative_to(parent)
    except ValueError:
        return False
    return True


def resolve_storage_paths(
    config: Mapping[str, object],
    *,
    environ: Mapping[str, str] | None = None,
    cwd: str | os.PathLike[str] | None = None,
) -> StoragePaths:
    """Resolve canonical v2 roles or preserve the historical content layout.

    Environment variables take precedence over application configuration. If no
    v2 directory key is present, ``MDICT_DIR`` and ``INDEX_DIR`` keep their
    historical meanings and the application database remains beside the corpus.
    Supplying any v2 directory key opts into separated writable defaults.
    """

    environment = os.environ if environ is None else environ
    base_dir = _absolute_path(cwd or os.getcwd(), Path.cwd())
    explicit_v2_layout = any(
        _configured_value(key, config, environment) is not None
        for key in V2_DIRECTORY_KEYS
    )

    legacy_library = _configured_value("MDICT_DIR", config, environment) or "content"
    library_value = (
        _configured_value("MDICT_LIBRARY_DIR", config, environment) or legacy_library
    )
    library_dir = _absolute_path(library_value, base_dir)

    if not explicit_v2_layout:
        legacy_index = _configured_value("INDEX_DIR", config, environment)
        return StoragePaths(
            library_dir=library_dir,
            data_dir=library_dir,
            index_dir=_absolute_path(legacy_index, base_dir) if legacy_index else None,
            config_dir=base_dir,
            legacy_layout=True,
        )

    data_value = _configured_value("MDICT_DATA_DIR", config, environment) or "data"
    data_dir = _absolute_path(data_value, base_dir)
    index_value = _configured_value("MDICT_INDEX_DIR", config, environment)
    index_dir = _absolute_path(index_value, base_dir) if index_value else data_dir / "index"
    config_value = _configured_value("MDICT_CONFIG_DIR", config, environment) or "config"
    config_dir = _absolute_path(config_value, base_dir)

    for role, writable_path in (("data", data_dir), ("index", index_dir)):
        if _is_within(writable_path, library_dir):
            raise StorageConfigurationError(
                f"{role} directory must not be inside the read-only library directory"
            )

    return StoragePaths(
        library_dir=library_dir,
        data_dir=data_dir,
        index_dir=index_dir,
        config_dir=config_dir,
        legacy_layout=False,
    )
