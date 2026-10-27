from __future__ import annotations

import pytest

from citations import (
    CitationGone,
    InvalidCitationToken,
    REPRESENTATION_VERSION,
    CitationTarget,
    citation_uri,
    cite_rendered_record,
    decode_citation_token,
    derive_purpose_key,
    encode_citation_token,
    make_block_id,
    make_entry_id,
    validate_citation_availability,
)
from representation import RawSourceRecord, build_record_representations


SECRET = b"synthetic-test-secret-that-is-at-least-32-bytes"
SIGNING_KEY = derive_purpose_key(SECRET, "citations")
SOURCE_ID = "src_fixture_primary"
REVISION = "rev_fixture_0001"


def render_fixture(text: str = "Correct as a fact."):
    return build_record_representations(
        (RawSourceRecord(" right ", 4, f"<p>{text}</p>"),),
        lambda _target: (),
        lambda path, kind: f"/assets/{kind}/{path}",
    )[0]


def test_entry_identity_is_stable_for_nfc_headword_ordinal_and_content() -> None:
    record_hash = "00" * 32

    composed = make_entry_id(" café ", 2, record_hash)
    decomposed = make_entry_id("cafe\u0301", 2, record_hash)

    assert composed == decomposed
    assert make_entry_id("café", 3, record_hash) != composed
    assert make_entry_id("café", 2, "01" * 32) != composed


def test_individual_blocks_have_order_and_text_specific_citations() -> None:
    first = make_block_id(0, "First sense")

    assert first == make_block_id(0, "First sense")
    assert first != make_block_id(1, "First sense")
    assert first != make_block_id(0, "Second sense")


def test_cited_record_round_trips_entry_and_block_tokens() -> None:
    cited = cite_rendered_record(SOURCE_ID, REVISION, render_fixture(), SIGNING_KEY)

    entry_target = decode_citation_token(cited.citation.token, SIGNING_KEY)
    block_target = decode_citation_token(cited.text_blocks[0].citation.token, SIGNING_KEY)

    assert entry_target.entry_id == cited.entry_id
    assert entry_target.block_id is None
    assert entry_target.headword == "right"
    assert entry_target.record_ordinal == 4
    assert block_target.entry_id == cited.entry_id
    assert block_target.block_id == cited.text_blocks[0].block_id
    assert block_target.headword == "right"
    assert block_target.record_ordinal == 4
    assert cited.citation.uri.startswith(
        f"mdict://{SOURCE_ID}/{REVISION}/{REPRESENTATION_VERSION}/"
    )
    assert cited.text_blocks[0].citation.uri.endswith(
        f"#{cited.text_blocks[0].block_id}"
    )


def test_unchanged_record_keeps_citations_and_content_change_advances_them() -> None:
    first = cite_rendered_record(SOURCE_ID, REVISION, render_fixture(), SIGNING_KEY)
    unchanged = cite_rendered_record(SOURCE_ID, REVISION, render_fixture(), SIGNING_KEY)
    changed = cite_rendered_record(
        SOURCE_ID, REVISION, render_fixture("Suitable for this purpose."), SIGNING_KEY
    )

    assert first == unchanged
    assert changed.entry_id != first.entry_id
    assert changed.text_blocks[0].block_id != first.text_blocks[0].block_id


@pytest.mark.parametrize("token", ("", "not+base64url", "AAAA", "_" * 40))
def test_malformed_tokens_are_rejected(token: str) -> None:
    with pytest.raises(InvalidCitationToken):
        decode_citation_token(token, SIGNING_KEY)


def test_forged_token_is_rejected_by_constant_time_signature_check() -> None:
    target = CitationTarget(
        SOURCE_ID, REVISION, REPRESENTATION_VERSION, "ent_fixture_001"
    )
    token = encode_citation_token(target, SIGNING_KEY)
    position = len(token) // 2
    replacement = "A" if token[position] != "A" else "B"
    forged = token[:position] + replacement + token[position + 1 :]

    with pytest.raises(InvalidCitationToken, match="signature"):
        decode_citation_token(forged, SIGNING_KEY)


@pytest.mark.parametrize(
    ("mounted", "version", "reason"),
    [
        ({}, REPRESENTATION_VERSION, "source_unavailable"),
        ({SOURCE_ID: "rev_fixture_9999"}, REPRESENTATION_VERSION, "revision_unavailable"),
        ({SOURCE_ID: REVISION}, "rep-future", "representation_version_unsupported"),
    ],
)
def test_missing_stale_and_unsupported_citations_are_gone(
    mounted: dict[str, str], version: str, reason: str
) -> None:
    target = CitationTarget(SOURCE_ID, REVISION, version, "ent_fixture_001")

    with pytest.raises(CitationGone) as captured:
        validate_citation_availability(target, mounted)

    assert captured.value.reason == reason
    assert captured.value.source_id == SOURCE_ID
    assert captured.value.revision == REVISION


def test_current_supported_citation_remains_available() -> None:
    target = CitationTarget(
        SOURCE_ID, REVISION, REPRESENTATION_VERSION, "ent_fixture_001"
    )

    assert validate_citation_availability(target, {SOURCE_ID: REVISION}) is target


def test_uri_percent_encodes_components_but_contains_no_host_path() -> None:
    target = CitationTarget(
        SOURCE_ID, REVISION, REPRESENTATION_VERSION, "ent word", "blk#one"
    )

    uri = citation_uri(target)

    assert "ent%20word" in uri
    assert uri.endswith("#blk%23one")
    assert "/Users/" not in uri
