from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from urllib.parse import parse_qs, unquote, urlsplit

import pytest


CLI_ROOT = Path(__file__).parents[1]
TOKEN = "private-test-token-0123456789abcdef"


def envelope(request_id: str, data: object, *, version: str = "2.0") -> dict:
    return {"api_version": version, "request_id": request_id, "data": data}


class FakeApiHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    requests: list[dict] = []
    api_version = "2.0"
    force_server_error = False

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _record(self, body: object | None = None) -> None:
        self.__class__.requests.append(
            {
                "method": self.command,
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "body": body,
            }
        )

    def _authorized(self) -> bool:
        if self.headers.get("Authorization") == f"Bearer {TOKEN}":
            return True
        self._record()
        self._send(401, {
            "api_version": "2.0",
            "request_id": "req_auth",
            "error": {"code": "authentication_required", "message": "Authentication failed."},
        })
        return False

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        path = url.path.removeprefix("/private") or "/"
        query = parse_qs(url.query)
        if path == "/health/live":
            self._record()
            self._send(200, {"status": "alive"})
            return
        if path == "/health/ready":
            self._record()
            self._send(200, {"status": "ready", "ready": True})
            return
        if not self._authorized():
            return
        self._record()
        if self.force_server_error and path != "/api/v2":
            self._send(422, {
                "api_version": "2.0",
                "request_id": "req_server",
                "error": {"code": "rejected", "message": "Request rejected."},
            })
        elif path == "/api/v2":
            self._send(200, envelope("req_discovery", {"api_version": self.api_version}, version=self.api_version))
        elif path == "/api/v2/status":
            self._send(200, envelope("req_status", {"state": "ready"}))
        elif path == "/api/v2/sources":
            self._send(200, envelope("req_sources", {"sources": [
                {"source_id": "src_oald", "revision": "rev_1", "title": "Oxford Advanced", "enabled": True, "available": True, "order": 0},
                {"source_id": "src_oxford_learner", "revision": "rev_2", "title": "Oxford Learner", "enabled": True, "available": True, "order": 1},
                {"source_id": "src_longman", "revision": "rev_3", "title": "Longman 6", "enabled": True, "available": True, "order": 2},
            ]}))
        elif path == "/api/v2/lookup":
            self._lookup(query.get("q", [""])[0], query.get("source_id", []), False)
        elif path == "/api/v2/suggestions":
            self._send(200, envelope("req_suggest", {
                "query": query.get("prefix", [""])[0],
                "fuzzy": query.get("fuzzy") == ["true"],
                "suggestions": [{"headword": "right"}, {"headword": "rigid"}],
            }))
        elif path.startswith("/api/v2/citations/"):
            token = unquote(path.rsplit("/", 1)[1])
            self._send(200, envelope("req_resolve", {
                "citation": {"uri": "mdict://src_oald/rev_1/rep-v1/ent_1", "token": token},
                "source": {"source_id": "src_oald", "revision": "rev_1", "title": "Oxford Advanced"},
                "entry_id": "ent_1",
                "headword": "right",
                "representation_version": "rep-v1",
                "text_block": {"text": "True or correct as a fact."},
            }))
        else:
            self._send(404, {
                "api_version": "2.0",
                "request_id": "req_missing",
                "error": {"code": "not_found", "message": "Not found."},
            })

    def do_POST(self) -> None:
        if not self._authorized():
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length))
        self._record(body)
        path = urlsplit(self.path).path.removeprefix("/private") or "/"
        if path == "/api/v2/lookup":
            self._lookup(body.get("query", ""), body.get("source_ids", []), bool(body.get("record_history")))
        else:
            self._send(404, {
                "api_version": "2.0",
                "request_id": "req_missing",
                "error": {"code": "not_found", "message": "Not found."},
            })

    def _lookup(self, query: str, source_ids: list[str], history_recorded: bool) -> None:
        if query == "server-error":
            self._send(500, {
                "api_version": "2.0",
                "request_id": "req_failure",
                "error": {"code": "internal_error", "message": "Server failed."},
            })
            return
        entries = [] if query == "absent" else [{
            "source_id": source_ids[0] if source_ids else "src_oald",
            "revision": "rev_1",
            "entry_id": "ent_1",
            "headword": query,
            "record_ordinal": 0,
            "citation": {"uri": "mdict://src_oald/rev_1/rep-v1/ent_1", "token": "citation-token"},
            "html": "<script>privateExecutable()</script>",
            "text_blocks": [{
                "block_id": "blk_1",
                "order": 0,
                "text": "True or correct as a fact." + (" evidence" * 10_000 if query == "huge" else ""),
                "citation": {"uri": "mdict://src_oald/rev_1/rep-v1/ent_1#blk_1", "token": "block-token"},
            }],
        }]
        partial = query == "partial"
        self._send(200, envelope(f"req_lookup_{query}", {
            "query": query,
            "normalized_query": query,
            "entries": entries,
            "partial": partial,
            "truncated": query == "bounded",
            "truncation": {"causes": ["text_response_bytes"]} if query == "bounded" else None,
            "history_recorded": history_recorded,
            "progress": {
                "completed_source_ids": ["src_oald"],
                "failed_sources": [{"source_id": "src_longman", "code": "timeout", "message": "Timed out."}] if partial else [],
                "omitted_source_ids": ["src_longman"] if partial else [],
            },
        }))


@pytest.fixture
def fake_service():
    FakeApiHandler.requests = []
    FakeApiHandler.api_version = "2.0"
    FakeApiHandler.force_server_error = False
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeApiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", FakeApiHandler
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def invoke(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    values = os.environ.copy()
    values["PYTHONPATH"] = str(CLI_ROOT / "src")
    values["MDICT_LIVE_CONFIG"] = str(CLI_ROOT / "tests" / "missing-config.toml")
    if env:
        values.update(env)
    return subprocess.run(
        [sys.executable, "-m", "mdict_live_cli", *args],
        text=True,
        capture_output=True,
        env=values,
        timeout=10,
        check=False,
    )


def service_env(url: str, token: str = TOKEN) -> dict[str, str]:
    return {"MDICT_LIVE_URL": url, "MDICT_LIVE_TOKEN": token}


def test_version_is_local_and_minimal_health_never_resolves_a_token(fake_service) -> None:
    url, handler = fake_service
    version = invoke("--version", env={"MDICT_LIVE_URL": "http://127.0.0.1:9"})
    health = invoke("--url", url, "--json", "health", env={"MDICT_LIVE_TOKEN": ""})

    assert version.returncode == 0
    assert version.stdout.strip().startswith("mdict-live 2.")
    assert health.returncode == 0
    assert json.loads(health.stdout)["data"]["readiness"]["ready"] is True
    assert [request["path"] for request in handler.requests] == ["/health/live", "/health/ready"]
    assert all(request["authorization"] is None for request in handler.requests)


def test_profile_precedence_and_protected_token_file_work_in_subprocess(fake_service, tmp_path: Path) -> None:
    url, handler = fake_service
    token_file = tmp_path / "token"
    token_file.write_text(TOKEN, encoding="utf-8")
    token_file.chmod(0o600)
    config = tmp_path / "config.toml"
    config.write_text(
        "default_profile = \"home\"\n[profiles.home]\n"
        f"url = \"http://127.0.0.1:9\"\ntoken_file = \"{token_file.name}\"\ntimeout_seconds = 1\n",
        encoding="utf-8",
    )
    result = invoke(
        "--url", url, "sources", "--json",
        env={"MDICT_LIVE_CONFIG": str(config), "MDICT_LIVE_TOKEN": ""},
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["data"]["sources"][0]["source_id"] == "src_oald"
    assert handler.requests[0]["authorization"] == f"Bearer {TOKEN}"


def test_unicode_lookup_source_resolution_and_explicit_history_method(fake_service) -> None:
    url, handler = fake_service
    ordinary = invoke("lookup", "cafe\u0301 / au lait", "--source", "Longman", "--json", env=service_env(url))
    recorded = invoke("lookup", "right", "--record-history", "--json", env=service_env(url))

    assert ordinary.returncode == 0
    assert json.loads(ordinary.stdout)["data"]["normalized_query"] == "café / au lait"
    lookup_get = next(request for request in handler.requests if request["method"] == "GET" and "/api/v2/lookup" in request["path"])
    assert "source_id=src_longman" in lookup_get["path"]
    lookup_post = next(request for request in handler.requests if request["method"] == "POST")
    assert lookup_post["body"]["record_history"] is True


@pytest.mark.parametrize(
    ("query", "expected"),
    (("absent", 1), ("partial", 7), ("bounded", 0)),
)
def test_lookup_exit_codes_cover_no_match_partial_and_successful_bounds(fake_service, query: str, expected: int) -> None:
    url, _ = fake_service
    result = invoke("lookup", query, "--json", env=service_env(url))
    assert result.returncode == expected
    assert json.loads(result.stdout)["data"]["normalized_query"] == query


def test_agent_output_is_bounded_plain_text_with_citations_and_no_html(fake_service) -> None:
    url, _ = fake_service
    result = invoke("lookup", "huge", "--agent", env=service_env(url))

    assert result.returncode == 0
    assert len(result.stdout.encode("utf-8")) <= 32 * 1024 + 1
    assert "citation: mdict://" in result.stdout
    assert "<script>" not in result.stdout
    assert "[agent output truncated]" in result.stdout


def test_ambiguous_source_is_a_local_validation_error(fake_service) -> None:
    url, _ = fake_service
    result = invoke("lookup", "right", "--source", "Oxford", "--json", env=service_env(url))
    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["error"]["category"] == "usage"
    assert "src_oald" in payload["error"]["message"]
    assert "src_oxford_learner" in payload["error"]["message"]


def test_auth_transport_compatibility_and_server_errors_have_distinct_codes(fake_service) -> None:
    url, handler = fake_service
    auth = invoke("sources", "--json", env=service_env(url, "wrong-secret"))
    transport = invoke("--url", "http://127.0.0.1:9", "--token", TOKEN, "--timeout", "0.2", "sources", "--json")
    handler.api_version = "3.0"
    compatibility = invoke("sources", "--json", env=service_env(url))
    handler.api_version = "2.0"
    server = invoke("lookup", "server-error", "--json", env=service_env(url))

    assert (auth.returncode, transport.returncode, compatibility.returncode, server.returncode) == (3, 4, 5, 6)
    assert json.loads(auth.stdout)["error"]["category"] == "authentication"
    assert json.loads(transport.stdout)["error"]["category"] == "transport"
    assert json.loads(compatibility.stdout)["error"]["category"] == "compatibility"
    assert json.loads(server.stdout)["error"]["category"] == "server"
    assert "wrong-secret" not in auth.stdout + auth.stderr
    assert TOKEN not in transport.stdout + transport.stderr


def test_suggest_resolve_and_verbose_diagnostics_are_script_safe(fake_service) -> None:
    url, handler = fake_service
    suggested = invoke("--verbose", "suggest", "rig", "--fuzzy", "--json", env=service_env(url))
    resolved = invoke("resolve", "opaque_token_123", "--json", env=service_env(url))

    assert suggested.returncode == 0
    assert json.loads(suggested.stdout)["data"]["fuzzy"] is True
    assert "request method=GET" in suggested.stderr
    assert TOKEN not in suggested.stderr
    assert resolved.returncode == 0
    assert json.loads(resolved.stdout)["data"]["headword"] == "right"
    assert any("/api/v2/citations/opaque_token_123" in request["path"] for request in handler.requests)


def test_insecure_token_file_and_bare_citation_uri_fail_before_transport(tmp_path: Path) -> None:
    token_file = tmp_path / "token"
    token_file.write_text(TOKEN, encoding="utf-8")
    token_file.chmod(0o644)
    insecure = invoke("--url", "http://127.0.0.1:9", "--token-file", str(token_file), "sources", "--json")
    citation = invoke("--url", "http://127.0.0.1:9", "--token", TOKEN, "resolve", "mdict://src/rev/rep/entry", "--json")

    assert insecure.returncode == 2
    assert "permissions are too broad" in json.loads(insecure.stdout)["error"]["message"]
    assert citation.returncode == 2
    assert "protected resolver token" in json.loads(citation.stdout)["error"]["message"]


def test_isolated_install_smokes_local_and_reverse_prefix_services(fake_service, tmp_path: Path) -> None:
    url, _ = fake_service
    environment = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True, timeout=30)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    executable = environment / ("Scripts/mdict-live.exe" if os.name == "nt" else "bin/mdict-live")
    installed = subprocess.run(
        [str(python), "-m", "pip", "install", "--no-deps", str(CLI_ROOT)],
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert installed.returncode == 0, installed.stderr
    values = os.environ.copy()
    values.update({
        "MDICT_LIVE_TOKEN": TOKEN,
        "MDICT_LIVE_CONFIG": str(tmp_path / "missing.toml"),
    })
    for base_url in (url, f"{url}/private"):
        result = subprocess.run(
            [str(executable), "--url", base_url, "sources", "--json"],
            text=True,
            capture_output=True,
            env=values,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["data"]["sources"][0]["source_id"] == "src_oald"
