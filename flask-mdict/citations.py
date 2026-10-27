"""Stable citation identities and HMAC-protected opaque resolver tokens."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import hmac
import json
import struct
import unicodedata
from urllib.parse import quote

from representation import RenderedSourceRecord


REPRESENTATION_VERSION = "rep-v1"
SUPPORTED_REPRESENTATION_VERSIONS = frozenset({REPRESENTATION_VERSION})
TOKEN_FORMAT_VERSION = 1
TOKEN_SIGNATURE_BYTES = hashlib.sha256().digest_size
MAX_TOKEN_BYTES = 4096


class InvalidCitationToken(ValueError):
    """Raised when a token is malformed, forged, or semantically invalid."""


class CitationGone(LookupError):
    """Raised when correctly signed evidence is no longer resolvable."""

    def __init__(self, reason: str, source_id: str, revision: str):
        super().__init__(reason)
        self.reason = reason
        self.source_id = source_id
        self.revision = revision


@dataclass(frozen=True, slots=True)
class CitationTarget:
    source_id: str
    revision: str
    representation_version: str
    entry_id: str
    block_id: str | None = None
    headword: str | None = None
    record_ordinal: int | None = None


@dataclass(frozen=True, slots=True)
class CitationReference:
    uri: str
    token: str


@dataclass(frozen=True, slots=True)
class CitedTextBlock:
    block_id: str
    order: int
    text: str
    citation: CitationReference


@dataclass(frozen=True, slots=True)
class CitedRenderedRecord:
    headword: str
    record_ordinal: int
    entry_id: str
    html: str
    text_blocks: tuple[CitedTextBlock, ...]
    citation: CitationReference
    link_chain: tuple[str, ...]


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    if not value or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for character in value):
        raise InvalidCitationToken("citation token is not valid base64url")
    padding = "=" * (-len(value) % 4)
    try:
        decoded = base64.b64decode(value + padding, altchars=b"-_", validate=True)
    except (ValueError, TypeError) as error:
        raise InvalidCitationToken("citation token is not valid base64url") from error
    if _base64url_encode(decoded) != value:
        raise InvalidCitationToken("citation token is not canonical base64url")
    return decoded


def derive_purpose_key(secret: bytes, purpose: str) -> bytes:
    if len(secret) < 32:
        raise ValueError("citation signing secret must contain at least 32 bytes")
    return hmac.new(secret, f"mdict-live:{purpose}:v1".encode(), hashlib.sha256).digest()


def normalize_headword(headword: str) -> str:
    return unicodedata.normalize("NFC", headword.strip())


def _identity_digest(domain: bytes, *parts: bytes) -> str:
    digest = hashlib.sha256(domain)
    for part in parts:
        digest.update(len(part).to_bytes(8, "big"))
        digest.update(part)
    return _base64url_encode(digest.digest()[:18])


def make_entry_id(
    headword: str, record_ordinal: int, record_hash: str
) -> str:
    if record_ordinal < 0:
        raise ValueError("record ordinal must be non-negative")
    try:
        record_hash_bytes = bytes.fromhex(record_hash)
    except ValueError as error:
        raise ValueError("record hash must be hexadecimal") from error
    return "ent_" + _identity_digest(
        b"mdict-live-entry-v1\0",
        normalize_headword(headword).encode("utf-8"),
        record_ordinal.to_bytes(8, "big"),
        record_hash_bytes,
    )


def make_block_id(order: int, text: str) -> str:
    if order < 0:
        raise ValueError("block order must be non-negative")
    text_hash = hashlib.sha256(text.encode("utf-8")).digest()
    return f"blk_{order}_" + _identity_digest(
        b"mdict-live-block-v1\0", order.to_bytes(8, "big"), text_hash
    )


def citation_uri(target: CitationTarget) -> str:
    path = "/".join(
        quote(component, safe="")
        for component in (
            target.source_id,
            target.revision,
            target.representation_version,
            target.entry_id,
        )
    )
    uri = f"mdict://{path}"
    if target.block_id is not None:
        uri += f"#{quote(target.block_id, safe='')}"
    return uri


def encode_citation_token(target: CitationTarget, signing_key: bytes) -> str:
    payload = json.dumps(
        {
            "b": target.block_id,
            "e": target.entry_id,
            "h": target.headword,
            "o": target.record_ordinal,
            "p": target.representation_version,
            "r": target.revision,
            "s": target.source_id,
            "v": TOKEN_FORMAT_VERSION,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(payload) > MAX_TOKEN_BYTES - 4 - TOKEN_SIGNATURE_BYTES:
        raise ValueError("citation payload exceeds its bound")
    framed_payload = struct.pack(">I", len(payload)) + payload
    signature = hmac.new(signing_key, framed_payload, hashlib.sha256).digest()
    return _base64url_encode(framed_payload + signature)


def decode_citation_token(token: str, signing_key: bytes) -> CitationTarget:
    framed = _base64url_decode(token)
    if len(framed) < 4 + TOKEN_SIGNATURE_BYTES or len(framed) > MAX_TOKEN_BYTES:
        raise InvalidCitationToken("citation token length is invalid")
    payload_size = struct.unpack(">I", framed[:4])[0]
    expected_size = 4 + payload_size + TOKEN_SIGNATURE_BYTES
    if expected_size != len(framed):
        raise InvalidCitationToken("citation token framing is invalid")
    framed_payload = framed[: 4 + payload_size]
    signature = framed[4 + payload_size :]
    expected_signature = hmac.new(signing_key, framed_payload, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_signature):
        raise InvalidCitationToken("citation token signature is invalid")
    try:
        payload = json.loads(framed[4 : 4 + payload_size].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InvalidCitationToken("citation token payload is invalid") from error
    if set(payload) != {"b", "e", "h", "o", "p", "r", "s", "v"}:
        raise InvalidCitationToken("citation token fields are invalid")
    if payload["v"] != TOKEN_FORMAT_VERSION:
        raise InvalidCitationToken("citation token format is unsupported")
    if not all(
        isinstance(payload[field], str) and payload[field]
        for field in ("e", "p", "r", "s")
    ):
        raise InvalidCitationToken("citation token identity is invalid")
    if payload["b"] is not None and not isinstance(payload["b"], str):
        raise InvalidCitationToken("citation block identity is invalid")
    if payload["h"] is not None and not isinstance(payload["h"], str):
        raise InvalidCitationToken("citation headword is invalid")
    if payload["o"] is not None and (
        not isinstance(payload["o"], int)
        or isinstance(payload["o"], bool)
        or payload["o"] < 0
    ):
        raise InvalidCitationToken("citation record ordinal is invalid")
    return CitationTarget(
        source_id=payload["s"],
        revision=payload["r"],
        representation_version=payload["p"],
        entry_id=payload["e"],
        block_id=payload["b"],
        headword=payload["h"],
        record_ordinal=payload["o"],
    )


def citation_reference(
    target: CitationTarget, signing_key: bytes
) -> CitationReference:
    return CitationReference(
        uri=citation_uri(target), token=encode_citation_token(target, signing_key)
    )


def cite_rendered_record(
    source_id: str,
    revision: str,
    record: RenderedSourceRecord,
    signing_key: bytes,
    *,
    representation_version: str = REPRESENTATION_VERSION,
) -> CitedRenderedRecord:
    entry_id = make_entry_id(record.headword, record.record_ordinal, record.record_hash)
    entry_target = CitationTarget(
        source_id=source_id,
        revision=revision,
        representation_version=representation_version,
        entry_id=entry_id,
        headword=normalize_headword(record.headword),
        record_ordinal=record.record_ordinal,
    )
    blocks = []
    for block in record.text_blocks:
        block_id = make_block_id(block.order, block.text)
        block_target = CitationTarget(
            source_id=source_id,
            revision=revision,
            representation_version=representation_version,
            entry_id=entry_id,
            block_id=block_id,
            headword=normalize_headword(record.headword),
            record_ordinal=record.record_ordinal,
        )
        blocks.append(
            CitedTextBlock(
                block_id=block_id,
                order=block.order,
                text=block.text,
                citation=citation_reference(block_target, signing_key),
            )
        )
    return CitedRenderedRecord(
        headword=record.headword,
        record_ordinal=record.record_ordinal,
        entry_id=entry_id,
        html=record.html,
        text_blocks=tuple(blocks),
        citation=citation_reference(entry_target, signing_key),
        link_chain=record.link_chain,
    )


def validate_citation_availability(
    target: CitationTarget,
    mounted_revisions: Mapping[str, str],
    *,
    supported_versions: frozenset[str] = SUPPORTED_REPRESENTATION_VERSIONS,
) -> CitationTarget:
    current_revision = mounted_revisions.get(target.source_id)
    if current_revision is None:
        raise CitationGone("source_unavailable", target.source_id, target.revision)
    if current_revision != target.revision:
        raise CitationGone("revision_unavailable", target.source_id, target.revision)
    if target.representation_version not in supported_versions:
        raise CitationGone(
            "representation_version_unsupported", target.source_id, target.revision
        )
    return target
