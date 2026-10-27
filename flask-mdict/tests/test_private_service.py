from __future__ import annotations

from pathlib import Path

from flask import Flask, request, url_for
import pytest

from private_service import (
    PrivateServiceConfigurationError,
    configure_proxy_middleware,
    load_private_service_settings,
)


TOKEN = "t" * 32


def test_token_file_is_preferred_and_purpose_keys_are_separated(tmp_path: Path) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("f" * 40 + "\n", encoding="utf-8")

    settings = load_private_service_settings(
        {
            "MDICT_LIVE_TOKEN": TOKEN,
            "MDICT_LIVE_TOKEN_FILE": str(token_file),
        }
    )

    assert settings.bearer_token == b"f" * 40
    assert settings.citation_signing_key != settings.asset_signing_key
    assert settings.bearer_token not in {
        settings.citation_signing_key,
        settings.asset_signing_key,
    }


@pytest.mark.parametrize(
    "environment",
    ({}, {"MDICT_LIVE_TOKEN": "short"}, {"MDICT_LIVE_TOKEN_FILE": "/missing"}),
)
def test_missing_short_or_unreadable_token_fails_closed(
    environment: dict[str, str],
) -> None:
    with pytest.raises(PrivateServiceConfigurationError):
        load_private_service_settings(environment)


def test_cors_origins_are_exact_and_normalized() -> None:
    settings = load_private_service_settings(
        {
            "MDICT_LIVE_TOKEN": TOKEN,
            "MDICT_CORS_ORIGINS": "https://reader.example, http://127.0.0.1:5173/",
        }
    )

    assert settings.cors_origins == {
        "https://reader.example",
        "http://127.0.0.1:5173",
    }


@pytest.mark.parametrize(
    "origin", ("*", "file:///tmp/reader.html", "https://example.test/path")
)
def test_invalid_cors_origins_fail_startup(origin: str) -> None:
    with pytest.raises(PrivateServiceConfigurationError, match="exact"):
        load_private_service_settings(
            {"MDICT_LIVE_TOKEN": TOKEN, "MDICT_CORS_ORIGINS": origin}
        )


def proxy_test_app(environment: dict[str, str]) -> Flask:
    app = Flask(__name__)

    @app.get("/inspect")
    def inspect_request():
        return {
            "url": url_for("inspect_request", _external=True),
            "remote_addr": request.remote_addr,
            "script_root": request.script_root,
        }

    app.wsgi_app = configure_proxy_middleware(app.wsgi_app, environment)
    return app


def test_trusted_proxy_headers_control_external_url_and_prefix() -> None:
    app = proxy_test_app(
        {
            "MDICT_TRUSTED_PROXY_HOPS": "1",
            "MDICT_TRUSTED_PROXY_CIDRS": "10.0.0.0/8",
        }
    )

    response = app.test_client().get(
        "/inspect",
        headers={
            "X-Forwarded-For": "100.64.0.5",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "dict.private.example",
            "X-Forwarded-Prefix": "/mdict",
        },
        environ_overrides={"REMOTE_ADDR": "10.1.2.3"},
    )

    assert response.json == {
        "url": "https://dict.private.example/mdict/inspect",
        "remote_addr": "100.64.0.5",
        "script_root": "/mdict",
    }


def test_direct_client_cannot_spoof_forwarded_headers() -> None:
    app = proxy_test_app(
        {
            "MDICT_TRUSTED_PROXY_HOPS": "1",
            "MDICT_TRUSTED_PROXY_CIDRS": "10.0.0.0/8",
        }
    )

    response = app.test_client().get(
        "/inspect",
        base_url="http://127.0.0.1:5248",
        headers={
            "X-Forwarded-For": "203.0.113.9",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "attacker.invalid",
            "X-Forwarded-Prefix": "/spoofed",
        },
        environ_overrides={"REMOTE_ADDR": "192.0.2.44"},
    )

    assert response.json == {
        "url": "http://127.0.0.1:5248/inspect",
        "remote_addr": "192.0.2.44",
        "script_root": "",
    }


def test_proxy_trust_is_disabled_by_default() -> None:
    app = proxy_test_app({})

    response = app.test_client().get(
        "/inspect",
        headers={"X-Forwarded-Host": "attacker.invalid"},
        environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
    )

    assert "attacker.invalid" not in response.json["url"]
