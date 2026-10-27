"""Byte-shape-compatible rendering adapter for the transitional SPA."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
import re


WORD_LINK = re.compile(r"^(@@@LINK=)(.+)$")
SRC_SCHEMA = re.compile(r'([ "]src=["\'])(/|file:///)?(?!data:)(.+?["\'])')
HREF_END_SLASH = re.compile(r'([ "]href=["\'].+?)(/)(["\'])')
HREF_SOUND = re.compile(r'([ "]href=["\'])(sound://)([^#].+?["\'])')
HREF_ENTRY = re.compile(r'([ "]href=["\'])(entry://)([^#].+?["\'])')
HREF_RESOURCE = re.compile(
    r'([ "]href=["\'])(?!http://|https://|sound://|entry://)([^#].+?["\'])'
)
CSS_LINK = re.compile(r'(<link.*? )(href)(=".+?>)')
SCRIPT_SRC = re.compile(r'(<script.*? )(src)(=".+?>)')


def resolve_legacy_links(
    records: Iterable[str], lookup: Callable[[str], Sequence[str]]
) -> list[str]:
    resolved = list(records)
    for index, record in enumerate(resolved):
        match = WORD_LINK.match(record)
        if match:
            target = match.group(2).strip()
            resolved[index] = "\n\n".join(lookup(target))
    return resolved


def render_legacy_records(
    records: Iterable[str],
    *,
    prefix_resource: str,
    reset_css_url: str,
    fix_html: Callable[[str], str],
) -> str:
    records = list(records)
    html_parts: list[str] = []
    count = 1
    record_num = sum(not record.startswith("@@@LINK=") for record in records)
    for record in records:
        record = fix_html(record)
        match = WORD_LINK.match(record)
        if match:
            target = match.group(2).strip()
            html_parts.append(
                f'<p>See also: <a href="entry://{target}" '
                f'data-entry-word="{target}">{target}</a></p>'
            )
            continue
        record = SRC_SCHEMA.sub(r"\g<1>%s/\3" % prefix_resource, record)
        record = HREF_RESOURCE.sub(r"\g<1>%s/\2" % prefix_resource, record)
        record = HREF_END_SLASH.sub(r"\1\3", record)
        record = HREF_SOUND.sub(
            r' data-sound-url="%s/\3" \1\2\3' % prefix_resource, record
        )
        record = HREF_ENTRY.sub(r' data-entry-word="\3" \1\2\3', record)
        if count > 1:
            record = CSS_LINK.sub(r"\1data-\2\3", record)
        if count < record_num:
            record = SCRIPT_SRC.sub(r"\1data-\2\3", record)
        count += 1
        html_parts.append(record)
    return f'<link rel="stylesheet" href="{reset_css_url}">' + "<hr />".join(
        html_parts
    )
