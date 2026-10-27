from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
import yaml


ROOT = Path(__file__).parents[2]


def test_agent_tool_contract_is_valid_and_maps_to_openapi_operations() -> None:
    contract = json.loads((ROOT / "contracts" / "agent-tools-v1.json").read_text(encoding="utf-8"))
    openapi = yaml.safe_load((ROOT / "contracts" / "openapi-v2.yaml").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(contract)
    operation_ids = {
        operation["operationId"]
        for path in openapi["paths"].values()
        for method, operation in path.items()
        if method in {"get", "post", "patch", "put", "delete"}
    }
    tools = contract["tools"]

    assert [tool["name"] for tool in tools] == [
        "mdict_sources",
        "mdict_lookup",
        "mdict_resolve",
        "mdict_suggest",
    ]
    assert {tool["operation_id"] for tool in tools} <= operation_ids
    assert all(tool["input_schema"]["$ref"].startswith("#/$defs/") for tool in tools)
    assert all(tool["output_schema"]["$ref"].startswith("#/$defs/") for tool in tools)


def test_agent_lookup_contract_matches_api_bounds_and_excludes_html() -> None:
    contract = json.loads((ROOT / "contracts" / "agent-tools-v1.json").read_text(encoding="utf-8"))
    openapi = yaml.safe_load((ROOT / "contracts" / "openapi-v2.yaml").read_text(encoding="utf-8"))
    lookup_input = contract["$defs"]["LookupInput"]
    entry = contract["$defs"]["AgentEntry"]
    api_entry = openapi["components"]["schemas"]["LookupEntry"]

    assert lookup_input["properties"]["query"]["maxLength"] == 256
    assert contract["$defs"]["SourceIds"]["maxItems"] == 32
    assert "html" in api_entry["properties"]
    assert "html" not in entry["properties"]
    assert {"source_id", "revision", "entry_id", "headword", "citation", "text_blocks"} <= set(entry["properties"])
