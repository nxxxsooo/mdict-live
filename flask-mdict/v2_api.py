"""Authenticated Flask boundary for the MdictLive v2 domain services."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import hmac
import secrets
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from flask import Blueprint, Flask, Response, g, jsonify, make_response, request
from werkzeug.exceptions import HTTPException

from citations import (
    CitationGone,
    CitationTarget,
    InvalidCitationToken,
    citation_reference,
    decode_citation_token,
    validate_citation_availability,
)
from domain import (
    API_SCHEMA_VERSION,
    EntryRecord,
    LookupBounds,
    LookupProgress,
    LookupResult,
    MetadataRecord,
    MetadataResult,
    SourceRecord,
    SuggestionResult,
    TextBlockRecord,
)
from lookup_services import (
    AllSourcesFailed,
    LookupService,
    LookupValidationError,
    MetadataService,
    SourceCatalog,
    SuggestionService,
    UnknownSourceSelection,
)
from private_service import PrivateServiceSettings
from resource_capabilities import (
    InvalidResourceCapability,
    ResourceTarget,
    UnsafeResourceMediaType,
    decode_resource_capability,
    prepare_safe_asset,
)


SourceUpdater = Callable[[str, bool | None, int | None], tuple[bool, SourceRecord]]
CitationResolver = Callable[[CitationTarget], dict[str, Any] | None]
AssetLoader = Callable[[ResourceTarget], bytes | None]


def _ready() -> bool:
    return True


def _status() -> dict[str, Any]:
    return {
        "state": "ready",
        "sources": {"available": 0, "unavailable": 0, "scan_state": "idle"},
        "storage": {
            "library_readable": True,
            "data_writable": True,
            "index_writable": True,
        },
        "capabilities": {"metadata": False, "external_cache": False},
    }


@dataclass(slots=True)
class V2Dependencies:
    catalog: SourceCatalog
    lookup_service: LookupService
    suggestion_service: SuggestionService
    metadata_service: MetadataService
    source_updater: SourceUpdater | None = None
    citation_resolver: CitationResolver | None = None
    asset_loader: AssetLoader | None = None
    readiness: Callable[[], bool] = _ready
    status_provider: Callable[[], dict[str, Any]] = _status
    legacy_source_ids: dict[str, str] = field(default_factory=dict)


def _request_id() -> str:
    return f"req_{secrets.token_urlsafe(12)}"


def _success(data: object, status: int = 200):
    return (
        jsonify(
            {
                "api_version": API_SCHEMA_VERSION,
                "request_id": g.request_id,
                "data": data,
            }
        ),
        status,
    )


def _error(
    status: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
):
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return (
        jsonify(
            {
                "api_version": API_SCHEMA_VERSION,
                "request_id": getattr(g, "request_id", _request_id()),
                "error": error,
            }
        ),
        status,
    )


def _source_json(source: SourceRecord) -> dict[str, Any]:
    return {
        "source_id": source.source_id,
        "revision": source.revision,
        "title": source.title,
        "enabled": source.enabled,
        "order": source.sort_order,
        "available": source.available,
        "supported_representations": list(source.supported_representations),
        "unavailable_reason": source.unavailable_reason,
    }


def _citation_json(reference) -> dict[str, str]:
    return {"uri": reference.uri, "token": reference.token}


def _block_json(block: TextBlockRecord) -> dict[str, Any]:
    return {
        "block_id": block.block_id,
        "order": block.order,
        "text": block.text,
        "citation": _citation_json(block.citation),
    }


def _entry_json(entry: EntryRecord) -> dict[str, Any]:
    data: dict[str, Any] = {
        "source_id": entry.source_id,
        "revision": entry.revision,
        "entry_id": entry.entry_id,
        "headword": entry.headword,
        "record_ordinal": entry.record_ordinal,
        "citation": _citation_json(entry.citation),
    }
    if entry.html is not None:
        data["html"] = entry.html
    if entry.text_blocks:
        data["text_blocks"] = [_block_json(block) for block in entry.text_blocks]
    return data


def _progress_json(progress: LookupProgress) -> dict[str, Any]:
    return {
        "selected_source_ids": list(progress.selected_source_ids),
        "completed_source_ids": list(progress.completed_source_ids),
        "failed_sources": [
            {
                "source_id": failure.source_id,
                "code": failure.code,
                "message": failure.message,
            }
            for failure in progress.failed_sources
        ],
        "omitted_source_ids": list(progress.omitted_source_ids),
    }


def _bounds_json(bounds: LookupBounds) -> dict[str, int]:
    return {
        "source_limit": bounds.source_limit,
        "entry_limit": bounds.entry_limit,
        "text_response_bytes": bounds.text_response_bytes,
        "text_entry_bytes": bounds.text_entry_bytes,
        "html_response_bytes": bounds.html_response_bytes,
    }


def _lookup_json(result: LookupResult) -> dict[str, Any]:
    truncation = None
    if result.truncated:
        truncation = {
            "causes": list(result.truncation_causes),
            "resumable_source_ids": list(result.progress.omitted_source_ids),
        }
    return {
        "query": result.query,
        "normalized_query": result.normalized_query,
        "representations": list(result.representations),
        "entries": [_entry_json(entry) for entry in result.entries],
        "partial": result.partial,
        "truncated": result.truncated,
        "truncation": truncation,
        "progress": _progress_json(result.progress),
        "bounds": _bounds_json(result.bounds),
        "elapsed_ms": round(result.elapsed_ms, 3),
        "history_recorded": result.history_recorded,
    }


def _metadata_record_json(record: MetadataRecord) -> dict[str, Any]:
    data: dict[str, Any] = {
        "query": record.query,
        "dataset": {
            "id": record.dataset.dataset_id,
            "title": record.dataset.title,
            "version": record.dataset.version,
        },
    }
    for name in ("phonetic", "frequency", "definition", "translation"):
        value = getattr(record, name)
        if value is not None:
            data[name] = value
    if record.tags:
        data["tags"] = list(record.tags)
    if record.inflections:
        data["inflections"] = dict(record.inflections)
    return data


def _metadata_json(result: MetadataResult) -> dict[str, Any]:
    return {
        "available": result.available,
        "query": result.query,
        "records": [_metadata_record_json(record) for record in result.records],
        "unavailable_reason": result.unavailable_reason,
    }


def _suggestion_json(result: SuggestionResult) -> dict[str, Any]:
    suggestions = []
    for suggestion in result.suggestions:
        item: dict[str, Any] = {
            "headword": suggestion.headword,
            "source_ids": list(suggestion.source_ids),
            "kind": suggestion.kind,
        }
        if suggestion.score is not None:
            item["score"] = suggestion.score
        suggestions.append(item)
    return {
        "prefix": result.prefix,
        "suggestions": suggestions,
        "fuzzy": result.fuzzy,
        "limit": result.limit,
        "truncated": result.truncated,
    }


def _parse_integer(value: str | None, field_name: str) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as error:
        raise LookupValidationError(field_name, f"{field_name} must be an integer") from error


def _redact_status(value: object, key: str = "") -> object:
    lowered_key = key.casefold()
    if any(
        marker in lowered_key
        for marker in ("token", "secret", "password", "credential", "path", "directory")
    ):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {name: _redact_status(item, str(name)) for name, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_status(item, key) for item in value]
    if isinstance(value, str) and "url" in lowered_key:
        parsed = urlsplit(value)
        if parsed.username or parsed.password:
            host = parsed.hostname or ""
            if parsed.port:
                host = f"{host}:{parsed.port}"
            return urlunsplit((parsed.scheme, host, parsed.path, parsed.query, parsed.fragment))
    return value


def install_v2_api(
    app: Flask,
    dependencies: V2Dependencies,
    settings: PrivateServiceSettings,
    *,
    request_id_factory: Callable[[], str] = _request_id,
) -> None:
    api = Blueprint("api_v2", __name__, url_prefix="/api/v2")
    public = Blueprint("v2_public", __name__)
    allowed_methods = {"GET", "POST", "PATCH", "OPTIONS"}
    allowed_headers = {"authorization", "content-type"}

    @api.before_request
    def protect_api():
        g.request_id = request_id_factory()
        origin = request.headers.get("Origin")
        if request.method == "OPTIONS":
            requested_method = request.headers.get(
                "Access-Control-Request-Method", ""
            ).upper()
            requested_headers = {
                header.strip().casefold()
                for header in request.headers.get(
                    "Access-Control-Request-Headers", ""
                ).split(",")
                if header.strip()
            }
            if (
                not origin
                or origin not in settings.cors_origins
                or requested_method not in allowed_methods
                or not requested_headers <= allowed_headers
            ):
                return _error(403, "origin_not_allowed", "Browser origin is not allowed.")
            return make_response("", 204)
        if origin and origin not in settings.cors_origins and request.method in {
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        }:
            return _error(403, "origin_not_allowed", "Browser origin is not allowed.")
        authorization = request.headers.get("Authorization", "")
        scheme, separator, candidate = authorization.partition(" ")
        valid = (
            separator == " "
            and scheme.casefold() == "bearer"
            and bool(candidate)
            and hmac.compare_digest(candidate.encode(), settings.bearer_token)
        )
        if not valid:
            return _error(401, "authentication_required", "Authentication failed.")
        return None

    @api.after_request
    def apply_api_cors(response: Response):
        origin = request.headers.get("Origin")
        if origin and origin in settings.cors_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            if request.method == "OPTIONS":
                response.headers["Access-Control-Allow-Methods"] = ", ".join(
                    sorted(allowed_methods - {"OPTIONS"})
                )
                response.headers["Access-Control-Allow-Headers"] = ", ".join(
                    sorted(allowed_headers)
                )
                response.headers["Access-Control-Max-Age"] = "600"
        return response

    @api.get("")
    def discovery():
        limits = dependencies.lookup_service.bounds
        return _success(
            {
                "api_version": API_SCHEMA_VERSION,
                "links": {
                    "self": "/api/v2",
                    "status": "/api/v2/status",
                    "sources": "/api/v2/sources",
                    "lookup": "/api/v2/lookup",
                    "suggestions": "/api/v2/suggestions",
                    "metadata": "/api/v2/metadata",
                },
                "limits": {
                    "query_characters": limits.query_characters,
                    "selected_sources": limits.source_limit,
                    "returned_entries": limits.entry_limit,
                    "text_response_bytes": limits.text_response_bytes,
                    "text_entry_bytes": limits.text_entry_bytes,
                    "html_response_bytes": limits.html_response_bytes,
                    "suggestions_default": dependencies.suggestion_service.default_limit,
                    "suggestions_maximum": dependencies.suggestion_service.maximum_limit,
                    "agent_evidence_bytes": 32768,
                },
            }
        )

    @api.get("/status")
    def service_status():
        status = dict(dependencies.status_provider())
        status.setdefault("api_version", API_SCHEMA_VERSION)
        limits = dependencies.lookup_service.bounds
        status["limits"] = {
            "query_characters": limits.query_characters,
            "selected_sources": limits.source_limit,
            "returned_entries": limits.entry_limit,
            "text_response_bytes": limits.text_response_bytes,
            "text_entry_bytes": limits.text_entry_bytes,
            "html_response_bytes": limits.html_response_bytes,
            "suggestions_default": dependencies.suggestion_service.default_limit,
            "suggestions_maximum": dependencies.suggestion_service.maximum_limit,
            "agent_evidence_bytes": 32768,
        }
        return _success(_redact_status(status))

    @api.get("/sources")
    def list_sources():
        return _success(
            {"sources": [_source_json(source) for source in dependencies.catalog.list_sources()]}
        )

    @api.patch("/sources/<source_id>")
    def update_source(source_id: str):
        if not request.is_json:
            return _error(415, "unsupported_media_type", "Content-Type must be application/json.")
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _error(422, "invalid_request", "JSON body must be an object.")
        unknown_fields = sorted(set(payload) - {"enabled", "order"})
        if unknown_fields or not payload:
            return _error(
                422,
                "invalid_request",
                "Source update fields are invalid.",
                {"fields": unknown_fields or ["enabled", "order"]},
            )
        enabled = payload.get("enabled")
        order = payload.get("order")
        if enabled is not None and not isinstance(enabled, bool):
            return _error(422, "invalid_request", "enabled must be a boolean.")
        if order is not None and (not isinstance(order, int) or isinstance(order, bool) or order < 0):
            return _error(422, "invalid_request", "order must be a non-negative integer.")
        if dependencies.source_updater is None:
            return _error(503, "source_update_unavailable", "Source updates are unavailable.")
        try:
            changed, source = dependencies.source_updater(source_id, enabled, order)
        except KeyError:
            return _error(404, "source_not_found", "Dictionary source was not found.")
        return _success({"changed": changed, "source": _source_json(source)})

    @api.route("/lookup", methods=["GET", "POST"])
    def lookup():
        if request.method == "GET":
            allowed = {"q", "source_id", "representation", "limit"}
            unknown = sorted(set(request.args) - allowed)
            if unknown:
                return _error(
                    422,
                    "invalid_request",
                    "Lookup query parameters are invalid.",
                    {"fields": unknown},
                )
            query = request.args.get("q")
            source_ids = request.args.getlist("source_id") or None
            representations = request.args.getlist("representation") or ("html", "text")
            try:
                limit = _parse_integer(request.args.get("limit"), "limit")
            except LookupValidationError as error:
                return _error(422, "invalid_request", error.message, {error.field: error.message})
            record_history = False
        else:
            if not request.is_json:
                return _error(415, "unsupported_media_type", "Content-Type must be application/json.")
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                return _error(422, "invalid_request", "JSON body must be an object.")
            unknown = sorted(
                set(payload)
                - {"query", "source_ids", "representations", "limit", "record_history"}
            )
            if unknown:
                return _error(
                    422,
                    "invalid_request",
                    "Lookup request fields are invalid.",
                    {"fields": unknown},
                )
            query = payload.get("query")
            source_ids = payload.get("source_ids")
            representations = payload.get("representations", ["html", "text"])
            limit = payload.get("limit")
            record_history = payload.get("record_history", False)
            if source_ids is not None and not isinstance(source_ids, list):
                return _error(422, "invalid_request", "source_ids must be an array.")
            if source_ids is not None and not all(
                isinstance(source_id, str) for source_id in source_ids
            ):
                return _error(422, "invalid_request", "source_ids must contain strings.")
            if not isinstance(representations, list):
                return _error(422, "invalid_request", "representations must be an array.")
            if not all(isinstance(value, str) for value in representations):
                return _error(422, "invalid_request", "representations must contain strings.")
            if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool)):
                return _error(422, "invalid_request", "limit must be an integer.")
            if not isinstance(record_history, bool):
                return _error(422, "invalid_request", "record_history must be a boolean.")
        try:
            result = dependencies.lookup_service.lookup(
                query,
                source_ids=source_ids,
                representations=representations,
                entry_limit=limit,
                record_history=record_history,
            )
        except UnknownSourceSelection as error:
            return _error(
                422,
                "unknown_source",
                "One or more dictionary sources are unknown.",
                {"source_ids": list(error.source_ids)},
            )
        except LookupValidationError as error:
            return _error(422, "invalid_request", error.message, {error.field: error.message})
        except AllSourcesFailed as error:
            return _error(
                503,
                "lookup_unavailable",
                "No selected dictionary source completed.",
                {"progress": _progress_json(error.progress)},
            )
        return _success(_lookup_json(result))

    @api.get("/suggestions")
    def suggestions():
        allowed = {"prefix", "source_id", "limit", "fuzzy"}
        unknown = sorted(set(request.args) - allowed)
        if unknown:
            return _error(422, "invalid_request", "Suggestion parameters are invalid.")
        try:
            limit = _parse_integer(request.args.get("limit"), "limit")
            fuzzy_value = request.args.get("fuzzy", "false").casefold()
            if fuzzy_value not in {"true", "false"}:
                raise LookupValidationError("fuzzy", "fuzzy must be true or false")
            result = dependencies.suggestion_service.suggest(
                request.args.get("prefix"),
                source_ids=request.args.getlist("source_id") or None,
                limit=limit,
                fuzzy=fuzzy_value == "true",
            )
        except UnknownSourceSelection as error:
            return _error(422, "unknown_source", "One or more dictionary sources are unknown.", {"source_ids": list(error.source_ids)})
        except LookupValidationError as error:
            return _error(422, "invalid_request", error.message, {error.field: error.message})
        return _success(_suggestion_json(result))

    @api.get("/metadata")
    def metadata():
        if set(request.args) - {"q"}:
            return _error(422, "invalid_request", "Metadata parameters are invalid.")
        try:
            result = dependencies.metadata_service.lookup(request.args.get("q"))
        except LookupValidationError as error:
            return _error(422, "invalid_request", error.message, {error.field: error.message})
        return _success(_metadata_json(result))

    @api.get("/citations/<citation_token>")
    def resolve_citation(citation_token: str):
        try:
            target = decode_citation_token(
                citation_token, settings.citation_signing_key
            )
        except InvalidCitationToken:
            return _error(422, "invalid_citation", "Citation is not valid.")
        mounted = {
            source.source_id: source.revision
            for source in dependencies.catalog.list_sources()
            if source.available
        }
        try:
            validate_citation_availability(target, mounted)
        except CitationGone as error:
            return _error(
                410,
                "citation_gone",
                "Cited dictionary evidence is no longer available.",
                {
                    "source_id": error.source_id,
                    "revision": error.revision,
                    "reason": error.reason,
                },
            )
        resolved = (
            dependencies.citation_resolver(target)
            if dependencies.citation_resolver is not None
            else None
        )
        if resolved is None:
            return _error(404, "citation_not_found", "Cited evidence was not found.")
        data = dict(resolved)
        data.setdefault(
            "citation",
            _citation_json(citation_reference(target, settings.citation_signing_key)),
        )
        return _success(data)

    @public.get("/health/live")
    def liveness():
        return jsonify({"status": "alive"})

    @public.get("/health/ready")
    def readiness():
        ready = bool(dependencies.readiness())
        return (
            jsonify({"status": "ready" if ready else "initializing", "ready": ready}),
            200 if ready else 503,
        )

    @public.get("/assets/v2/<capability>")
    def asset(capability: str):
        try:
            target = decode_resource_capability(
                capability, settings.asset_signing_key
            )
        except InvalidResourceCapability:
            g.request_id = request_id_factory()
            return _error(401, "invalid_capability", "Resource capability is invalid.")
        source = next(
            (
                source
                for source in dependencies.catalog.list_sources()
                if source.source_id == target.source_id
                and source.revision == target.revision
                and source.available
            ),
            None,
        )
        if source is None:
            g.request_id = request_id_factory()
            return _error(401, "invalid_capability", "Resource capability is invalid.")
        content = dependencies.asset_loader(target) if dependencies.asset_loader else None
        if content is None:
            g.request_id = request_id_factory()
            return _error(404, "resource_not_found", "Dictionary resource was not found.")
        try:
            safe_asset = prepare_safe_asset(
                target, content, settings.asset_signing_key
            )
        except UnsafeResourceMediaType:
            g.request_id = request_id_factory()
            return _error(415, "unsafe_media_type", "Dictionary resource type is not allowed.")
        response = make_response(safe_asset.content)
        response.headers["Content-Type"] = safe_asset.media_type
        response.headers["Cache-Control"] = f"private, max-age={safe_asset.cache_seconds}"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    @api.errorhandler(Exception)
    def api_unexpected_error(_error_value: Exception):
        g.request_id = getattr(g, "request_id", request_id_factory())
        return _error(500, "internal_error", "The request could not be completed safely.")

    app.register_blueprint(api)
    app.register_blueprint(public)

    @app.errorhandler(HTTPException)
    def v2_http_error(error: HTTPException):
        if request.path.startswith("/api/v2"):
            g.request_id = getattr(g, "request_id", request_id_factory())
            code = "not_found" if error.code == 404 else "http_error"
            return _error(error.code or 500, code, "The v2 request could not be completed.")
        return error
