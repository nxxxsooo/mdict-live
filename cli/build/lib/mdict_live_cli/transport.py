"""Version-checked standard-library HTTP transport."""

from __future__ import annotations

import json
import socket
import sys
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .config import ConnectionConfig
from .errors import (
    AuthenticationError,
    CompatibilityError,
    ServerError,
    TransportError,
)


API_VERSION = "2.0"
JsonObject = dict[str, Any]
OpenFunction = Callable[..., Any]


def redact_url(url: str) -> str:
    parsed = urlsplit(url)
    hostname = parsed.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    port = f":{parsed.port}" if parsed.port else ""
    return urlunsplit((parsed.scheme, f"{hostname}{port}", parsed.path, "", ""))


class HttpClient:
    def __init__(
        self,
        config: ConnectionConfig,
        *,
        verbose: bool = False,
        opener: OpenFunction = urlopen,
    ):
        self.config = config
        self.verbose = verbose
        self._opener = opener
        self._compatible = False

    def _url(self, path: str, query: list[tuple[str, str]] | None = None) -> str:
        url = f"{self.config.url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        return url

    def _diagnostic(self, text: str) -> None:
        if self.verbose:
            print(text, file=sys.stderr)

    def request(
        self,
        method: str,
        path: str,
        *,
        query: list[tuple[str, str]] | None = None,
        body: JsonObject | None = None,
        authenticated: bool = True,
        envelope: bool = True,
    ) -> JsonObject:
        url = self._url(path, query)
        headers = {"Accept": "application/json", "User-Agent": "mdict-live-cli/2"}
        if authenticated:
            if not self.config.token:
                raise AuthenticationError("Authentication token is unavailable.")
            headers["Authorization"] = f"Bearer {self.config.token}"
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)
        safe_url = redact_url(url)
        started = time.monotonic()
        self._diagnostic(f"request method={method} url={safe_url}")
        try:
            with self._opener(request, timeout=self.config.timeout_seconds) as response:
                status = int(response.status)
                raw = response.read()
        except HTTPError as error:
            raw = error.read()
            payload = self._decode_json(raw, error.status, safe_url)
            request_id, code, message = self._error_fields(payload)
            self._diagnostic(
                f"response status={error.status} elapsed_ms={int((time.monotonic() - started) * 1000)}"
                + (f" request_id={request_id}" if request_id else "")
            )
            if error.status in {401, 403}:
                raise AuthenticationError("Authentication failed.", request_id=request_id) from error
            raise ServerError(
                message or f"Server rejected the request with HTTP {error.status}.",
                status=error.status,
                server_code=code,
                request_id=request_id,
            ) from error
        except (URLError, TimeoutError, socket.timeout, OSError) as error:
            self._diagnostic(
                f"transport_error url={safe_url} elapsed_ms={int((time.monotonic() - started) * 1000)}"
            )
            reason = "timeout" if isinstance(error, (TimeoutError, socket.timeout)) else "unreachable"
            if isinstance(error, URLError) and isinstance(error.reason, (TimeoutError, socket.timeout)):
                reason = "timeout"
            raise TransportError(f"Service transport failed ({reason}).") from error
        self._diagnostic(
            f"response status={status} elapsed_ms={int((time.monotonic() - started) * 1000)}"
        )
        payload = self._decode_json(raw, status, safe_url)
        if envelope:
            self._validate_envelope(payload)
        return payload

    @staticmethod
    def _decode_json(raw: bytes, status: int, safe_url: str) -> JsonObject:
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CompatibilityError(
                f"Server returned non-JSON data for HTTP {status} at {safe_url}."
            ) from error
        if not isinstance(payload, dict):
            raise CompatibilityError("Server JSON response is not an object.")
        return payload

    @staticmethod
    def _error_fields(payload: JsonObject) -> tuple[str | None, str | None, str | None]:
        request_id = payload.get("request_id") if isinstance(payload.get("request_id"), str) else None
        error = payload.get("error")
        if not isinstance(error, dict):
            return request_id, None, None
        code = error.get("code") if isinstance(error.get("code"), str) else None
        message = error.get("message") if isinstance(error.get("message"), str) else None
        return request_id, code, message

    @staticmethod
    def _validate_envelope(payload: JsonObject) -> None:
        if payload.get("api_version") != API_VERSION:
            raise CompatibilityError(
                f"Server API version is incompatible; expected {API_VERSION}."
            )
        if not isinstance(payload.get("request_id"), str):
            raise CompatibilityError("Server response is missing a request identifier.")
        if "data" not in payload and "error" not in payload:
            raise CompatibilityError("Server response is not a v2 envelope.")

    def ensure_compatible(self) -> JsonObject:
        if self._compatible:
            return {}
        discovery = self.request("GET", "/api/v2")
        data = discovery.get("data")
        if not isinstance(data, dict) or data.get("api_version") != API_VERSION:
            raise CompatibilityError(
                f"Server discovery is incompatible; expected API {API_VERSION}."
            )
        self._compatible = True
        return discovery

    def api_request(self, method: str, path: str, **kwargs: Any) -> JsonObject:
        self.ensure_compatible()
        return self.request(method, path, **kwargs)

    def health(self, details: bool = False) -> JsonObject:
        live = self.request("GET", "/health/live", authenticated=False, envelope=False)
        ready = self.request("GET", "/health/ready", authenticated=False, envelope=False)
        result: JsonObject = {"liveness": live, "readiness": ready}
        if details:
            self.ensure_compatible()
            result["status"] = self.request("GET", "/api/v2/status")
        return result

    def sources(self) -> JsonObject:
        return self.api_request("GET", "/api/v2/sources")

    def lookup(
        self,
        query_text: str,
        source_ids: tuple[str, ...],
        *,
        record_history: bool,
    ) -> JsonObject:
        if record_history:
            body: JsonObject = {
                "query": query_text,
                "representations": ["text"],
                "record_history": True,
            }
            if source_ids:
                body["source_ids"] = list(source_ids)
            return self.api_request("POST", "/api/v2/lookup", body=body)
        query = [("q", query_text), ("representation", "text")]
        query.extend(("source_id", source_id) for source_id in source_ids)
        return self.api_request("GET", "/api/v2/lookup", query=query)

    def resolve(self, token: str) -> JsonObject:
        return self.api_request(
            "GET", f"/api/v2/citations/{quote(token, safe='')}"
        )

    def suggest(self, prefix: str, *, fuzzy: bool) -> JsonObject:
        query = [("prefix", prefix)]
        if fuzzy:
            query.append(("fuzzy", "true"))
        return self.api_request("GET", "/api/v2/suggestions", query=query)
