from __future__ import annotations

from collections.abc import Iterator
import json
from pathlib import Path
import time

from flask import Flask
from jsonschema import Draft202012Validator, FormatChecker
import pytest
import yaml

from citations import CitationTarget, REPRESENTATION_VERSION, encode_citation_token
from domain import LookupBounds, MetadataDataset, MetadataRecord, SourceRecord
from lookup_services import LookupService, MetadataService, SourceCatalog, SuggestionService
from private_service import load_private_service_settings
from resource_capabilities import (
    ResourceTarget,
    encode_resource_capability,
    issue_resource_capability,
)
from tests.support.source_fakes import FakeDictionarySource, FakeEntryRecord
from v2_api import V2Dependencies, install_v2_api


TOKEN = "private-test-token-0123456789abcdef"
REPOSITORY_ROOT = Path(__file__).parents[2]
CONTRACT_PATH = REPOSITORY_ROOT / "contracts" / "openapi-v2.yaml"


class FixtureMetadataProvider:
    available = True
    unavailable_reason = None

    def lookup(self, query: str):
        return (
            MetadataRecord(
                query=query,
                dataset=MetadataDataset("fixture", "Fixture metadata", "1"),
                definition="A deterministic fixture definition.",
                translation="测试释义",
            ),
        )


def request_ids() -> Iterator[str]:
    index = 0
    while True:
        index += 1
        yield f"req_test_{index:04d}"


@pytest.fixture
def v2_bundle():
    source = FakeDictionarySource(
        source_id="src_fixture_primary",
        revision="rev_fixture_0001",
        title="Synthetic Fixture Dictionary",
        records={
            "right": (
                FakeEntryRecord("right", "<p>Correct as a fact.</p>", ordinal=2),
            ),
            "café / au lait": (
                FakeEntryRecord("café / au lait", "<p>Coffee with milk.</p>"),
            ),
            "rigid": (FakeEntryRecord("rigid", "<p>Not flexible.</p>"),),
        },
        resources={
            "images/diagram.png": b"synthetic-png",
            "styles/main.css": b".hero{background:url('../images/diagram.png')}",
        },
    )
    source_record = SourceRecord(
        source.source_id,
        source.revision,
        source.title,
        True,
        0,
    )
    catalog = SourceCatalog((source_record,), {source.source_id: source})
    settings = load_private_service_settings(
        {
            "MDICT_LIVE_TOKEN": TOKEN,
            "MDICT_CORS_ORIGINS": "https://reader.example",
        }
    )
    history: list[str] = []
    lookup = LookupService(
        catalog,
        citation_signing_key=settings.citation_signing_key,
        asset_signing_key=settings.asset_signing_key,
        history_recorder=history.append,
    )
    suggestions = SuggestionService(catalog)
    metadata = MetadataService(FixtureMetadataProvider())
    ready = {"value": True}
    current_source = {"value": source_record}

    def update_source(
        source_id: str, enabled: bool | None, order: int | None
    ) -> tuple[bool, SourceRecord]:
        if source_id != current_source["value"].source_id:
            raise KeyError(source_id)
        before = current_source["value"]
        after = SourceRecord(
            source_id=before.source_id,
            revision=before.revision,
            title=before.title,
            enabled=before.enabled if enabled is None else enabled,
            sort_order=before.sort_order if order is None else order,
            available=before.available,
            unavailable_reason=before.unavailable_reason,
        )
        current_source["value"] = after
        return after != before, after

    def resolve_citation(target: CitationTarget):
        if not target.entry_id.startswith("ent_"):
            return None
        return {
            "source": {
                "source_id": source.source_id,
                "revision": source.revision,
                "title": source.title,
            },
            "entry_id": target.entry_id,
            "headword": "right",
            "representation_version": target.representation_version,
            "text_block": None,
        }

    def load_asset(target: ResourceTarget):
        return source.resources.get(target.resource_path)

    def status():
        return {
            "state": "ready",
            "sources": {"available": 1, "unavailable": 0, "scan_state": "idle"},
            "storage": {
                "library_readable": True,
                "data_writable": True,
                "index_writable": True,
            },
            "capabilities": {"metadata": True, "external_cache": False},
        }

    dependencies = V2Dependencies(
        catalog=catalog,
        lookup_service=lookup,
        suggestion_service=suggestions,
        metadata_service=metadata,
        source_updater=update_source,
        citation_resolver=resolve_citation,
        asset_loader=load_asset,
        readiness=lambda: ready["value"],
        status_provider=status,
    )
    app = Flask(__name__)
    app.config["TESTING"] = True
    ids = request_ids()
    install_v2_api(app, dependencies, settings, request_id_factory=lambda: next(ids))
    try:
        yield {
            "app": app,
            "client": app.test_client(),
            "settings": settings,
            "dependencies": dependencies,
            "source": source,
            "history": history,
            "ready": ready,
        }
    finally:
        lookup.close()


def auth_headers(**extra: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}", **extra}


def assert_component_schema(payload: object, schema_name: str) -> None:
    document = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$ref": f"#/components/schemas/{schema_name}",
        "components": document["components"],
    }
    errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(payload)
    )
    assert not errors, "\n".join(error.message for error in errors)


def test_health_is_minimal_unauthenticated_and_readiness_is_distinct(v2_bundle) -> None:
    client = v2_bundle["client"]

    live = client.get("/health/live")
    ready = client.get("/health/ready")
    v2_bundle["ready"]["value"] = False
    initializing = client.get("/health/ready")

    assert live.status_code == 200
    assert live.json == {"status": "alive"}
    assert ready.status_code == 200
    assert ready.json == {"status": "ready", "ready": True}
    assert initializing.status_code == 503
    assert initializing.json == {"status": "initializing", "ready": False}
    assert "Synthetic" not in json.dumps(initializing.json)


@pytest.mark.parametrize(
    "authorization", (None, "Bearer wrong", "Basic private-test-token")
)
def test_protected_routes_return_same_generic_authentication_error(
    v2_bundle, authorization: str | None
) -> None:
    headers = {} if authorization is None else {"Authorization": authorization}

    response = v2_bundle["client"].get("/api/v2", headers=headers)

    assert response.status_code == 401
    assert response.json["error"] == {
        "code": "authentication_required",
        "message": "Authentication failed.",
    }
    assert TOKEN not in response.get_data(as_text=True)
    assert_component_schema(response.json, "ErrorEnvelope")


def test_discovery_is_authenticated_and_matches_contract(v2_bundle) -> None:
    response = v2_bundle["client"].get("/api/v2", headers=auth_headers())

    assert response.status_code == 200
    assert response.json["data"]["api_version"] == "2.0"
    assert response.json["data"]["links"]["lookup"] == "/api/v2/lookup"
    assert response.json["data"]["limits"]["html_response_bytes"] == 4 * 1024 * 1024
    assert_component_schema(response.json, "DiscoveryResponse")


def test_cors_is_absent_for_cli_exact_for_browser_and_rejects_unknown_mutation(
    v2_bundle,
) -> None:
    client = v2_bundle["client"]

    cli = client.get("/api/v2", headers=auth_headers())
    preflight = client.options(
        "/api/v2/lookup",
        headers={
            "Origin": "https://reader.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        },
    )
    rejected = client.patch(
        "/api/v2/sources/src_fixture_primary",
        json={"enabled": False},
        headers=auth_headers(Origin="https://evil.example"),
    )

    assert "Access-Control-Allow-Origin" not in cli.headers
    assert preflight.status_code == 204
    assert preflight.headers["Access-Control-Allow-Origin"] == "https://reader.example"
    assert "authorization" in preflight.headers["Access-Control-Allow-Headers"]
    assert rejected.status_code == 403
    assert "Access-Control-Allow-Origin" not in rejected.headers


def test_sources_list_and_json_only_update_use_stable_records(v2_bundle) -> None:
    client = v2_bundle["client"]

    listed = client.get("/api/v2/sources", headers=auth_headers())
    wrong_type = client.patch(
        "/api/v2/sources/src_fixture_primary",
        data="enabled=false",
        headers=auth_headers(**{"Content-Type": "text/plain"}),
    )
    updated = client.patch(
        "/api/v2/sources/src_fixture_primary",
        json={"enabled": False, "order": 3},
        headers=auth_headers(),
    )

    assert listed.json["data"]["sources"][0]["source_id"] == "src_fixture_primary"
    assert wrong_type.status_code == 415
    assert updated.json["data"]["changed"] is True
    assert updated.json["data"]["source"]["enabled"] is False
    assert updated.json["data"]["source"]["order"] == 3
    assert_component_schema(listed.json, "SourceListResponse")
    assert_component_schema(updated.json, "SourceUpdateResponse")


def test_get_lookup_handles_unicode_phrases_and_never_records_history(v2_bundle) -> None:
    query = " cafe\u0301 / au lait "

    response = v2_bundle["client"].get(
        "/api/v2/lookup",
        query_string={"q": query, "representation": "text"},
        headers=auth_headers(),
    )

    assert response.status_code == 200
    assert response.json["data"]["normalized_query"] == "café / au lait"
    assert response.json["data"]["entries"][0]["text_blocks"][0]["text"] == "Coffee with milk."
    assert v2_bundle["history"] == []
    assert_component_schema(response.json, "LookupResponse")


def test_get_rejects_history_parameter_and_post_requires_explicit_history(v2_bundle) -> None:
    client = v2_bundle["client"]

    rejected = client.get(
        "/api/v2/lookup",
        query_string={"q": "right", "record_history": "true"},
        headers=auth_headers(),
    )
    ordinary = client.post(
        "/api/v2/lookup", json={"query": "right"}, headers=auth_headers()
    )
    recorded = client.post(
        "/api/v2/lookup",
        json={"query": "right", "record_history": True},
        headers=auth_headers(),
    )

    assert rejected.status_code == 422
    assert ordinary.json["data"]["history_recorded"] is False
    assert recorded.json["data"]["history_recorded"] is True
    assert v2_bundle["history"] == ["right"]


def test_lookup_validation_unknown_source_and_no_match_have_distinct_contracts(
    v2_bundle,
) -> None:
    client = v2_bundle["client"]

    invalid = client.get("/api/v2/lookup", headers=auth_headers())
    unknown = client.get(
        "/api/v2/lookup",
        query_string={"q": "right", "source_id": "src_unknown"},
        headers=auth_headers(),
    )
    empty = client.get(
        "/api/v2/lookup", query_string={"q": "absent"}, headers=auth_headers()
    )

    assert invalid.status_code == 422
    assert unknown.status_code == 422
    assert unknown.json["error"]["code"] == "unknown_source"
    assert empty.status_code == 200
    assert empty.json["data"]["entries"] == []
    assert empty.json["data"]["partial"] is False


def test_suggestions_and_named_metadata_match_contract(v2_bundle) -> None:
    client = v2_bundle["client"]

    suggestions = client.get(
        "/api/v2/suggestions",
        query_string={"prefix": "ri"},
        headers=auth_headers(),
    )
    metadata = client.get(
        "/api/v2/metadata", query_string={"q": "right"}, headers=auth_headers()
    )

    assert suggestions.json["data"]["suggestions"][0]["headword"] in {"right", "rigid"}
    assert metadata.json["data"]["records"][0]["dataset"]["id"] == "fixture"
    assert_component_schema(suggestions.json, "SuggestionResponse")
    assert_component_schema(metadata.json, "MetadataResponse")


def test_citation_resolution_rejects_forgery_and_returns_gone_for_stale_revision(
    v2_bundle,
) -> None:
    settings = v2_bundle["settings"]
    current = CitationTarget(
        "src_fixture_primary",
        "rev_fixture_0001",
        REPRESENTATION_VERSION,
        "ent_fixture_0001",
    )
    stale = CitationTarget(
        "src_fixture_primary",
        "rev_fixture_stale",
        REPRESENTATION_VERSION,
        "ent_fixture_0001",
    )
    current_token = encode_citation_token(current, settings.citation_signing_key)
    stale_token = encode_citation_token(stale, settings.citation_signing_key)
    forged = current_token[:-2] + ("AA" if not current_token.endswith("AA") else "BB")

    resolved = v2_bundle["client"].get(
        f"/api/v2/citations/{current_token}", headers=auth_headers()
    )
    invalid = v2_bundle["client"].get(
        f"/api/v2/citations/{forged}", headers=auth_headers()
    )
    gone = v2_bundle["client"].get(
        f"/api/v2/citations/{stale_token}", headers=auth_headers()
    )

    assert resolved.status_code == 200
    assert resolved.json["data"]["source"]["source_id"] == "src_fixture_primary"
    assert invalid.status_code == 422
    assert gone.status_code == 410
    assert gone.json["error"]["details"]["revision"] == "rev_fixture_stale"
    assert_component_schema(resolved.json, "CitationResponse")


def test_signed_assets_have_safe_headers_nested_css_and_generic_capability_failure(
    v2_bundle,
) -> None:
    settings = v2_bundle["settings"]
    now = int(time.time())
    css = issue_resource_capability(
        "src_fixture_primary",
        "rev_fixture_0001",
        "styles/main.css",
        settings.asset_signing_key,
        now=now,
    )
    expired = encode_resource_capability(
        ResourceTarget(
            "src_fixture_primary",
            "rev_fixture_0001",
            "images/diagram.png",
            now - 1,
        ),
        settings.asset_signing_key,
    )

    response = v2_bundle["client"].get(css.url)
    rejected = v2_bundle["client"].get(f"/assets/v2/{expired}")

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/css")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Access-Control-Allow-Origin"] == "*"
    assert b"/assets/v2/" in response.data
    assert rejected.status_code == 401
    assert rejected.json["error"]["code"] == "invalid_capability"


def test_status_redacts_secret_path_and_credential_url_values(v2_bundle) -> None:
    v2_bundle["dependencies"].status_provider = lambda: {
        "state": "ready",
        "sources": {"available": 1, "unavailable": 0, "scan_state": "idle"},
        "storage": {
            "library_readable": True,
            "data_writable": True,
            "index_writable": True,
        },
        "capabilities": {"metadata": True, "external_cache": True},
        "token": TOKEN,
        "library_path": "/private/dictionaries",
        "cache_url": "redis://user:password@cache.internal:6379/0",
    }

    response = v2_bundle["client"].get("/api/v2/status", headers=auth_headers())
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert TOKEN not in body
    assert "/private/dictionaries" not in body
    assert "password" not in body


def test_unknown_and_unexpected_v2_errors_are_json_without_tracebacks(v2_bundle) -> None:
    unknown = v2_bundle["client"].get("/api/v2/not-a-route", headers=auth_headers())
    v2_bundle["dependencies"].status_provider = lambda: (_ for _ in ()).throw(
        RuntimeError("private traceback detail")
    )
    unexpected = v2_bundle["client"].get("/api/v2/status", headers=auth_headers())

    assert unknown.status_code == 404
    assert unknown.json["error"]["code"] == "not_found"
    assert unexpected.status_code == 500
    assert unexpected.json["error"]["code"] == "internal_error"
    assert "private traceback detail" not in unexpected.get_data(as_text=True)
    assert_component_schema(unknown.json, "ErrorEnvelope")
    assert_component_schema(unexpected.json, "ErrorEnvelope")


def build_failure_matrix_app(
    sources: tuple[FakeDictionarySource, ...], bounds: LookupBounds | None = None
):
    records = tuple(
        SourceRecord(
            source.source_id,
            source.revision,
            source.title,
            source.enabled,
            source.sort_order,
            source.available,
            source.unavailable_reason,
        )
        for source in sources
    )
    catalog = SourceCatalog(records, {source.source_id: source for source in sources})
    settings = load_private_service_settings({"MDICT_LIVE_TOKEN": TOKEN})
    lookup = LookupService(
        catalog,
        citation_signing_key=settings.citation_signing_key,
        asset_signing_key=settings.asset_signing_key,
        bounds=bounds,
    )
    dependencies = V2Dependencies(
        catalog,
        lookup,
        SuggestionService(catalog),
        MetadataService(None),
    )
    app = Flask(f"failure-matrix-{id(sources)}")
    app.config["TESTING"] = True
    install_v2_api(app, dependencies, settings, request_id_factory=lambda: "req_matrix_001")
    return app.test_client(), lookup


def test_http_boundary_distinguishes_empty_partial_and_all_failed() -> None:
    empty = FakeDictionarySource(
        "src_empty",
        "rev_fixture_0001",
        "Empty source",
        sort_order=0,
    )
    failing = FakeDictionarySource(
        "src_failing",
        "rev_fixture_0002",
        "Failing source",
        lookup_error=RuntimeError("private failure"),
        sort_order=1,
    )
    partial_client, partial_service = build_failure_matrix_app((empty, failing))
    failed_client, failed_service = build_failure_matrix_app((failing,))
    try:
        partial = partial_client.get(
            "/api/v2/lookup", query_string={"q": "right"}, headers=auth_headers()
        )
        failed = failed_client.get(
            "/api/v2/lookup", query_string={"q": "right"}, headers=auth_headers()
        )
    finally:
        partial_service.close()
        failed_service.close()

    assert partial.status_code == 200
    assert partial.json["data"]["entries"] == []
    assert partial.json["data"]["partial"] is True
    assert partial.json["data"]["progress"]["completed_source_ids"] == ["src_empty"]
    assert failed.status_code == 503
    assert failed.json["error"]["code"] == "lookup_unavailable"
    assert "private failure" not in failed.get_data(as_text=True)


def test_http_boundary_reports_complete_entry_truncation() -> None:
    oversized = FakeDictionarySource(
        "src_oversized",
        "rev_fixture_0001",
        "Oversized source",
        records={
            "right": (
                FakeEntryRecord("right", "<p>This complete entry is intentionally oversized.</p>"),
            )
        },
    )
    client, lookup_service = build_failure_matrix_app(
        (oversized,), LookupBounds(html_response_bytes=10)
    )
    try:
        response = client.get(
            "/api/v2/lookup", query_string={"q": "right"}, headers=auth_headers()
        )
    finally:
        lookup_service.close()

    assert response.status_code == 200
    assert response.json["data"]["entries"] == []
    assert response.json["data"]["truncated"] is True
    assert response.json["data"]["truncation"]["causes"] == [
        "html_response_bytes"
    ]
    assert_component_schema(response.json, "LookupResponse")
