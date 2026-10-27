from __future__ import annotations

from pathlib import Path
import sqlite3

from application_database import migrate_application_database
from artifact_storage import adopt_legacy_index_files


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "migration"


def materialize_sql_fixture(sql_fixture: str, database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    script = (FIXTURE_DIR / sql_fixture).read_text(encoding="utf-8")
    with sqlite3.connect(database_path) as connection:
        connection.executescript(script)


def test_current_legacy_application_and_wordbook_schema_migrates_in_place(
    tmp_path: Path,
) -> None:
    database = tmp_path / "flask_mdict.db"
    materialize_sql_fixture("legacy-application.sql", database)

    migrate_application_database(database)

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT word, count FROM history").fetchall() == [
            ("right", 7)
        ]
        assert connection.execute("SELECT name, value FROM setting").fetchall() == [
            ("legacy-source-uuid", "1")
        ]
        assert connection.execute("SELECT name FROM wordbook").fetchall() == [
            ("Fixture words",)
        ]
        assert connection.execute(
            "SELECT wordbook_id, word FROM wordbook_entry"
        ).fetchall() == [(1, "right")]
        assert connection.execute(
            "SELECT COUNT(*) FROM source_registry"
        ).fetchone() == (0,)


def test_representative_legacy_mdx_and_mdd_indexes_are_copied_not_moved(
    tmp_path: Path,
) -> None:
    library = tmp_path / "library"
    destination = tmp_path / "data" / "index" / "LEGACY-UUID"
    mdx_file = library / "fixture.mdx"
    library.mkdir()
    mdx_file.write_bytes(b"synthetic mdx")
    (library / "fixture.mdd").write_bytes(b"synthetic mdd")
    mdx_index = library / "fixture.mdx.db"
    mdd_index = library / "fixture.mdd.db"
    materialize_sql_fixture("legacy-mdx-index.sql", mdx_index)
    materialize_sql_fixture("legacy-mdd-index.sql", mdd_index)
    source_bytes = {path.name: path.read_bytes() for path in (mdx_index, mdd_index)}

    result = adopt_legacy_index_files(mdx_file, destination)

    assert result.copied == ("fixture.mdd.db", "fixture.mdx.db")
    assert result.rejected == ()
    assert {path.name for path in destination.glob("*.db")} == {
        "fixture.mdd.db",
        "fixture.mdx.db",
    }
    assert {path.name: path.read_bytes() for path in (mdx_index, mdd_index)} == source_bytes
    with sqlite3.connect(destination / "fixture.mdx.db") as connection:
        assert connection.execute("SELECT key_text FROM MDX_INDEX").fetchall() == [
            ("right",)
        ]


def test_invalid_legacy_index_is_nonfatal_and_left_for_rebuild(tmp_path: Path) -> None:
    library = tmp_path / "library"
    destination = tmp_path / "data" / "index" / "LEGACY-UUID"
    library.mkdir()
    mdx_file = library / "fixture.mdx"
    mdx_file.write_bytes(b"synthetic mdx")
    invalid_index = library / "fixture.mdx.db"
    invalid_index.write_bytes(b"invalid sqlite")

    result = adopt_legacy_index_files(mdx_file, destination)

    assert result.copied == ()
    assert result.rejected == ("fixture.mdx.db",)
    assert invalid_index.read_bytes() == b"invalid sqlite"
    assert not list(destination.glob("*.db"))
    assert not list(destination.glob("*.tmp"))
