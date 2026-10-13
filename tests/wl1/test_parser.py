import sys
from pathlib import Path

# Link tests to wl1/crawler
_wl1_dir = Path(__file__).resolve().parents[2] / "wl1"
if str(_wl1_dir) not in sys.path:
    sys.path.insert(0, str(_wl1_dir))

from crawler.parser import extract_links, parse_html, parse_page

SAMPLE = """
<html>
  <head><title>Test</title><style>.x { color: red }</style></head>
  <body>
    <script>var a = "should be stripped";</script>
    <h1>Hello World</h1>
    <p>This is a <b>test</b> page.</p>
    <a href="/relative">Rel</a>
    <a href="https://other.com/abs">Abs</a>
    <a href="#frag">Frag</a>
  </body>
</html>
"""


def test_parse_html_strips_scripts_styles_and_tags():
    text = parse_html(SAMPLE)
    assert "should be stripped" not in text
    assert "Hello World" in text
    assert "This is a test page." in text


def test_parse_html_handles_none_and_malformed():
    assert parse_html(None) == ""
    # lxml recovers text from malformed input rather than raising.
    assert isinstance(parse_html("<<< not html >>>"), str)


def test_extract_links_resolves_relative():
    links = extract_links(SAMPLE, "https://example.com/base")
    assert "https://example.com/relative" in links
    assert "https://other.com/abs" in links


def test_extract_links_handles_none():
    assert extract_links(None, "https://example.com/") == []


def test_parse_page_returns_text_and_links():
    """parse_page should return the same results as calling both functions."""
    text, links = parse_page(SAMPLE, "https://example.com/base")
    assert "Hello World" in text
    assert "should be stripped" not in text
    assert "https://example.com/relative" in links
    assert "https://other.com/abs" in links


def test_parse_page_handles_none():
    text, links = parse_page(None, "https://example.com/")
    assert text == ""
    assert links == []
