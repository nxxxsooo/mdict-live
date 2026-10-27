"""Framework-independent MDict link, HTML, resource, and text representation."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
import hashlib
import html
import posixpath
import re
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup, NavigableString, Tag


MDICT_LINK_PATTERN = re.compile(r"^\s*@@@LINK=(.+?)\s*$", re.DOTALL | re.IGNORECASE)
CSS_URL_PATTERN = re.compile(
    r"url\(\s*(?P<quote>['\"]?)(?P<url>.*?)(?P=quote)\s*\)", re.IGNORECASE
)
CSS_IMPORT_PATTERN = re.compile(
    r"@import\s+(?P<quote>['\"])(?P<url>.*?)(?P=quote)", re.IGNORECASE
)
CSS_UNSAFE_PATTERN = re.compile(
    r"expression\s*\(|-moz-binding\s*:|behavior\s*:|javascript\s*:",
    re.IGNORECASE,
)
CONTROL_OR_SPACE_PATTERN = re.compile(r"[\x00-\x20]+")
WHITESPACE_PATTERN = re.compile(r"\s+")

URL_ATTRIBUTES = {"href", "src", "poster", "data", "action", "formaction", "xlink:href"}
UNSAFE_EMBEDDING_TAGS = {"applet", "embed", "iframe", "object"}
TEXT_BLOCK_TAGS = {
    "address",
    "blockquote",
    "dd",
    "dt",
    "figcaption",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "p",
    "pre",
    "td",
    "th",
}
NON_CONTENT_TAGS = {"head", "script", "style", "template", "noscript", "nav"}


class UnsafeResourcePath(ValueError):
    """Raised when a dictionary resource path cannot be safely scoped."""


@dataclass(frozen=True, slots=True)
class RawSourceRecord:
    headword: str
    record_ordinal: int
    html: str


@dataclass(frozen=True, slots=True)
class ResolvedSourceRecord:
    headword: str
    record_ordinal: int
    html: str
    link_chain: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExtractedTextBlock:
    order: int
    text: str


@dataclass(frozen=True, slots=True)
class RenderedSourceRecord:
    headword: str
    record_ordinal: int
    record_hash: str
    html: str
    text_blocks: tuple[ExtractedTextBlock, ...]
    link_chain: tuple[str, ...]


RecordLookup = Callable[[str], Sequence[RawSourceRecord]]
ResourceUrlBuilder = Callable[[str, str], str]


def _unresolved_link_record(
    record: RawSourceRecord, target: str, reason: str, chain: tuple[str, ...]
) -> ResolvedSourceRecord:
    safe_target = html.escape(target, quote=True)
    markup = (
        f'<p data-mdict-unresolved-link="{reason}">See also: '
        f'<a href="entry://{safe_target}">{safe_target}</a></p>'
    )
    return ResolvedSourceRecord(
        headword=record.headword,
        record_ordinal=record.record_ordinal,
        html=markup,
        link_chain=chain,
    )


def resolve_mdict_links(
    records: Iterable[RawSourceRecord],
    lookup: RecordLookup,
    *,
    max_depth: int = 8,
) -> tuple[ResolvedSourceRecord, ...]:
    """Resolve whole-record ``@@@LINK`` indirections with cycle/depth bounds."""

    if max_depth < 1:
        raise ValueError("max_depth must be positive")

    def resolve(
        record: RawSourceRecord, chain: tuple[str, ...], depth: int
    ) -> list[ResolvedSourceRecord]:
        match = MDICT_LINK_PATTERN.match(record.html)
        if match is None:
            return [
                ResolvedSourceRecord(
                    headword=record.headword,
                    record_ordinal=record.record_ordinal,
                    html=record.html,
                    link_chain=chain,
                )
            ]
        target = match.group(1).strip()
        normalized_target = target.casefold()
        normalized_chain = {item.casefold() for item in chain}
        next_chain = (*chain, target)
        if normalized_target in normalized_chain:
            return [_unresolved_link_record(record, target, "cycle", next_chain)]
        if depth >= max_depth:
            return [_unresolved_link_record(record, target, "depth", next_chain)]
        linked_records = tuple(lookup(target))
        if not linked_records:
            return [_unresolved_link_record(record, target, "missing", next_chain)]
        resolved: list[ResolvedSourceRecord] = []
        for linked_record in linked_records:
            resolved.extend(resolve(linked_record, next_chain, depth + 1))
        return resolved

    resolved_records: list[ResolvedSourceRecord] = []
    for record in records:
        resolved_records.extend(resolve(record, (record.headword,), 0))
    return tuple(resolved_records)


def normalize_resource_path(raw_path: str) -> str:
    """Normalize one packaged path while rejecting absolute or parent traversal."""

    decoded = unquote(raw_path).replace("\\", "/").strip()
    lowered = decoded.casefold()
    if lowered.startswith("file:///"):
        decoded = decoded[8:]
    decoded = decoded.lstrip("/")
    normalized = posixpath.normpath(decoded)
    if normalized in {"", "."}:
        raise UnsafeResourcePath("resource path is empty")
    if normalized == ".." or normalized.startswith("../"):
        raise UnsafeResourcePath("resource path escapes its source")
    if any(segment == ".." for segment in normalized.split("/")):
        raise UnsafeResourcePath("resource path contains parent traversal")
    return normalized


def _normalized_scheme(value: str) -> str:
    collapsed = CONTROL_OR_SPACE_PATTERN.sub("", value)
    return urlsplit(collapsed).scheme.casefold()


def _is_safe_data_url(value: str) -> bool:
    lowered = value.casefold()
    return lowered.startswith(
        (
            "data:image/png",
            "data:image/jpeg",
            "data:image/gif",
            "data:image/webp",
            "data:font/woff",
            "data:font/woff2",
        )
    )


def _resource_kind(tag: Tag, attribute: str) -> str:
    name = tag.name.casefold()
    if name == "link":
        return "stylesheet"
    if name == "img" or attribute == "poster":
        return "image"
    if name in {"audio"}:
        return "sound"
    if name in {"video", "source", "track"}:
        return "media"
    return "resource"


def _rewrite_packaged_url(
    value: str,
    kind: str,
    resource_url: ResourceUrlBuilder,
    *,
    base_path: str | None = None,
) -> str | None:
    value = value.strip()
    if not value:
        return None
    if value.startswith("#"):
        return value
    scheme = _normalized_scheme(value)
    if scheme == "data":
        return value if _is_safe_data_url(value) else None
    if scheme == "file":
        try:
            path = normalize_resource_path(value)
            return resource_url(path, kind)
        except UnsafeResourcePath:
            return None
    if scheme:
        return None
    try:
        if base_path is None or value.startswith(("/", "\\")):
            path = normalize_resource_path(value)
        else:
            decoded = unquote(value).replace("\\", "/").strip()
            path = normalize_resource_path(
                posixpath.join(posixpath.dirname(base_path), decoded)
            )
    except UnsafeResourcePath:
        return None
    return resource_url(path, kind)


def rewrite_css_resources(
    css: str,
    resource_url: ResourceUrlBuilder,
    *,
    base_path: str | None = None,
) -> str:
    """Rewrite nested CSS resources and neutralize executable CSS constructs."""

    css = CSS_UNSAFE_PATTERN.sub("mdict-inert(", css)

    def replace_url(match: re.Match[str]) -> str:
        raw_url = match.group("url").strip()
        rewritten = _rewrite_packaged_url(
            raw_url, "css-resource", resource_url, base_path=base_path
        )
        if rewritten is None:
            return 'url("about:blank")'
        return f'url("{html.escape(rewritten, quote=True)}")'

    def replace_import(match: re.Match[str]) -> str:
        raw_url = match.group("url").strip()
        rewritten = _rewrite_packaged_url(
            raw_url, "stylesheet", resource_url, base_path=base_path
        )
        if rewritten is None:
            return '@import url("about:blank")'
        return f'@import url("{html.escape(rewritten, quote=True)}")'

    return CSS_IMPORT_PATTERN.sub(replace_import, CSS_URL_PATTERN.sub(replace_url, css))


def _sanitize_anchor(tag: Tag, resource_url: ResourceUrlBuilder) -> None:
    href = str(tag.get("href", "")).strip()
    scheme = _normalized_scheme(href)
    if scheme == "entry":
        target = unquote(href.split(":", 1)[1].lstrip("/")).strip()
        tag["href"] = "#"
        tag["data-mdict-action"] = "entry"
        tag["data-mdict-entry"] = target
    elif scheme == "sound":
        raw_path = href.split(":", 1)[1].lstrip("/")
        rewritten = _rewrite_packaged_url(raw_path, "sound", resource_url)
        tag["href"] = "#"
        if rewritten is not None:
            tag["data-mdict-action"] = "sound"
            tag["data-mdict-resource"] = rewritten
        else:
            tag["data-mdict-action"] = "inert"
    elif href.startswith("#"):
        tag["href"] = href
    elif scheme in {"http", "https", "mailto", "tel"}:
        tag["href"] = "#"
        tag["data-mdict-action"] = "inert-external"
        tag["data-mdict-external"] = href
    elif href:
        rewritten = _rewrite_packaged_url(href, "resource", resource_url)
        tag["href"] = rewritten or "#"
        tag["data-mdict-action"] = "resource" if rewritten else "inert"
    else:
        tag["href"] = "#"


def sanitize_dictionary_html(
    raw_html: str, resource_url: ResourceUrlBuilder
) -> tuple[str, BeautifulSoup]:
    """Return source-faithful inert HTML and its sanitized parse tree."""

    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in list(soup.find_all(True)):
        name = tag.name.casefold()
        if name == "script" or name in UNSAFE_EMBEDDING_TAGS or name == "base":
            tag.decompose()
            continue
        if name == "meta" and str(tag.get("http-equiv", "")).casefold() == "refresh":
            tag.decompose()
            continue
        if name == "form":
            preserved_class = tag.get("class")
            preserved_id = tag.get("id")
            tag.attrs = {"data-mdict-inert-form": ""}
            if preserved_class:
                tag["class"] = preserved_class
            if preserved_id:
                tag["id"] = preserved_id
            tag.name = "div"
        if name in {"button", "input", "select", "textarea"}:
            tag["disabled"] = ""

        for attribute in list(tag.attrs):
            attribute_lower = attribute.casefold()
            if attribute_lower.startswith("on"):
                del tag.attrs[attribute]
                continue
            if attribute_lower in {"target", "ping", "download", "srcdoc"}:
                del tag.attrs[attribute]
                continue
            if attribute_lower == "style":
                tag.attrs[attribute] = rewrite_css_resources(
                    str(tag.attrs[attribute]), resource_url
                )
                continue
            if attribute_lower not in URL_ATTRIBUTES:
                continue
            if name == "a" and attribute_lower == "href":
                _sanitize_anchor(tag, resource_url)
                continue
            value = str(tag.attrs.get(attribute, ""))
            rewritten = _rewrite_packaged_url(
                value, _resource_kind(tag, attribute_lower), resource_url
            )
            if rewritten is None:
                del tag.attrs[attribute]
            else:
                tag.attrs[attribute] = rewritten

        if name == "link":
            rel_values = {str(value).casefold() for value in tag.get("rel", [])}
            if "stylesheet" not in rel_values or not tag.get("href"):
                tag.decompose()
                continue
        if name == "style" and tag.string is not None:
            tag.string.replace_with(rewrite_css_resources(str(tag.string), resource_url))

    return str(soup), soup


def _is_hidden_or_noise(tag: Tag) -> bool:
    if tag.name.casefold() in NON_CONTENT_TAGS:
        return True
    if tag.has_attr("hidden") or str(tag.get("aria-hidden", "")).casefold() == "true":
        return True
    if str(tag.get("role", "")).casefold() == "navigation":
        return True
    classes = {str(value).casefold() for value in tag.get("class", [])}
    if classes & {"navigation", "nav", "toolbar", "menu"}:
        return True
    style = CONTROL_OR_SPACE_PATTERN.sub("", str(tag.get("style", "")).casefold())
    return "display:none" in style or "visibility:hidden" in style


def _normalized_visible_text(tag: Tag) -> str:
    if tag.name.casefold() == "tr":
        cells = [
            WHITESPACE_PATTERN.sub(" ", cell.get_text(" ", strip=True)).strip()
            for cell in tag.find_all(["th", "td"], recursive=False)
        ]
        return " | ".join(cell for cell in cells if cell)
    text = WHITESPACE_PATTERN.sub(" ", tag.get_text(" ", strip=True)).strip()
    return re.sub(r"\s+([,.;:!?])", r"\1", text)


def extract_visible_text_blocks(soup: BeautifulSoup) -> tuple[ExtractedTextBlock, ...]:
    """Extract ordered complete visible blocks without style/script/navigation noise."""

    for tag in list(soup.find_all(True)):
        if tag.name is None or tag.attrs is None or tag.parent is None:
            continue
        if _is_hidden_or_noise(tag):
            tag.decompose()

    candidates: list[Tag] = []
    for tag in soup.find_all(True):
        name = tag.name.casefold()
        if name == "tr":
            candidates.append(tag)
            continue
        if name in {"td", "th"} and tag.find_parent("tr") is not None:
            continue
        if name in TEXT_BLOCK_TAGS:
            candidates.append(tag)
            continue
        if name in {"article", "section", "div", "main"} and not tag.find(
            TEXT_BLOCK_TAGS | {"tr"}
        ):
            candidates.append(tag)

    blocks: list[ExtractedTextBlock] = []
    for candidate in candidates:
        text = _normalized_visible_text(candidate)
        if not text:
            continue
        blocks.append(ExtractedTextBlock(order=len(blocks), text=text))

    if not blocks:
        root_text = WHITESPACE_PATTERN.sub(" ", soup.get_text(" ", strip=True)).strip()
        if root_text:
            blocks.append(ExtractedTextBlock(order=0, text=root_text))
    return tuple(blocks)


def build_record_representations(
    records: Iterable[RawSourceRecord],
    lookup: RecordLookup,
    resource_url: ResourceUrlBuilder,
    *,
    max_link_depth: int = 8,
) -> tuple[RenderedSourceRecord, ...]:
    """Resolve and represent source records once for both HTML and text clients."""

    resolved = resolve_mdict_links(records, lookup, max_depth=max_link_depth)
    return build_resolved_record_representations(resolved, resource_url)


def build_resolved_record_representations(
    records: Iterable[ResolvedSourceRecord],
    resource_url: ResourceUrlBuilder,
) -> tuple[RenderedSourceRecord, ...]:
    """Represent records whose source indirections were resolved in a worker."""

    rendered = []
    for record in records:
        safe_html, soup = sanitize_dictionary_html(record.html, resource_url)
        rendered.append(
            RenderedSourceRecord(
                headword=record.headword,
                record_ordinal=record.record_ordinal,
                record_hash=hashlib.sha256(record.html.encode("utf-8")).hexdigest(),
                html=safe_html,
                text_blocks=extract_visible_text_blocks(soup),
                link_chain=record.link_chain,
            )
        )
    return tuple(rendered)
