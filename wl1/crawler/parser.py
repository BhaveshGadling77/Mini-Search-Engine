"""HTML parsing: visible-text extraction and outbound link collection.

Uses `lxml.html` (no `beautifulsoup4` dependency). Malformed HTML is handled
gracefully by lxml; on hard parse failure the functions degrade gracefully
(empty text / empty link list) rather than raising.

A **section-break sentinel** (``SECTION_BREAK``) is inserted between text
that comes from separate block-level elements so that downstream phrase
matching does not treat words from different sections as adjacent.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

import lxml.html

_WS_RE = re.compile(r"\s+")

# Nodes removed before extracting visible text.
_STRIP_XPATH = "//script | //style | //noscript | //head | //template"

# Sentinel injected between block-level elements so the tokenizer can tell
# that two tokens were never truly adjacent in the page's visual layout.
SECTION_BREAK = "\x00"

# Block-level tags whose boundaries create a "break" in flowing text.
# Includes HTML5 structural & sectioning elements, headings, lists, tables,
# and common content-grouping elements.
_BLOCK_TAGS = frozenset({
    "address", "article", "aside", "blockquote", "br", "caption", "col",
    "colgroup", "dd", "details", "dialog", "div", "dl", "dt", "fieldset",
    "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5",
    "h6", "header", "hgroup", "hr", "li", "main", "nav", "ol", "p", "pre",
    "section", "summary", "table", "tbody", "td", "tfoot", "th", "thead",
    "tr", "ul",
})


def _extract_text_with_breaks(node) -> str:
    """Recursively extract visible text, inserting ``SECTION_BREAK`` markers
    between content from separate block-level elements.

    The result is *not* collapsed — downstream functions handle whitespace
    normalization while preserving the sentinel characters.
    """
    parts: list[str] = []

    # The node's own direct text (text before the first child element).
    if node.text:
        parts.append(node.text)

    for child in node:
        tag = child.tag if isinstance(child.tag, str) else ""
        is_block = tag.lower() in _BLOCK_TAGS if tag else False

        if is_block:
            parts.append(SECTION_BREAK)

        parts.append(_extract_text_with_breaks(child))

        if is_block:
            parts.append(SECTION_BREAK)

        # Tail text: text that follows the closing tag of *child* but still
        # belongs to the current parent node.
        if child.tail:
            parts.append(child.tail)

    return "".join(parts)


def _collapse(raw: str) -> str:
    """Collapse whitespace while preserving ``SECTION_BREAK`` sentinels.

    Adjacent whitespace and sentinels are merged so that each sentinel
    occupies exactly one character position with no surrounding spaces.
    """
    # Merge runs of whitespace / sentinels into a single SECTION_BREAK
    # whenever at least one SECTION_BREAK is present in the run.
    merged = re.sub(rf"[\s{re.escape(SECTION_BREAK)}]*{re.escape(SECTION_BREAK)}[\s{re.escape(SECTION_BREAK)}]*", SECTION_BREAK, raw)
    # Collapse remaining plain whitespace runs.
    merged = _WS_RE.sub(" ", merged)
    return merged.strip(f" {SECTION_BREAK}")


def _parse_dom(html: str | None):
    """Parse HTML into an lxml DOM tree, or return None on failure."""
    if not html:
        return None
    try:
        return lxml.html.fromstring(html)
    except Exception:  # noqa: BLE001 - malformed HTML must not crash the crawl
        return None



def _extract_title(doc) -> str:
    """Extract the page ``<title>`` text, or return ``""`` if absent."""
    title_nodes = doc.xpath("//head/title")
    if not title_nodes:
        # Fallback: some pages have <title> outside <head> or lxml
        # may have re-parented it.
        title_nodes = doc.xpath("//title")
    if title_nodes:
        raw = title_nodes[0].text_content()
        return _WS_RE.sub(" ", raw).strip()
    return ""


def parse_page(html: str | None, base_url: str) -> tuple[str, str, list[str]]:
    """Parse HTML once and return the title, clean text, and outbound links.

    This avoids parsing the same HTML twice when both text and links are
    needed (which is the common case in the crawl loop).

    The returned ``text`` contains ``SECTION_BREAK`` sentinels between
    content that originates from separate block-level elements.

    Returns
    -------
    tuple[str, str, list[str]]
        (page_title, visible_text_with_breaks, list_of_absolute_urls)
    """
    doc = _parse_dom(html)
    if doc is None:
        return "", "", []

    # --- Extract title before stripping <head> ----------------------------
    title = _extract_title(doc)

    # --- Extract links before stripping nodes (anchors may be in <head>) ---
    links: list[str] = []
    for element in doc.xpath("//a[@href]"):
        href = element.get("href")
        if href:
            links.append(urljoin(base_url, href))

    # --- Strip non-visible nodes and extract text -------------------------
    for node in doc.xpath(_STRIP_XPATH):
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)
    text = _collapse(_extract_text_with_breaks(doc))

    return title, text, links


def parse_html(html: str | None) -> str:
    """Strip scripts/styles/tags and return collapsed visible text.

    The returned string contains ``SECTION_BREAK`` sentinels between text
    from separate block-level elements.
    """
    doc = _parse_dom(html)
    if doc is None:
        return ""
    for node in doc.xpath(_STRIP_XPATH):
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)
    return _collapse(_extract_text_with_breaks(doc))


def extract_links(html: str | None, base_url: str) -> list[str]:
    """Collect absolute URLs from all ``<a href>`` anchors in ``html``."""
    doc = _parse_dom(html)
    if doc is None:
        return []
    links: list[str] = []
    for element in doc.xpath("//a[@href]"):
        href = element.get("href")
        if not href:
            continue
        links.append(urljoin(base_url, href))
    return links