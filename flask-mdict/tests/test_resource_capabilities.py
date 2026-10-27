from __future__ import annotations

import pytest

from citations import derive_purpose_key
from representation import UnsafeResourcePath
from resource_capabilities import (
    DEFAULT_CAPABILITY_TTL_SECONDS,
    InvalidResourceCapability,
    ResourceTarget,
    UnsafeResourceMediaType,
    decode_resource_capability,
    encode_resource_capability,
    issue_resource_capability,
    prepare_safe_asset,
    safe_media_type,
)


SECRET = b"synthetic-test-secret-that-is-at-least-32-bytes"
SIGNING_KEY = derive_purpose_key(SECRET, "assets")
SOURCE_ID = "src_fixture_primary"
REVISION = "rev_fixture_0001"
NOW = 1_800_000_000


def test_capability_round_trip_is_source_revision_path_and_expiry_scoped() -> None:
    issued = issue_resource_capability(
        SOURCE_ID, REVISION, "images/diagram.png", SIGNING_KEY, now=NOW
    )

    target = decode_resource_capability(issued.token, SIGNING_KEY, now=NOW + 1)

    assert target == ResourceTarget(
        SOURCE_ID,
        REVISION,
        "images/diagram.png",
        NOW + DEFAULT_CAPABILITY_TTL_SECONDS,
    )
    assert issued.url == f"/assets/v2/{issued.token}"
    assert SECRET.decode() not in issued.url


@pytest.mark.parametrize(
    "path", ("../secret", "%2e%2e/secret", "images/../../secret", "/../secret")
)
def test_raw_and_encoded_parent_traversal_cannot_be_issued(path: str) -> None:
    with pytest.raises(UnsafeResourcePath):
        issue_resource_capability(SOURCE_ID, REVISION, path, SIGNING_KEY, now=NOW)


def test_expired_and_forged_capabilities_share_a_generic_failure() -> None:
    issued = issue_resource_capability(
        SOURCE_ID, REVISION, "images/diagram.png", SIGNING_KEY, now=NOW
    )
    position = len(issued.token) // 2
    replacement = "A" if issued.token[position] != "A" else "B"
    forged = issued.token[:position] + replacement + issued.token[position + 1 :]

    with pytest.raises(InvalidResourceCapability, match="invalid"):
        decode_resource_capability(
            issued.token,
            SIGNING_KEY,
            now=NOW + DEFAULT_CAPABILITY_TTL_SECONDS,
        )
    with pytest.raises(InvalidResourceCapability, match="invalid"):
        decode_resource_capability(forged, SIGNING_KEY, now=NOW)


def test_capability_signed_for_one_purpose_fails_with_another_key() -> None:
    issued = issue_resource_capability(
        SOURCE_ID, REVISION, "images/diagram.png", SIGNING_KEY, now=NOW
    )
    citation_key = derive_purpose_key(SECRET, "citations")

    with pytest.raises(InvalidResourceCapability):
        decode_resource_capability(issued.token, citation_key, now=NOW)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("style/main.css", "text/css; charset=utf-8"),
        ("images/photo.JPEG", "image/jpeg"),
        ("fonts/source.woff2", "font/woff2"),
        ("sounds/word.mp3", "audio/mpeg"),
        ("media/example.webm", "video/webm"),
    ],
)
def test_safe_media_types_are_explicit(path: str, expected: str) -> None:
    assert safe_media_type(path) == expected


@pytest.mark.parametrize("path", ("script.js", "entry.html", "vector.svg", "payload.bin"))
def test_executable_or_unknown_media_types_are_rejected(path: str) -> None:
    with pytest.raises(UnsafeResourceMediaType):
        safe_media_type(path)


def test_nested_css_resources_inherit_source_revision_and_parent_expiry() -> None:
    parent = ResourceTarget(
        SOURCE_ID, REVISION, "styles/main.css", NOW + 120
    )
    css = b"""
    @font-face { src: url('../fonts/fixture.woff2'); }
    .hero { background: url('../images/diagram.png'); }
    """

    asset = prepare_safe_asset(parent, css, SIGNING_KEY, now=NOW)

    assert asset.media_type == "text/css; charset=utf-8"
    assert asset.cache_seconds == 120
    text = asset.content.decode("utf-8")
    tokens = [part.split('"', 1)[0] for part in text.split("/assets/v2/")[1:]]
    targets = [
        decode_resource_capability(token, SIGNING_KEY, now=NOW) for token in tokens
    ]
    assert {target.resource_path for target in targets} == {
        "fonts/fixture.woff2",
        "images/diagram.png",
    }
    assert {target.expires_at for target in targets} == {NOW + 120}


def test_invalid_stylesheet_encoding_is_rejected_without_fallback_sniffing() -> None:
    target = ResourceTarget(SOURCE_ID, REVISION, "styles/main.css", NOW + 60)

    with pytest.raises(UnsafeResourceMediaType, match="encoding"):
        prepare_safe_asset(target, b"\xff\xfe", SIGNING_KEY, now=NOW)
