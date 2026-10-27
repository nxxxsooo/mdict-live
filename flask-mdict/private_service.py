"""Fail-closed private-service secrets, origins, and proxy trust."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import os
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

from citations import derive_purpose_key
from werkzeug.middleware.proxy_fix import ProxyFix


FORWARDED_ENVIRONMENT_KEYS = (
    "HTTP_X_FORWARDED_FOR",
    "HTTP_X_FORWARDED_PROTO",
    "HTTP_X_FORWARDED_HOST",
    "HTTP_X_FORWARDED_PORT",
    "HTTP_X_FORWARDED_PREFIX",
)


class PrivateServiceConfigurationError(RuntimeError):
    """Raised when v2 cannot start without weakening its private boundary."""


@dataclass(frozen=True, slots=True)
class PrivateServiceSettings:
    bearer_token: bytes
    citation_signing_key: bytes
    asset_signing_key: bytes
    cors_origins: frozenset[str]


def _read_secret_file(path_value: str, setting_name: str) -> bytes:
    try:
        value = Path(path_value).read_bytes().strip()
    except OSError as error:
        raise PrivateServiceConfigurationError(
            f"{setting_name} could not be read"
        ) from error
    if not value:
        raise PrivateServiceConfigurationError(f"{setting_name} is empty")
    return value


def _load_secret(
    environ: Mapping[str, str], direct_name: str, file_name: str
) -> bytes | None:
    file_value = environ.get(file_name, "").strip()
    if file_value:
        return _read_secret_file(file_value, file_name)
    direct_value = environ.get(direct_name, "")
    return direct_value.encode() if direct_value else None


def _parse_cors_origins(value: str) -> frozenset[str]:
    origins = frozenset(origin.strip() for origin in value.split(",") if origin.strip())
    for origin in origins:
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise PrivateServiceConfigurationError(
                "MDICT_CORS_ORIGINS must contain exact HTTP(S) origins"
            )
    return frozenset(origin.rstrip("/") for origin in origins)


def load_private_service_settings(
    environ: Mapping[str, str] | None = None,
) -> PrivateServiceSettings:
    environment = os.environ if environ is None else environ
    bearer_token = _load_secret(
        environment, "MDICT_LIVE_TOKEN", "MDICT_LIVE_TOKEN_FILE"
    )
    if bearer_token is None:
        raise PrivateServiceConfigurationError(
            "v2 requires MDICT_LIVE_TOKEN or MDICT_LIVE_TOKEN_FILE on every bind"
        )
    if len(bearer_token) < 32:
        raise PrivateServiceConfigurationError(
            "the v2 bearer token must contain at least 32 bytes"
        )
    signing_secret = _load_secret(
        environment, "MDICT_SIGNING_KEY", "MDICT_SIGNING_KEY_FILE"
    ) or bearer_token
    if len(signing_secret) < 32:
        raise PrivateServiceConfigurationError(
            "the signing key must contain at least 32 bytes"
        )
    return PrivateServiceSettings(
        bearer_token=bearer_token,
        citation_signing_key=derive_purpose_key(signing_secret, "citations"),
        asset_signing_key=derive_purpose_key(signing_secret, "assets"),
        cors_origins=_parse_cors_origins(environment.get("MDICT_CORS_ORIGINS", "")),
    )


def parse_proxy_configuration(
    environ: Mapping[str, str] | None = None,
) -> tuple[int, tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]]:
    environment = os.environ if environ is None else environ
    raw_hops = environment.get("MDICT_TRUSTED_PROXY_HOPS", "0").strip() or "0"
    try:
        hops = int(raw_hops)
    except ValueError as error:
        raise PrivateServiceConfigurationError(
            "MDICT_TRUSTED_PROXY_HOPS must be a non-negative integer"
        ) from error
    if hops < 0 or hops > 16:
        raise PrivateServiceConfigurationError(
            "MDICT_TRUSTED_PROXY_HOPS must be between 0 and 16"
        )
    networks = []
    for value in environment.get("MDICT_TRUSTED_PROXY_CIDRS", "").split(","):
        value = value.strip()
        if not value:
            continue
        try:
            networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError as error:
            raise PrivateServiceConfigurationError(
                "MDICT_TRUSTED_PROXY_CIDRS contains an invalid network"
            ) from error
    return hops, tuple(networks)


class TrustedProxyMiddleware:
    """Apply ProxyFix only when the immediate peer is inside the trust boundary."""

    def __init__(
        self,
        application,
        *,
        hops: int,
        networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (),
    ) -> None:
        self.application = application
        self.hops = hops
        self.networks = networks
        self.proxy_application = ProxyFix(
            application,
            x_for=hops,
            x_proto=hops,
            x_host=hops,
            x_port=hops,
            x_prefix=hops,
        )

    def _trusted(self, remote_address: str | None) -> bool:
        if self.hops == 0 or not remote_address:
            return False
        if not self.networks:
            return True
        try:
            address = ipaddress.ip_address(remote_address)
        except ValueError:
            return False
        return any(address in network for network in self.networks)

    def __call__(self, environ, start_response):
        if self._trusted(environ.get("REMOTE_ADDR")):
            return self.proxy_application(environ, start_response)
        for key in FORWARDED_ENVIRONMENT_KEYS:
            environ.pop(key, None)
        return self.application(environ, start_response)


def configure_proxy_middleware(
    application,
    environ: Mapping[str, str] | None = None,
):
    hops, networks = parse_proxy_configuration(environ)
    return TrustedProxyMiddleware(application, hops=hops, networks=networks)
