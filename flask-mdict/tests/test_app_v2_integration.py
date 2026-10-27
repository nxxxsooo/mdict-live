from __future__ import annotations

from pathlib import Path

import pytest

import app as application
from flask_mdict import helper
from private_service import PrivateServiceConfigurationError


TOKEN = "private-test-token-0123456789abcdef"


def test_real_app_factory_installs_v2_and_preserves_legacy_routes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    library = tmp_path / "library"
    data = tmp_path / "data"
    indexes = data / "index"
    config_dir = tmp_path / "config"
    library.mkdir()
    monkeypatch.setenv("MDICT_LIVE_TOKEN", TOKEN)
    monkeypatch.delenv("MDICT_TRUSTED_PROXY_HOPS", raising=False)
    monkeypatch.setattr(helper, "init_plugins", lambda *_args, **_kwargs: None)

    app = application.create_app(
        {
            "TESTING": True,
            "MDICT_V2_ENABLED": True,
            "MDICT_LIBRARY_DIR": str(library),
            "MDICT_DATA_DIR": str(data),
            "MDICT_INDEX_DIR": str(indexes),
            "MDICT_CONFIG_DIR": str(config_dir),
        }
    )
    try:
        client = app.test_client()
        discovery = client.get(
            "/api/v2", headers={"Authorization": f"Bearer {TOKEN}"}
        )
        legacy = client.get("/api/dicts")
        health = client.get("/health/ready")
    finally:
        app.extensions["mdict_v2_dependencies"].lookup_service.close()

    assert discovery.status_code == 200
    assert discovery.json["data"]["api_version"] == "2.0"
    assert legacy.status_code == 200
    assert legacy.json == []
    assert health.json == {"status": "ready", "ready": True}
    assert (data / "mdict-live.db").is_file()
    assert not (library / "flask_mdict.db").exists()


def test_real_app_factory_fails_v2_startup_without_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MDICT_LIVE_TOKEN", raising=False)
    monkeypatch.delenv("MDICT_LIVE_TOKEN_FILE", raising=False)

    with pytest.raises(PrivateServiceConfigurationError, match="requires"):
        application.create_app(
            {
                "MDICT_V2_ENABLED": True,
                "MDICT_LIBRARY_DIR": str(tmp_path / "library"),
                "MDICT_DATA_DIR": str(tmp_path / "data"),
                "MDICT_INDEX_DIR": str(tmp_path / "data" / "index"),
            }
        )


def test_reverse_proxy_prefix_is_preserved_in_workspace_redirect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "library").mkdir()
    monkeypatch.setenv("MDICT_LIVE_TOKEN", TOKEN)
    monkeypatch.setenv("MDICT_TRUSTED_PROXY_HOPS", "1")
    monkeypatch.setenv("MDICT_TRUSTED_PROXY_CIDRS", "127.0.0.0/8")
    monkeypatch.setattr(helper, "init_plugins", lambda *_args, **_kwargs: None)
    app = application.create_app(
        {
            "TESTING": True,
            "MDICT_V2_ENABLED": True,
            "MDICT_LIBRARY_DIR": str(tmp_path / "library"),
            "MDICT_DATA_DIR": str(tmp_path / "data"),
            "MDICT_INDEX_DIR": str(tmp_path / "data" / "index"),
        }
    )
    try:
        response = app.test_client().get(
            "/",
            headers={"X-Forwarded-Prefix": "/private/dictionary"},
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
    finally:
        app.extensions["mdict_v2_dependencies"].lookup_service.close()

    assert response.status_code == 302
    assert response.headers["Location"] == "/private/dictionary/app/"
