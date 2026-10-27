"""Stable human, JSON, and bounded agent renderers."""

from __future__ import annotations

import json
from typing import Any

from . import __version__
from .errors import CliError


AGENT_OUTPUT_BYTES = 32 * 1024


def json_line(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def client_error_envelope(error: CliError) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "client_version": __version__,
        "ok": False,
        "error": {
            "category": error.category,
            "message": str(error),
            "exit_code": error.exit_code,
        },
    }
    if error.request_id:
        payload["error"]["request_id"] = error.request_id
    return payload


def client_success_envelope(data: object) -> dict[str, Any]:
    return {"client_version": __version__, "ok": True, "data": data}


def _data(envelope: dict[str, Any]) -> dict[str, Any]:
    value = envelope.get("data")
    return value if isinstance(value, dict) else {}


def render_health(result: dict[str, Any]) -> str:
    live = result.get("liveness", {})
    ready = result.get("readiness", {})
    lines = [
        f"Liveness: {live.get('status', 'unknown') if isinstance(live, dict) else 'unknown'}",
        f"Readiness: {ready.get('status', 'unknown') if isinstance(ready, dict) else 'unknown'}",
    ]
    status = result.get("status")
    if isinstance(status, dict):
        state = _data(status).get("state", "unknown")
        lines.append(f"Service: {state}")
    return "\n".join(lines)


def render_sources(envelope: dict[str, Any]) -> str:
    sources = _data(envelope).get("sources", [])
    lines = [f"Sources: {len(sources) if isinstance(sources, list) else 0}"]
    if isinstance(sources, list):
        for source in sources:
            if not isinstance(source, dict):
                continue
            marker = "✓" if source.get("enabled") and source.get("available") else "–"
            title = source.get("title", source.get("source_id", "source"))
            source_id = source.get("source_id", "unknown")
            reason = source.get("unavailable_reason")
            lines.append(f"{marker} {title} [{source_id}]" + (f" — {reason}" if reason else ""))
    return "\n".join(lines)


def _citation_uri(value: object) -> str | None:
    if isinstance(value, dict) and isinstance(value.get("uri"), str):
        return value["uri"]
    return None


def render_lookup(envelope: dict[str, Any]) -> str:
    data = _data(envelope)
    query = data.get("normalized_query", data.get("query", ""))
    entries = data.get("entries", [])
    lines = [str(query)]
    if data.get("partial"):
        lines.append("[partial evidence]")
    if data.get("truncated"):
        causes = data.get("truncation")
        lines.append(f"[bounded response: {causes}]")
    if not isinstance(entries, list) or not entries:
        lines.append("No match.")
        return "\n".join(lines)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        title = entry.get("source_title") or entry.get("source_id") or "Dictionary"
        lines.extend(("", f"## {title}"))
        blocks = entry.get("text_blocks", [])
        if isinstance(blocks, list):
            for block in blocks:
                if not isinstance(block, dict) or not isinstance(block.get("text"), str):
                    continue
                lines.append(block["text"])
                uri = _citation_uri(block.get("citation"))
                if uri:
                    lines.append(f"Citation: {uri}")
        entry_uri = _citation_uri(entry.get("citation"))
        if entry_uri and not any(line == f"Citation: {entry_uri}" for line in lines):
            lines.append(f"Citation: {entry_uri}")
    failures = data.get("progress", {}).get("failed_sources", []) if isinstance(data.get("progress"), dict) else []
    if failures:
        lines.extend(("", "Failed sources:"))
        for failure in failures:
            if isinstance(failure, dict):
                lines.append(f"- {failure.get('source_id', 'source')}: {failure.get('code', 'failed')}")
    return "\n".join(lines)


def render_suggestions(envelope: dict[str, Any]) -> str:
    suggestions = _data(envelope).get("suggestions", [])
    if not isinstance(suggestions, list):
        return ""
    return "\n".join(
        str(item.get("headword"))
        for item in suggestions
        if isinstance(item, dict) and item.get("headword")
    )


def render_resolve(envelope: dict[str, Any]) -> str:
    data = _data(envelope)
    source = data.get("source", {})
    title = source.get("title", source.get("source_id", "Dictionary")) if isinstance(source, dict) else "Dictionary"
    lines = [f"{data.get('headword', 'Citation')} — {title}"]
    block = data.get("text_block")
    if isinstance(block, dict) and isinstance(block.get("text"), str):
        lines.append(block["text"])
    uri = _citation_uri(data.get("citation"))
    if uri:
        lines.append(f"Citation: {uri}")
    return "\n".join(lines)


def bounded_agent_lookup(envelope: dict[str, Any], limit: int = AGENT_OUTPUT_BYTES) -> str:
    data = _data(envelope)
    lines = [
        f"query: {data.get('normalized_query', data.get('query', ''))}",
        f"request_id: {envelope.get('request_id', '')}",
        f"partial: {str(bool(data.get('partial'))).lower()}",
        f"truncated: {str(bool(data.get('truncated'))).lower()}",
    ]
    entries = data.get("entries", [])
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            lines.append(f"\nsource: {entry.get('source_title') or entry.get('source_id', 'unknown')}")
            for block in entry.get("text_blocks", []):
                if not isinstance(block, dict) or not isinstance(block.get("text"), str):
                    continue
                uri = _citation_uri(block.get("citation"))
                if uri:
                    lines.append(f"citation: {uri}")
                lines.append(block["text"])
    rendered = "\n".join(lines)
    encoded = rendered.encode("utf-8")
    if len(encoded) <= limit:
        return rendered
    suffix = b"\n[agent output truncated]"
    clipped = encoded[: max(0, limit - len(suffix))]
    while clipped:
        try:
            return clipped.decode("utf-8") + suffix.decode("ascii")
        except UnicodeDecodeError:
            clipped = clipped[:-1]
    return suffix.decode("ascii")
