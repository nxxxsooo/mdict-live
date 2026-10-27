#!/usr/bin/env python3
# -*- encoding:utf-8 -*-
import os
import sys
import json
import argparse
import atexit
import logging

from flask import Flask, redirect, request, url_for, g

from application_database import adopt_legacy_database
from flask_mdict import __version__, get_mdict, init_app
from flask_mdict.api import api as api_blueprint
from private_service import configure_proxy_middleware, load_private_service_settings
from runtime_v2 import build_v2_dependencies
from storage_config import resolve_storage_paths
from v2_api import install_v2_api


logger = logging.getLogger(__name__)


def _optional_boolean(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("MDICT_V2_ENABLED must be a boolean value")


def create_app(config=None):
    logging.basicConfig(
        level=20,
        format="%(message)s",
    )
    app = Flask(__name__, template_folder=None, static_folder=None)

    # csrf 永久有效
    app.config["WTF_CSRF_TIME_LIMIT"] = None
    app.config["MDICT_DIR"] = os.path.realpath("content")
    app.config["MDICT_CACHE"] = False
    app.config["SECRET_KEY"] = "21ffjfdlsafj2ofjaslfjdsaf"
    app.config["INDEX_DIR"] = None
    app.config["APP_NAME"] = "MdictLive"

    if config:
        app.config.update(config)

    configured_v2 = _optional_boolean(
        app.config.get("MDICT_V2_ENABLED", os.environ.get("MDICT_V2_ENABLED"))
    )
    token_configured = bool(
        os.environ.get("MDICT_LIVE_TOKEN") or os.environ.get("MDICT_LIVE_TOKEN_FILE")
    )
    v2_enabled = token_configured if configured_v2 is None else configured_v2
    v2_settings = load_private_service_settings() if v2_enabled else None
    app.config["MDICT_V2_ENABLED"] = v2_enabled

    # Opting into v2 also opts out of the historical writable-corpus layout.
    if v2_enabled and not any(
        app.config.get(key) or os.environ.get(key)
        for key in (
            "MDICT_LIBRARY_DIR",
            "MDICT_DATA_DIR",
            "MDICT_INDEX_DIR",
            "MDICT_CONFIG_DIR",
        )
    ):
        app.config["MDICT_LIBRARY_DIR"] = app.config["MDICT_DIR"]

    storage_paths = resolve_storage_paths(app.config)
    app.extensions["mdict_storage_paths"] = storage_paths
    app.config["MDICT_LIBRARY_DIR"] = os.fspath(storage_paths.library_dir)
    app.config["MDICT_DATA_DIR"] = os.fspath(storage_paths.data_dir)
    app.config["MDICT_INDEX_DIR"] = (
        os.fspath(storage_paths.index_dir) if storage_paths.index_dir else None
    )
    app.config["MDICT_CONFIG_DIR"] = os.fspath(storage_paths.config_dir)
    app.config["MDICT_DESCRIPTION_DIR"] = (
        os.fspath(storage_paths.data_dir / "descriptions")
        if not storage_paths.legacy_layout
        else None
    )
    # Legacy internals continue to consume these names during the service cutover.
    app.config["MDICT_DIR"] = app.config["MDICT_LIBRARY_DIR"]
    app.config["INDEX_DIR"] = app.config["MDICT_INDEX_DIR"]

    mdict_dir = app.config["MDICT_DIR"]
    if storage_paths.legacy_layout and not os.path.exists(mdict_dir):
        os.makedirs(mdict_dir)
    if not storage_paths.legacy_layout:
        os.makedirs(storage_paths.data_dir, exist_ok=True)
        if storage_paths.index_dir:
            os.makedirs(storage_paths.index_dir, exist_ok=True)

    app.config["APP_DB"] = os.fspath(storage_paths.application_database)
    if not storage_paths.legacy_layout:
        adopt_legacy_database(
            storage_paths.library_dir / "flask_mdict.db",
            storage_paths.application_database,
        )

    wfd_db = None
    local_wfd_db = os.path.join(mdict_dir, "flask_mdict_wfd.db")
    app_wfd_db = os.path.join(os.path.dirname(__file__), os.path.basename(local_wfd_db))
    if os.path.exists(local_wfd_db):
        wfd_db = local_wfd_db
        app.config["WFD_DB"] = wfd_db
    elif os.path.exists(app_wfd_db):
        wfd_db = app_wfd_db
        app.config["WFD_DB"] = wfd_db

    logger.info(" * app version: %s" % __version__)
    logger.info(" * app db: %s" % app.config["APP_DB"])
    if wfd_db:
        logger.info(f' * Word Frequency Database: {wfd_db}"')
    else:
        logger.error(f' * Could not found "Word Frequency Database - {local_wfd_db}"!')

    init_app(app, url_prefix="/mdict")
    app.register_blueprint(api_blueprint, url_prefix="/api")

    if v2_enabled:
        v2_dependencies = build_v2_dependencies(
            app.config, get_mdict(), v2_settings
        )
        install_v2_api(app, v2_dependencies, v2_settings)
        app.extensions["mdict_v2_dependencies"] = v2_dependencies
        atexit.register(v2_dependencies.lookup_service.close)

    # Serve React SPA static files in production
    spa_dir = os.path.join(os.path.dirname(__file__), "..", "website", "dist")
    if os.path.isdir(spa_dir):
        from flask import send_from_directory

        @app.route("/app/")
        @app.route("/app/<path:path>")
        def serve_spa(path="index.html"):
            full_path = os.path.join(spa_dir, path)
            if os.path.isfile(full_path):
                return send_from_directory(spa_dir, path)
            return send_from_directory(spa_dir, "index.html")

    @app.route("/")
    def index():
        # If SPA is built, redirect to it; otherwise use legacy UI
        if os.path.isdir(spa_dir):
            return redirect(f"{request.script_root}/app/")
        return redirect(url_for("mdict.query_word_all"))

    @app.route("/favicon.ico")
    def favicon():
        return redirect(url_for("mdict.static", filename="favicon.ico"))

    @app.teardown_appcontext
    def close_connection(exception):
        database = getattr(g, "_database", None)
        if not database:
            return
        for conn in database.values():
            conn.close()

    app.wsgi_app = configure_proxy_middleware(app.wsgi_app)

    return app


def cli():
    parser = argparse.ArgumentParser(description="Flask-mdict")
    about = "Flask-mdict version: %s" % __version__
    parser.add_argument(
        "--version", action="version", version=about, help="show version"
    )

    parser.add_argument(
        "--config-file",
        default="flask_mdict.json",
        help="app config json file. default: flask_mdict.json",
    )
    parser.add_argument("--debug", action="store_true", help="flask run as debug mode")
    parser.add_argument("--host", help="service listen ip:port")
    parser.add_argument("--mdict-dir", help="mdict dictionary path")

    args = parser.parse_args()

    config_data = {}
    if os.path.exists(args.config_file):
        config_data = json.load(open(args.config_file))

    if "server" not in config_data:
        config_data["server"] = {}
        config_data["server"]["ip"] = "0.0.0.0"
        config_data["server"]["port"] = "5248"
        config_data["server"]["debug"] = False
        config_data["server"]["threaded"] = True
        config_data["server"]["process"] = 1

    ip = config_data["server"].get("ip", "0.0.0.0")
    port = config_data["server"].get("port", "5248")
    debug = config_data["server"].get("debug", False)
    threaded = config_data["server"].get("threaded", True)
    process = config_data["server"].get("process", 1)

    if args.host:
        ip, port = args.host.split(":")
    if args.debug:
        debug = args.debug

    if "mdict" not in config_data:
        config_data["mdict"] = {}
        config_data["mdict"]["SECRET_KEY"] = "21fwkepawlsafj2jaslfjdsaf"

        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            config_data["mdict"]["MDICT_DIR"] = os.path.realpath(".")
        else:
            config_data["mdict"]["MDICT_DIR"] = os.path.realpath("content")

    if not os.path.exists(args.config_file):
        json.dump(config_data, open("flask_mdict.json", "wt"), indent=4)

    if args.mdict_dir:
        config_data["mdict"]["MDICT_DIR"] = os.path.realpath(args.mdict_dir)

    app = create_app(config_data["mdict"])

    ssl_context = None
    # ssl_context = 'adhoc'
    app.run(
        host=ip,
        port=port,
        debug=debug,
        ssl_context=ssl_context,
        threaded=threaded,
        processes=process,
    )


if __name__ == "__main__":
    cli()
