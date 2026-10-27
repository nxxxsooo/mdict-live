from __future__ import annotations

from pathlib import Path
import sqlite3

from lookup_services import MetadataService
from metadata_providers import ECDICTMetadataProvider


def create_metadata_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE ecdict(
                word TEXT PRIMARY KEY,
                phonetic TEXT,
                definition TEXT,
                translation TEXT,
                tag TEXT,
                exchange TEXT,
                frq INTEGER
            )
            """
        )
        connection.execute(
            """
            INSERT INTO ecdict
                (word, phonetic, definition, translation, tag, exchange, frq)
            VALUES
                ('right', 'raɪt', 'correct or suitable', '正确的；合适的',
                 'cet4 core', 'p:righted/3:rights/', 492)
            """
        )


def test_ecdict_provider_returns_named_structured_metadata(tmp_path: Path) -> None:
    database = tmp_path / "ecdict.db"
    create_metadata_database(database)
    provider = ECDICTMetadataProvider(database, dataset_version="fixture-1")

    result = MetadataService(provider).lookup(" right ")

    assert result.available is True
    assert len(result.records) == 1
    record = result.records[0]
    assert record.dataset.dataset_id == "ecdict"
    assert record.dataset.version == "fixture-1"
    assert record.phonetic == "raɪt"
    assert record.frequency == 492.0
    assert record.tags == ("cet4", "core")
    assert record.inflections == (("past_tense", "righted"), ("third_person", "rights"))
    assert record.definition == "correct or suitable"
    assert record.translation == "正确的；合适的"


def test_missing_ecdict_database_is_a_nonfatal_unavailable_capability(
    tmp_path: Path,
) -> None:
    provider = ECDICTMetadataProvider(tmp_path / "missing.db")

    result = MetadataService(provider).lookup("right")

    assert result.available is False
    assert result.records == ()
    assert result.unavailable_reason == "metadata_database_unavailable"
