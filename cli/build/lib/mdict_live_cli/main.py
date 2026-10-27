"""Command-line entry point for the standalone MdictLive client."""

from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata
from typing import Any, Sequence

from . import __version__
from .config import ConnectionConfig, resolve_connection
from .errors import CliError, ConfigurationError, UsageError
from .output import (
    bounded_agent_lookup,
    client_error_envelope,
    client_success_envelope,
    json_line,
    render_health,
    render_lookup,
    render_resolve,
    render_sources,
    render_suggestions,
)
from .transport import HttpClient


class RaisingArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise UsageError(message)


def _add_global_options(parser: argparse.ArgumentParser, *, hidden: bool = False) -> None:
    default = argparse.SUPPRESS if hidden else None
    help_text = argparse.SUPPRESS if hidden else None
    parser.add_argument("--profile", default=default, help=help_text or "Named connection profile")
    parser.add_argument("--url", default=default, help=help_text or "Service base URL, including any reverse-proxy prefix")
    parser.add_argument("--token", default=default, help=help_text or "Bearer token (prefer environment or a protected file)")
    parser.add_argument("--token-file", default=default, help=help_text or "Path to a protected bearer-token file")
    parser.add_argument("--timeout", default=default, help=help_text or "HTTP timeout in seconds")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", default=default, help=help_text or "Emit one JSON document")
    output.add_argument("--agent", action="store_true", default=default, help=help_text or "Emit bounded plain-text evidence")
    parser.add_argument("--verbose", action="store_true", default=default, help=help_text or "Write redacted request diagnostics to stderr")


def build_parser() -> RaisingArgumentParser:
    parser = RaisingArgumentParser(prog="mdict-live", description="Private MdictLive v2 client")
    parser.add_argument("--version", action="version", version=f"mdict-live {__version__}")
    _add_global_options(parser)
    hidden_globals = RaisingArgumentParser(add_help=False, argument_default=argparse.SUPPRESS)
    _add_global_options(hidden_globals, hidden=True)
    commands = parser.add_subparsers(dest="command", required=True)

    health = commands.add_parser("health", parents=[hidden_globals], help="Check liveness and readiness")
    health.add_argument("--details", action="store_true", help="Include authenticated service status")
    commands.add_parser("sources", parents=[hidden_globals], help="List dictionary sources")

    lookup = commands.add_parser("lookup", parents=[hidden_globals], help="Look up a word or phrase")
    lookup.add_argument("query")
    lookup.add_argument("--source", action="append", default=[], help="Source ID or unambiguous title fragment")
    lookup.add_argument("--record-history", action="store_true", help="Record a successful lookup once")

    resolve = commands.add_parser("resolve", parents=[hidden_globals], help="Resolve an opaque citation token")
    resolve.add_argument("citation")

    suggest = commands.add_parser("suggest", parents=[hidden_globals], help="Suggest matching headwords")
    suggest.add_argument("prefix")
    suggest.add_argument("--fuzzy", action="store_true", help="Enable explicit bounded typo fallback")
    return parser


def _normalized_query(value: str, label: str) -> str:
    normalized = unicodedata.normalize("NFC", value.strip())
    if not normalized:
        raise UsageError(f"{label} must not be empty.")
    if len(normalized) > 256:
        raise UsageError(f"{label} exceeds 256 Unicode scalar values.")
    return normalized


def _source_records(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    data = envelope.get("data")
    sources = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(sources, list):
        raise UsageError("Source response cannot be used for selector resolution.")
    return [source for source in sources if isinstance(source, dict)]


def resolve_source_selectors(
    selectors: Sequence[str], source_envelope: dict[str, Any]
) -> tuple[str, ...]:
    records = _source_records(source_envelope)
    resolved: list[str] = []
    for raw_selector in selectors:
        selector = raw_selector.strip()
        if not selector:
            raise UsageError("Source selectors must not be empty.")
        exact_ids = [source for source in records if source.get("source_id") == selector]
        if exact_ids:
            source_id = exact_ids[0]["source_id"]
        else:
            folded = selector.casefold()
            exact_titles = [
                source for source in records
                if isinstance(source.get("title"), str) and source["title"].casefold() == folded
            ]
            candidates = exact_titles or [
                source for source in records
                if isinstance(source.get("title"), str) and folded in source["title"].casefold()
            ]
            if not candidates:
                raise UsageError(f"Source selector {selector!r} matched no source.")
            if len(candidates) > 1:
                matches = ", ".join(
                    f"{source.get('title', 'source')} [{source.get('source_id', 'unknown')}]"
                    for source in candidates
                )
                raise UsageError(f"Source selector {selector!r} is ambiguous: {matches}.")
            source_id = candidates[0].get("source_id")
            if not isinstance(source_id, str):
                raise UsageError("Matched source has no stable source_id.")
        if source_id not in resolved:
            resolved.append(source_id)
    return tuple(resolved)


def _lookup_exit(envelope: dict[str, Any]) -> int:
    data = envelope.get("data")
    if not isinstance(data, dict):
        return 5
    if data.get("partial"):
        return 7
    entries = data.get("entries")
    return 1 if isinstance(entries, list) and not entries else 0


def _requires_token(args: argparse.Namespace) -> bool:
    return args.command != "health" or bool(getattr(args, "details", False))


def _execute(args: argparse.Namespace, config: ConnectionConfig) -> tuple[object, str, int]:
    client = HttpClient(config, verbose=bool(getattr(args, "verbose", False)))
    if args.command == "health":
        result = client.health(details=args.details)
        return result, render_health(result), 0 if result.get("readiness", {}).get("ready") else 6
    if args.command == "sources":
        result = client.sources()
        return result, render_sources(result), 0
    if args.command == "lookup":
        query = _normalized_query(args.query, "Query")
        selectors = tuple(args.source) or config.sources
        source_ids: tuple[str, ...] = ()
        if selectors:
            source_ids = resolve_source_selectors(selectors, client.sources())
        result = client.lookup(query, source_ids, record_history=args.record_history)
        text = bounded_agent_lookup(result) if getattr(args, "agent", False) else render_lookup(result)
        return result, text, _lookup_exit(result)
    if args.command == "resolve":
        citation = _normalized_query(args.citation, "Citation token")
        if citation.startswith("mdict://"):
            raise UsageError(
                "A stable citation URI identifies evidence but does not contain its protected resolver token; pass the paired token."
            )
        result = client.resolve(citation)
        return result, render_resolve(result), 0
    if args.command == "suggest":
        prefix = _normalized_query(args.prefix, "Suggestion prefix")
        result = client.suggest(prefix, fuzzy=args.fuzzy)
        return result, render_suggestions(result), 0
    raise UsageError("No command selected.")


def run(argv: Sequence[str] | None = None, *, env: dict[str, str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    json_mode = "--json" in arguments
    try:
        args = build_parser().parse_args(arguments)
        config = resolve_connection(
            args,
            env=os.environ if env is None else env,
            require_token=_requires_token(args),
        )
        payload, human, exit_code = _execute(args, config)
        if getattr(args, "json", False):
            output = payload if isinstance(payload, dict) and payload.get("api_version") else client_success_envelope(payload)
            print(json_line(output))
        else:
            if human:
                print(human)
        return exit_code
    except CliError as error:
        if json_mode:
            print(json_line(client_error_envelope(error)))
        profile = "default"
        try:
            position = arguments.index("--profile")
            profile = arguments[position + 1]
        except (ValueError, IndexError):
            profile = (os.environ if env is None else env).get("MDICT_LIVE_PROFILE", "default")
        print(f"mdict-live[{profile}]: {error.category}: {error}", file=sys.stderr)
        return error.exit_code
    except KeyboardInterrupt:
        error = ConfigurationError("Interrupted.")
        if json_mode:
            print(json_line(client_error_envelope(error)))
        print("mdict-live: interrupted", file=sys.stderr)
        return error.exit_code


def entrypoint() -> None:
    raise SystemExit(run())
