from __future__ import annotations

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from representation import (
    RawSourceRecord,
    UnsafeResourcePath,
    build_record_representations,
    extract_visible_text_blocks,
    normalize_resource_path,
    resolve_mdict_links,
    sanitize_dictionary_html,
)
from tests.support.source_fakes import REPRESENTATIVE_FIXTURES, load_entry_fixture


def resource_url(path: str, kind: str) -> str:
    return f"/assets/v2/cap-{kind}-{path.replace('/', '--')}"


def no_link_records(_target: str) -> tuple[RawSourceRecord, ...]:
    return ()


def test_mdict_link_resolution_follows_chains_and_preserves_target_ordinal() -> None:
    linked = {
        "colour": (RawSourceRecord("colour", 4, "@@@LINK=color"),),
        "color": (RawSourceRecord("color", 9, "<p>A visual property.</p>"),),
    }

    resolved = resolve_mdict_links(
        (RawSourceRecord("hue", 1, "@@@LINK=colour"),),
        lambda target: linked.get(target, ()),
    )

    assert len(resolved) == 1
    assert resolved[0].headword == "color"
    assert resolved[0].record_ordinal == 9
    assert resolved[0].link_chain == ("hue", "colour", "color")


@pytest.mark.parametrize(
    ("records", "reason"),
    [
        ({"loop": (RawSourceRecord("loop", 0, "@@@LINK=loop"),)}, "cycle"),
        ({}, "missing"),
    ],
)
def test_mdict_link_resolution_is_bounded_and_keeps_a_readable_fallback(
    records: dict[str, tuple[RawSourceRecord, ...]], reason: str
) -> None:
    resolved = resolve_mdict_links(
        (RawSourceRecord("start", 0, "@@@LINK=loop"),),
        lambda target: records.get(target, ()),
    )

    assert f'data-mdict-unresolved-link="{reason}"' in resolved[0].html
    assert "entry://loop" in resolved[0].html


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("/images\\diagram.png", "images/diagram.png"),
        ("file:///fonts/fixture.woff2", "fonts/fixture.woff2"),
        ("sounds/example%20one.mp3", "sounds/example one.mp3"),
    ],
)
def test_resource_path_normalization_is_source_relative(raw: str, expected: str) -> None:
    assert normalize_resource_path(raw) == expected


@pytest.mark.parametrize("raw", ("../secret", "images/../../secret", "%2e%2e/secret"))
def test_resource_path_normalization_rejects_parent_traversal(raw: str) -> None:
    with pytest.raises(UnsafeResourcePath):
        normalize_resource_path(raw)


@pytest.mark.parametrize("fixture_name", REPRESENTATIVE_FIXTURES)
def test_every_representative_fixture_produces_readable_inert_html(
    fixture_name: str,
) -> None:
    safe_html, soup = sanitize_dictionary_html(
        load_entry_fixture(fixture_name), resource_url
    )

    assert safe_html
    assert not soup.find("script")
    assert not soup.find(["iframe", "object", "embed", "applet"])
    assert not any(
        attribute.casefold().startswith("on")
        for tag in soup.find_all(True)
        for attribute in tag.attrs
    )
    assert "javascript:" not in safe_html.casefold()


def test_css_media_links_and_source_selectors_survive_with_scoped_resources() -> None:
    css_html, css_soup = sanitize_dictionary_html(
        load_entry_fixture("css-heavy"), resource_url
    )
    media_html, media_soup = sanitize_dictionary_html(
        load_entry_fixture("media"), resource_url
    )
    link_html, link_soup = sanitize_dictionary_html(
        load_entry_fixture("link"), resource_url
    )

    assert ":root" in css_html
    assert "grid-template-columns" in css_html
    assert "#sense-one" in css_html
    assert "/assets/v2/cap-css-resource-fonts--fixture.woff2" in css_html
    assert media_soup.img["src"].startswith("/assets/v2/cap-image-")
    sound_link = media_soup.find("a", attrs={"data-mdict-action": "sound"})
    assert sound_link["href"] == "#"
    assert sound_link["data-mdict-resource"].startswith("/assets/v2/cap-sound-")
    entry_link = link_soup.find("a", attrs={"data-mdict-action": "entry"})
    assert entry_link["data-mdict-entry"] == "correct"
    assert "javascript:" not in link_html.casefold()


def test_script_forms_and_unsafe_embeds_become_inert_without_losing_definition() -> None:
    safe_html, soup = sanitize_dictionary_html(
        load_entry_fixture("script-bearing"), resource_url
    )

    assert "window.dictionaryScriptRan" not in safe_html
    assert "window.inlineHandlerRan" not in safe_html
    assert soup.find(attrs={"data-mdict-inert-form": ""}) is not None
    assert all(control.has_attr("disabled") for control in soup.find_all("button"))
    assert "A visible definition" in soup.get_text(" ", strip=True)


def test_visible_text_blocks_preserve_reading_order_and_table_rows() -> None:
    _, plain_soup = sanitize_dictionary_html(load_entry_fixture("plain"), resource_url)
    _, table_soup = sanitize_dictionary_html(load_entry_fixture("table"), resource_url)

    plain_blocks = extract_visible_text_blocks(plain_soup)
    table_blocks = extract_visible_text_blocks(table_soup)

    assert [block.order for block in plain_blocks] == list(range(len(plain_blocks)))
    assert [block.text for block in plain_blocks][:3] == [
        "plain",
        "adjective",
        "Easy to see, hear, or understand.",
    ]
    assert any(
        block.text == "Role | Singular | Plural" for block in table_blocks
    )
    assert any(block.text == "Noun | fixture | fixtures" for block in table_blocks)


def test_text_extraction_excludes_navigation_style_and_hidden_noise() -> None:
    markup = """
    <style>.entry { color: red; }</style>
    <nav>Previous Next</nav>
    <div hidden>Hidden definition</div>
    <p>Visible <strong>definition</strong>.</p>
    """
    _, soup = sanitize_dictionary_html(markup, resource_url)

    blocks = extract_visible_text_blocks(soup)

    assert [block.text for block in blocks] == ["Visible definition."]


def test_full_pipeline_derives_html_and_text_from_the_same_resolved_record() -> None:
    linked_record = RawSourceRecord(
        "right",
        3,
        '<style>.sense{color:teal}</style><p class="sense">Correct as a fact.</p>',
    )

    rendered = build_record_representations(
        (RawSourceRecord("correct", 1, "@@@LINK=right"),),
        lambda target: (linked_record,) if target == "right" else (),
        resource_url,
    )[0]

    assert rendered.headword == "right"
    assert rendered.record_ordinal == 3
    assert ".sense{color:teal}" in rendered.html
    assert [block.text for block in rendered.text_blocks] == ["Correct as a fact."]
    assert rendered.link_chain == ("correct", "right")
