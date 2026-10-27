"""Production WSGI entry point for the container image."""

from __future__ import annotations

import json
import os
from pathlib import Path

from app import create_app


def load_application():
    config_path = Path(os.environ.get("MDICT_CONFIG_FILE", "/app/flask_mdict.json"))
    config_data = {}
    if config_path.is_file():
        with config_path.open(encoding="utf-8") as config_file:
            config_data = json.load(config_file)
    return create_app(config_data.get("mdict", {}))


application = load_application()
