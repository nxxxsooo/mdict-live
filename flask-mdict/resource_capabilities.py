"""Short-lived source-scoped dictionary resource capabilities."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import struct
import time

from representation import (
    UnsafeResourcePath,
    normalize_resource_path,
    rewrite_css_resources,
)


CAPABILITY_FORMAT_VERSION = 1
DEFAULT_CAPABILITY_TTL_SECONDS = 300
MAX_CAPABILITY_TTL_SECONDS = 3600
MAX_CAPABILITY_BYTES = 4096
SIGNATURE_BYTES = hashlib.sha256().digest_size

SAFE_MEDIA_TYPES = {
    ".avif": "image/avif",
    ".css": "text/css; charset=utf-8",
    ".flac": "audio/flac",
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".oga": "audio/ogg",
    ".ogg": "audio/ogg",
    ".otf": "font/otf",
    ".png": "image/png",
    ".ttf": "font/ttf",
    ".wav": "audio/wav",
    ".webm": "video/webm",
    ".webp": "image/webp",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


class InvalidResourceCapability(ValueError):
    """Generic failure for malformed, forged, or expired capabilities."""


class UnsafeResourceMediaType(ValueError):
    """Raised before serving a resource with an executable/unknown media type."""


@dataclass(frozen=True, slots=True)
class ResourceTarget:
    source_id: str
    revision: str
    resource_path: str
    expires_at: int


@dataclass(frozen=True, slots=True)
class IssuedResourceCapability:
    token: str
    url: str
    expires_at: int


@dataclass(frozen=True, slots=True)
class SafeAsset:
    content: bytes
    media_type: str
    cache_seconds: int


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    if not value or any(
        character
        not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        for character in value
    ):
        raise InvalidResourceCapability("resource capability is invalid")
    try:
        decoded = base64.b64decode(
            value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
        )
    except (TypeError, ValueError) as error:
        raise InvalidResourceCapability("resource capability is invalid") from error
    if _encode(decoded) != value:
        raise InvalidResourceCapability("resource capability is invalid")
    return decoded


def _serialize_target(target: ResourceTarget) -> bytes:
    return json.dumps(
        {
            "p": target.resource_path,
            "r": target.revision,
            "s": target.source_id,
            "v": CAPABILITY_FORMAT_VERSION,
            "x": target.expires_at,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def encode_resource_capability(target: ResourceTarget, signing_key: bytes) -> str:
    payload = _serialize_target(target)
    if len(payload) > MAX_CAPABILITY_BYTES - 4 - SIGNATURE_BYTES:
        raise ValueError("resource capability payload exceeds its bound")
    framed_payload = struct.pack(">I", len(payload)) + payload
    signature = hmac.new(signing_key, framed_payload, hashlib.sha256).digest()
    return _encode(framed_payload + signature)


def decode_resource_capability(
    token: str, signing_key: bytes, *, now: int | None = None
) -> ResourceTarget:
    framed = _decode(token)
    if len(framed) < 4 + SIGNATURE_BYTES or len(framed) > MAX_CAPABILITY_BYTES:
        raise InvalidResourceCapability("resource capability is invalid")
    payload_size = struct.unpack(">I", framed[:4])[0]
    if len(framed) != 4 + payload_size + SIGNATURE_BYTES:
        raise InvalidResourceCapability("resource capability is invalid")
    framed_payload = framed[: 4 + payload_size]
    signature = framed[4 + payload_size :]
    expected = hmac.new(signing_key, framed_payload, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise InvalidResourceCapability("resource capability is invalid")
    try:
        payload = json.loads(framed[4 : 4 + payload_size].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InvalidResourceCapability("resource capability is invalid") from error
    if set(payload) != {"p", "r", "s", "v", "x"}:
        raise InvalidResourceCapability("resource capability is invalid")
    if payload["v"] != CAPABILITY_FORMAT_VERSION:
        raise InvalidResourceCapability("resource capability is invalid")
    if not all(
        isinstance(payload[field], str) and payload[field]
        for field in ("p", "r", "s")
    ) or not isinstance(payload["x"], int):
        raise InvalidResourceCapability("resource capability is invalid")
    try:
        normalized_path = normalize_resource_path(payload["p"])
    except UnsafeResourcePath as error:
        raise InvalidResourceCapability("resource capability is invalid") from error
    if normalized_path != payload["p"]:
        raise InvalidResourceCapability("resource capability is invalid")
    current_time = int(time.time()) if now is None else now
    if current_time >= payload["x"]:
        raise InvalidResourceCapability("resource capability is invalid")
    return ResourceTarget(
        source_id=payload["s"],
        revision=payload["r"],
        resource_path=payload["p"],
        expires_at=payload["x"],
    )


def issue_resource_capability(
    source_id: str,
    revision: str,
    raw_resource_path: str,
    signing_key: bytes,
    *,
    now: int | None = None,
    ttl_seconds: int = DEFAULT_CAPABILITY_TTL_SECONDS,
    expires_at: int | None = None,
) -> IssuedResourceCapability:
    current_time = int(time.time()) if now is None else now
    if expires_at is None:
        if ttl_seconds < 1 or ttl_seconds > MAX_CAPABILITY_TTL_SECONDS:
            raise ValueError("resource capability TTL is outside its bound")
        expires_at = current_time + ttl_seconds
    elif expires_at <= current_time:
        raise ValueError("resource capability expiry must be in the future")
    target = ResourceTarget(
        source_id=source_id,
        revision=revision,
        resource_path=normalize_resource_path(raw_resource_path),
        expires_at=expires_at,
    )
    token = encode_resource_capability(target, signing_key)
    return IssuedResourceCapability(
        token=token, url=f"/assets/v2/{token}", expires_at=expires_at
    )


def safe_media_type(resource_path: str) -> str:
    suffix = Path(resource_path).suffix.casefold()
    media_type = SAFE_MEDIA_TYPES.get(suffix)
    if media_type is None:
        raise UnsafeResourceMediaType("dictionary resource media type is not allowed")
    return media_type


def prepare_safe_asset(
    target: ResourceTarget,
    content: bytes,
    signing_key: bytes,
    *,
    now: int | None = None,
) -> SafeAsset:
    """Apply MIME policy and rewrite nested CSS with the parent's expiry."""

    current_time = int(time.time()) if now is None else now
    media_type = safe_media_type(target.resource_path)
    safe_content = content
    if media_type.startswith("text/css"):
        try:
            css = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise UnsafeResourceMediaType(
                "dictionary stylesheet encoding is not supported"
            ) from error

        def nested_url(path: str, _kind: str) -> str:
            return issue_resource_capability(
                target.source_id,
                target.revision,
                path,
                signing_key,
                now=current_time,
                expires_at=target.expires_at,
            ).url

        safe_content = rewrite_css_resources(
            css, nested_url, base_path=target.resource_path
        ).encode("utf-8")
    return SafeAsset(
        content=safe_content,
        media_type=media_type,
        cache_seconds=max(0, target.expires_at - current_time),
    )
