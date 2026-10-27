from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.source_fakes import (
    ENTRY_FIXTURE_DIR,
    REPRESENTATIVE_FIXTURES,
    FakeDictionarySource,
    FakeEntryRecord,
    FakeSourceUnavailable,
    load_entry_fixture,
    representative_source,
)


EXPECTED_FEATURES = {
    "plain": ("<article", "<ol>", "class=\"example\""),
    "css-heavy": ("@font-face", ":root", "grid-template-columns", "@media"),
    "malformed": ("<article class=entry>", "<h1>unfinished", "<li>First sense<li>"),
    "media": ("<img", "sound://", "<video", "background-image"),
    "link": ("entry://", "href=\"#sense-two\"", "https://", "javascript:"),
    "table": ("<table>", "rowspan=\"2\"", "colspan=\"2\"", "<caption>"),
    "script-bearing": ("<script>", "onload=", "onclick=", "<iframe", "<object", "<embed"),
}


@pytest.mark.parametrize("fixture_name", REPRESENTATIVE_FIXTURES)
def test_representative_fixture_exists_and_has_expected_features(fixture_name: str) -> None:
    fixture_path = ENTRY_FIXTURE_DIR / f"{fixture_name}.html"

    assert fixture_path.is_file()
    fixture = load_entry_fixture(fixture_name)
    assert fixture.strip().lower().startswith("<!doctype html>")
    for marker in EXPECTED_FEATURES[fixture_name]:
        assert marker in fixture


def test_fixture_loader_rejects_paths_outside_the_allowlist() -> None:
    with pytest.raises(ValueError, match="unknown representative fixture"):
        load_entry_fixture("../private-entry")


def test_representative_source_supports_exact_lookup_resources_and_call_history() -> None:
    source = representative_source()

    records = source.lookup("css-heavy")

    assert source.source_id == "src_fixture_primary"
    assert source.revision == "rev_fixture_001"
    assert records[0].headword == "css-heavy"
    assert "@font-face" in records[0].html
    assert source.read_resource("images/diagram.png") == b"synthetic-png"
    assert source.lookup_calls == ["css-heavy"]
    assert source.lookup("missing") == ()


def test_fake_source_suggestions_are_deterministic_deduplicated_and_bounded() -> None:
    source = FakeDictionarySource(
        source_id="src_fixture_suggestions",
        revision="rev_fixture_001",
        title="Suggestion Fixtures",
        records={
            "a": (FakeEntryRecord("Alpha", "<p>one</p>"),),
            "b": (FakeEntryRecord("alphabet", "<p>two</p>"),),
            "c": (FakeEntryRecord("Alpha", "<p>duplicate</p>", ordinal=1),),
            "d": (FakeEntryRecord("beta", "<p>three</p>"),),
        },
    )

    assert source.suggest("ALP", limit=10) == ("Alpha", "alphabet")
    assert source.suggest("", limit=2) == ("Alpha", "alphabet")
    assert source.suggest("a", limit=0) == ()


def test_fake_source_can_inject_unavailability_and_lookup_failures() -> None:
    unavailable = FakeDictionarySource(
        source_id="src_fixture_unavailable",
        revision="rev_fixture_001",
        title="Unavailable Fixture",
        available=False,
        unavailable_reason="index missing",
    )
    failing = FakeDictionarySource(
        source_id="src_fixture_failure",
        revision="rev_fixture_001",
        title="Failure Fixture",
        lookup_error=TimeoutError("synthetic timeout"),
    )

    with pytest.raises(FakeSourceUnavailable, match="index missing"):
        unavailable.lookup("word")
    with pytest.raises(TimeoutError, match="synthetic timeout"):
        failing.lookup("word")


def test_fixture_directory_contains_only_the_public_representative_set() -> None:
    fixture_names = {
        path.stem for path in Path(ENTRY_FIXTURE_DIR).glob("*.html") if path.is_file()
    }

    assert fixture_names == set(REPRESENTATIVE_FIXTURES)
