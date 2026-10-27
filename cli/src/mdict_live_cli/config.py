"""Cross-platform profile and secret resolution."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import stat
import tomllib
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

from .errors import ConfigurationError


DEFAULT_URL = "http://127.0.0.1:5248"
DEFAULT_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True, slots=True)
class Profile:
    name: str
    url: str | None = None
    token_file: Path | None = None
    timeout_seconds: float | None = None
    sources: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ConnectionConfig:
    profile_name: str
    url: str
    token: str | None
    timeout_seconds: float
    sources: tuple[str, ...]
    config_path: Path


def default_config_path(env: Mapping[str, str] | None = None) -> Path:
    values = os.environ if env is None else env
    if values.get("MDICT_LIVE_CONFIG"):
        return Path(values["MDICT_LIVE_CONFIG"]).expanduser()
    if os.name == "nt":
        appdata = values.get("APPDATA")
        if appdata:
            return Path(appdata) / "mdict-live" / "config.toml"
    xdg = values.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg).expanduser() / "mdict-live" / "config.toml"
    return Path.home() / ".config" / "mdict-live" / "config.toml"


def _profile_from_table(name: str, table: object, config_path: Path) -> Profile:
    if not isinstance(table, dict):
        raise ConfigurationError(f"Profile {name!r} must be a TOML table.")
    allowed = {"url", "token_file", "timeout_seconds", "sources"}
    unknown = set(table) - allowed
    if unknown:
        raise ConfigurationError(
            f"Profile {name!r} has unsupported fields: {', '.join(sorted(unknown))}."
        )
    url = table.get("url")
    token_file = table.get("token_file")
    timeout = table.get("timeout_seconds")
    sources = table.get("sources", [])
    if url is not None and not isinstance(url, str):
        raise ConfigurationError(f"Profile {name!r} url must be a string.")
    if token_file is not None and not isinstance(token_file, str):
        raise ConfigurationError(f"Profile {name!r} token_file must be a string.")
    if timeout is not None and (
        isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0
    ):
        raise ConfigurationError(f"Profile {name!r} timeout_seconds must be positive.")
    if not isinstance(sources, list) or not all(
        isinstance(source, str) and source.strip() for source in sources
    ):
        raise ConfigurationError(f"Profile {name!r} sources must be non-empty strings.")
    resolved_token_file = None
    if token_file:
        candidate = Path(token_file).expanduser()
        resolved_token_file = (
            candidate if candidate.is_absolute() else config_path.parent / candidate
        )
    return Profile(
        name=name,
        url=url,
        token_file=resolved_token_file,
        timeout_seconds=float(timeout) if timeout is not None else None,
        sources=tuple(source.strip() for source in sources),
    )


def load_profiles(config_path: Path) -> tuple[str, dict[str, Profile]]:
    if not config_path.exists():
        return "default", {}
    try:
        document = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise ConfigurationError(f"Cannot read MdictLive configuration: {error}.") from error
    if not isinstance(document, dict):
        raise ConfigurationError("MdictLive configuration must be a TOML table.")
    unknown = set(document) - {"default_profile", "profiles"}
    if unknown:
        raise ConfigurationError(
            f"Configuration has unsupported fields: {', '.join(sorted(unknown))}."
        )
    default_profile = document.get("default_profile", "default")
    if not isinstance(default_profile, str) or not default_profile.strip():
        raise ConfigurationError("default_profile must be a non-empty string.")
    tables = document.get("profiles", {})
    if not isinstance(tables, dict):
        raise ConfigurationError("profiles must be a TOML table.")
    profiles = {
        name: _profile_from_table(name, table, config_path)
        for name, table in tables.items()
        if isinstance(name, str)
    }
    return default_profile.strip(), profiles


def _validated_url(raw_url: str) -> str:
    value = raw_url.strip().rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ConfigurationError("Service URL must be an absolute http:// or https:// URL.")
    if parsed.username is not None or parsed.password is not None:
        raise ConfigurationError("Service URL must not contain credentials.")
    if parsed.query or parsed.fragment:
        raise ConfigurationError("Service URL must not contain a query or fragment.")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _positive_timeout(raw: str | float | int) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError) as error:
        raise ConfigurationError("Timeout must be a positive number of seconds.") from error
    if value <= 0 or value > 3600:
        raise ConfigurationError("Timeout must be greater than 0 and at most 3600 seconds.")
    return value


def _read_token_file(path: Path) -> str:
    try:
        file_stat = path.stat()
        if not stat.S_ISREG(file_stat.st_mode):
            raise ConfigurationError("Token file must be a regular file.")
        if os.name != "nt" and stat.S_IMODE(file_stat.st_mode) & 0o077:
            raise ConfigurationError("Token file permissions are too broad; use mode 0600.")
        token = path.read_text(encoding="utf-8").strip()
    except ConfigurationError:
        raise
    except (OSError, UnicodeError) as error:
        raise ConfigurationError("Cannot read the configured token file.") from error
    if not token:
        raise ConfigurationError("The configured token file is empty.")
    return token


def resolve_connection(
    args: Any,
    *,
    env: Mapping[str, str] | None = None,
    require_token: bool,
) -> ConnectionConfig:
    values = os.environ if env is None else env
    config_path = default_config_path(values)
    configured_default, profiles = load_profiles(config_path)
    profile_name = (
        getattr(args, "profile", None)
        or values.get("MDICT_LIVE_PROFILE")
        or configured_default
    )
    profile = profiles.get(profile_name)
    if profile is None:
        if profile_name != "default" or profiles:
            raise ConfigurationError(f"MdictLive profile {profile_name!r} does not exist.")
        profile = Profile("default")

    url = _validated_url(
        getattr(args, "url", None)
        or values.get("MDICT_LIVE_URL")
        or profile.url
        or DEFAULT_URL
    )
    timeout = _positive_timeout(
        getattr(args, "timeout", None)
        or values.get("MDICT_LIVE_TIMEOUT")
        or profile.timeout_seconds
        or DEFAULT_TIMEOUT_SECONDS
    )

    token: str | None = None
    explicit_token = getattr(args, "token", None)
    explicit_token_file = getattr(args, "token_file", None)
    if explicit_token:
        token = explicit_token.strip()
    elif explicit_token_file:
        token = _read_token_file(Path(explicit_token_file).expanduser())
    elif values.get("MDICT_LIVE_TOKEN"):
        token = values["MDICT_LIVE_TOKEN"].strip()
    elif profile.token_file:
        token = _read_token_file(profile.token_file)
    if token == "":
        token = None
    if require_token and token is None:
        raise ConfigurationError(
            "No bearer token is configured. Set MDICT_LIVE_TOKEN or use a protected token file."
        )
    return ConnectionConfig(
        profile_name=profile_name,
        url=url,
        token=token,
        timeout_seconds=timeout,
        sources=profile.sources,
        config_path=config_path,
    )
