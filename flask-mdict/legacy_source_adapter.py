"""Thread-safe adapters from existing parser objects to the v2 source port."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3

from representation import RawSourceRecord, normalize_resource_path


class LegacyMdictSourceAdapter:
    def __init__(self, item: dict[str, object]) -> None:
        self.item = item
        self.query = item["query"]
        self.source_type = str(item["type"])
        self.database_path = item.get("database_path")
        self.root_path = Path(os.fspath(item["root_path"])).resolve(strict=False)

    @contextmanager
    def _connection(self):
        if self.source_type != "mdict_db" or not self.database_path:
            yield None
            return
        uri = f"{Path(os.fspath(self.database_path)).resolve(strict=True).as_uri()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def lookup(self, query: str) -> tuple[RawSourceRecord, ...]:
        if self.source_type == "app":
            records = self.query(query, self.item)
        else:
            with self._connection() as connection:
                records = self.query.mdx_lookup(connection, query, ignorecase=True)
        return tuple(
            RawSourceRecord(query, ordinal, record)
            for ordinal, record in enumerate(records or ())
        )

    def suggest(self, prefix: str, limit: int) -> tuple[str, ...]:
        if limit <= 0 or self.source_type == "app":
            return ()
        with self._connection() as connection:
            values = self.query.get_mdx_keys(connection, prefix)
        return tuple(values[:limit])

    def read_resource(self, raw_path: str) -> bytes | None:
        resource_path = normalize_resource_path(raw_path)
        local_path = (self.root_path / resource_path).resolve(strict=False)
        try:
            local_path.relative_to(self.root_path)
        except ValueError:
            return None
        if local_path.is_file():
            return local_path.read_bytes()
        if self.source_type == "app":
            return None
        mdict_key = "\\" + resource_path.replace("/", "\\")
        with self._connection() as connection:
            return self.query.mdd_lookup(connection, mdict_key, ignorecase=True)
