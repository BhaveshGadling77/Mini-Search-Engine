"""HTML parsing: visible-text extraction and outbound link collection.

Uses `lxml.html` (no `beautifulsoup4` dependency). Malformed HTML is handled
gracefully by lxml; on hard parse failure the functions degrade gracefully
(empty text / empty link list) rather than raising.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

import lxml.html

_WS_RE = re.compile(r"\s+")

# Nodes removed before extracting visible text.
_STRIP_XPATH = "//script | //style | //noscript | //head | //template"


def _parse_dom(html: str | None):
    """Parse HTML into an lxml DOM tree, or return None on failure."""
    if not html:
        return None
    try:
        return lxml.html.fromstring(html)
    except Exception:  # noqa: BLE001 - malformed HTML must not crash the crawl
        return None


def parse_page(html: str | None, base_url: str) -> tuple[str, list[str]]:
    """Parse HTML once and return both clean text and outbound links.

    This avoids parsing the same HTML twice when both text and links are
    needed (which is the common case in the crawl loop).

    Returns
    -------
    tuple[str, list[str]]
        (visible_text, list_of_absolute_urls)
    """
    doc = _parse_dom(html)
    if doc is None:
        return "", []

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
    text = _WS_RE.sub(" ", doc.text_content()).strip()

    return text, links


def parse_html(html: str | None) -> str:
    """Strip scripts/styles/tags and return collapsed visible text."""
    doc = _parse_dom(html)
    if doc is None:
        return ""
    for node in doc.xpath(_STRIP_XPATH):
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)
    text = doc.text_content()
    return _WS_RE.sub(" ", text).strip()


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