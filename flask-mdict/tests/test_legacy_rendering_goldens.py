from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from legacy_rendering import render_legacy_records
from tests.support.source_fakes import REPRESENTATIVE_FIXTURES, load_entry_fixture


MANIFEST_PATH = (
    Path(__file__).parent / "fixtures" / "legacy-rendering" / "manifest.json"
)
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def render_fixture(fixture_name: str) -> str:
    return render_legacy_records(
        [load_entry_fixture(fixture_name)],
        prefix_resource="/mdict/uuid_FIXTURE/resource/",
        reset_css_url="/mdict/uuid_FIXTURE/resource/css/reset.css",
        fix_html=lambda value: value,
    )


@pytest.mark.parametrize("fixture_name", REPRESENTATIVE_FIXTURES)
def test_legacy_native_entry_output_matches_pre_boundary_golden(
    fixture_name: str,
) -> None:
    rendered = render_fixture(fixture_name)
    encoded = rendered.encode("utf-8")

    assert len(encoded) == MANIFEST[fixture_name]["bytes"]
    assert hashlib.sha256(encoded).hexdigest() == MANIFEST[fixture_name]["sha256"]


def test_goldens_capture_fidelity_and_security_behavior_before_iframe_cutover() -> None:
    css_heavy = render_fixture("css-heavy")
    media = render_fixture("media")
    links = render_fixture("link")
    script_bearing = render_fixture("script-bearing")

    assert "@font-face" in css_heavy
    assert "grid-template-columns" in css_heavy
    assert "/mdict/uuid_FIXTURE/resource//images/diagram.png" in media
    assert 'data-sound-url="/mdict/uuid_FIXTURE/resource//sounds/example.mp3"' in media
    assert 'data-entry-word="correct"' in links
    # This deliberately records the unsafe legacy behavior that v2 replaces.
    assert "<script>window.dictionaryScriptRan = true;</script>" in script_bearing
    assert 'onload="window.inlineHandlerRan = true"' in script_bearing


def test_rendering_manifest_exactly_covers_representative_fixture_set() -> None:
    assert set(MANIFEST) == set(REPRESENTATIVE_FIXTURES)
