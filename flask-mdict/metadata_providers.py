"""Optional named lexical-metadata adapters for the shared service layer."""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3

from domain import MetadataDataset, MetadataRecord


ECDICT_EXCHANGE_FIELDS = {
    "p": "past_tense",
    "d": "past_participle",
    "i": "present_participle",
    "3": "third_person",
    "r": "comparative",
    "t": "superlative",
    "s": "plural",
    "0": "root",
    "1": "root_variant",
}


class ECDICTMetadataProvider:
    """Read ECDICT-derived fields without mixing them into MDict evidence."""

    def __init__(
        self,
        database_path: str | os.PathLike[str] | None,
        *,
        dataset_version: str | None = None,
    ) -> None:
        self.database_path = Path(database_path) if database_path else None
        self.dataset = MetadataDataset(
            dataset_id="ecdict",
            title="ECDICT lexical metadata",
            version=dataset_version,
        )

    @property
    def available(self) -> bool:
        return self.database_path is not None and self.database_path.is_file()

    @property
    def unavailable_reason(self) -> str | None:
        return None if self.available else "metadata_database_unavailable"

    def lookup(self, query: str) -> tuple[MetadataRecord, ...]:
        if not self.available:
            return ()
        uri = f"{self.database_path.resolve(strict=True).as_uri()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM ecdict WHERE WORD = ?", (query.casefold(),)
            ).fetchone()
        if row is None:
            return ()
        values = dict(row)
        inflections = []
        for item in (values.get("exchange") or "").split("/"):
            if not item or ":" not in item:
                continue
            kind, value = item.split(":", 1)
            inflections.append((ECDICT_EXCHANGE_FIELDS.get(kind, kind), value))
        frequency_value = values.get("frq")
        frequency = float(frequency_value) if frequency_value not in (None, "") else None
        return (
            MetadataRecord(
                query=query,
                dataset=self.dataset,
                phonetic=values.get("phonetic") or None,
                frequency=frequency,
                tags=tuple((values.get("tag") or "").split()),
                inflections=tuple(inflections),
                definition=values.get("definition") or None,
                translation=values.get("translation") or None,
                legacy_fields=tuple(
                    (name, values.get(name))
                    for name in ("oxford", "collins", "bnc", "frq")
                    if name in values
                ),
            ),
        )
