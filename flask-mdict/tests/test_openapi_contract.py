from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate
import pytest
import yaml


REPOSITORY_ROOT = Path(__file__).parents[2]
CONTRACT_PATH = REPOSITORY_ROOT / "contracts" / "openapi-v2.yaml"
EXAMPLE_DIR = REPOSITORY_ROOT / "contracts" / "examples" / "v2"
MANIFEST_PATH = EXAMPLE_DIR / "manifest.json"


def load_contract() -> dict:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


def load_manifest() -> list[dict[str, str]]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_openapi_document_is_valid_31_contract() -> None:
    document = load_contract()

    validate(document)
    assert document["openapi"] == "3.1.0"
    assert document["info"]["version"] == "2.0.0"


def test_openapi_exposes_every_foundation_route() -> None:
    paths = load_contract()["paths"]
    expected_methods = {
        "/health/live": {"get"},
        "/health/ready": {"get"},
        "/assets/v2/{capability}": {"get"},
        "/api/v2": {"get"},
        "/api/v2/status": {"get"},
        "/api/v2/sources": {"get"},
        "/api/v2/sources/{source_id}": {"patch"},
        "/api/v2/lookup": {"get", "post"},
        "/api/v2/suggestions": {"get"},
        "/api/v2/metadata": {"get"},
        "/api/v2/citations/{citation_token}": {"get"},
    }

    for path, methods in expected_methods.items():
        assert path in paths
        assert methods <= paths[path].keys()


def test_only_bounded_public_surfaces_override_bearer_security() -> None:
    document = load_contract()
    assert document["security"] == [{"bearerAuth": []}]
    assert document["paths"]["/health/live"]["get"]["security"] == []
    assert document["paths"]["/health/ready"]["get"]["security"] == []
    assert document["paths"]["/assets/v2/{capability}"]["get"]["security"] == []

    for path, item in document["paths"].items():
        if path in {"/health/live", "/health/ready", "/assets/v2/{capability}"}:
            continue
        for method, operation in item.items():
            if method in {"get", "post", "patch", "put", "delete"}:
                assert operation.get("security") != []


def test_get_lookup_cannot_request_history_mutation() -> None:
    document = load_contract()
    lookup_path = document["paths"]["/api/v2/lookup"]
    get_parameters = {
        document["components"]["parameters"][parameter["$ref"].rsplit("/", 1)[-1]]["name"]
        if "$ref" in parameter
        else parameter["name"]
        for parameter in lookup_path["get"]["parameters"]
    }
    post_schema = lookup_path["post"]["requestBody"]["content"]["application/json"]["schema"]

    assert "record_history" not in get_parameters
    assert post_schema == {"$ref": "#/components/schemas/LookupRequest"}
    assert "record_history" in document["components"]["schemas"]["LookupRequest"]["properties"]


@pytest.mark.parametrize("example", load_manifest(), ids=lambda item: item["file"])
def test_golden_example_matches_declared_component_schema(example: dict[str, str]) -> None:
    document = load_contract()
    payload = json.loads((EXAMPLE_DIR / example["file"]).read_text(encoding="utf-8"))
    schema_name = example["schema"]
    root_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$ref": f"#/components/schemas/{schema_name}",
        "components": document["components"],
    }
    validator = Draft202012Validator(root_schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))

    assert not errors, "\n".join(error.message for error in errors)


def test_golden_manifest_covers_every_json_example_exactly_once() -> None:
    manifest_files = [item["file"] for item in load_manifest()]
    example_files = sorted(path.name for path in EXAMPLE_DIR.glob("*.json") if path.name != "manifest.json")

    assert len(manifest_files) == len(set(manifest_files))
    assert sorted(manifest_files) == example_files
