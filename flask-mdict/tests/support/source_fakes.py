"""Deterministic dictionary source doubles for service and contract tests.

These fakes deliberately avoid importing Flask or the private MDict parser. They
model only the source-facing operations needed by the v2 service seam so tests
can exercise ordering, partial failure, resources, and representative markup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import time


ENTRY_FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "entries"
REPRESENTATIVE_FIXTURES = (
    "plain",
    "css-heavy",
    "malformed",
    "media",
    "link",
    "table",
    "script-bearing",
)


class FakeSourceUnavailable(RuntimeError):
    """Raised when a fake source is configured as unavailable."""


@dataclass(frozen=True, slots=True)
class FakeEntryRecord:
    """One source record before representation and citation processing."""

    headword: str
    html: str
    ordinal: int = 0


@dataclass(slots=True)
class FakeDictionarySource:
    """Configurable in-memory source adapter with deterministic behavior."""

    source_id: str
    revision: str
    title: str
    records: dict[str, tuple[FakeEntryRecord, ...]] = field(default_factory=dict)
    resources: dict[str, bytes] = field(default_factory=dict)
    enabled: bool = True
    sort_order: int = 0
    available: bool = True
    unavailable_reason: str | None = None
    lookup_error: Exception | None = None
    lookup_delay_seconds: float = 0.0
    lookup_calls: list[str] = field(default_factory=list, init=False)

    def lookup(self, query: str) -> tuple[FakeEntryRecord, ...]:
        """Return exact records or inject the configured source behavior."""

        self.lookup_calls.append(query)
        if not self.available:
            reason = self.unavailable_reason or "source unavailable"
            raise FakeSourceUnavailable(reason)
        if self.lookup_delay_seconds:
            time.sleep(self.lookup_delay_seconds)
        if self.lookup_error is not None:
            raise self.lookup_error
        return self.records.get(query, ())

    def suggest(self, prefix: str, limit: int) -> tuple[str, ...]:
        """Return sorted, deduplicated headwords using a bounded prefix match."""

        if limit <= 0:
            return ()
        prefix_folded = prefix.casefold()
        matches = {
            record.headword
            for records in self.records.values()
            for record in records
            if record.headword.casefold().startswith(prefix_folded)
        }
        return tuple(sorted(matches, key=lambda item: (item.casefold(), item))[:limit])

    def read_resource(self, resource_path: str) -> bytes:
        """Return an exact source-scoped resource or raise ``KeyError``."""

        return self.resources[resource_path]


def load_entry_fixture(name: str) -> str:
    """Load one allowlisted synthetic entry fixture as UTF-8 text."""

    if name not in REPRESENTATIVE_FIXTURES:
        raise ValueError(f"unknown representative fixture: {name}")
    return (ENTRY_FIXTURE_DIR / f"{name}.html").read_text(encoding="utf-8")


def representative_source() -> FakeDictionarySource:
    """Build a healthy source containing every representative fixture."""

    records = {
        name: (FakeEntryRecord(headword=name, html=load_entry_fixture(name)),)
        for name in REPRESENTATIVE_FIXTURES
    }
    return FakeDictionarySource(
        source_id="src_fixture_primary",
        revision="rev_fixture_001",
        title="Synthetic Fixture Dictionary",
        records=records,
        resources={
            "images/diagram.png": b"synthetic-png",
            "sounds/example.mp3": b"synthetic-mp3",
            "fonts/fixture.woff2": b"synthetic-woff2",
        },
    )
