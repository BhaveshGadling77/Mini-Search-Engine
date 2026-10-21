import sys
from pathlib import Path

# Link tests to wl1/crawler
_wl1_dir = Path(__file__).resolve().parents[2] / "wl1"
if str(_wl1_dir) not in sys.path:
    sys.path.insert(0, str(_wl1_dir))

from crawler.parser import extract_links, parse_html, parse_page, SECTION_BREAK

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
    # Text content is still present (possibly separated by SECTION_BREAK).
    plain = text.replace(SECTION_BREAK, " ")
    assert "Hello World" in plain
    assert "test" in plain


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
    plain = text.replace(SECTION_BREAK, " ")
    assert "Hello World" in plain
    assert "should be stripped" not in text
    assert "https://example.com/relative" in links
    assert "https://other.com/abs" in links


def test_parse_page_handles_none():
    text, links = parse_page(None, "https://example.com/")
    assert text == ""
    assert links == []


# ─── Section-break tests ─────────────────────────────────────────────

def test_section_break_between_block_elements():
    """Words in separate block elements must NOT be adjacent in the output."""
    html = "<html><body><div>Contact</div><div>Support SEP</div></body></html>"
    text = parse_html(html)
    # The sentinel should separate "Contact" from "Support SEP".
    assert SECTION_BREAK in text
    # Splitting on the sentinel must yield separate fragments.
    fragments = [f.strip() for f in text.split(SECTION_BREAK) if f.strip()]
    # "Contact" and "Support" must be in different fragments.
    contact_frag = [f for f in fragments if "Contact" in f]
    support_frag = [f for f in fragments if "Support" in f]
    assert contact_frag and support_frag
    assert contact_frag[0] != support_frag[0], (
        "Contact and Support must be in separate segments"
    )


def test_no_section_break_within_inline_content():
    """Inline elements like <b>, <a>, <span> must NOT create breaks."""
    html = "<html><body><p>Contact <b>Support</b> here</p></body></html>"
    text = parse_html(html)
    # Inside a single <p>, there should be no sentinel between the words.
    # Find the fragment containing "Contact".
    fragments = [f.strip() for f in text.split(SECTION_BREAK) if f.strip()]
    found = [f for f in fragments if "Contact" in f and "Support" in f]
    assert found, "Contact and Support should be in the same segment"


def test_section_break_footer_columns():
    """Simulate the exact bug scenario from the issue: footer columns."""
    html = """
    <html><body>
      <main><p>Main content here.</p></main>
      <footer>
        <div>Contact</div>
        <div>Support SEP</div>
      </footer>
    </body></html>
    """
    text = parse_html(html)
    # "Contact" and "Support" must be separated by at least one sentinel.
    fragments = [f.strip() for f in text.split(SECTION_BREAK) if f.strip()]
    for frag in fragments:
        assert not ("Contact" in frag and "Support" in frag), (
            f"Contact and Support incorrectly merged: {frag!r}"
        )


def test_section_break_across_headings_and_paragraphs():
    """Headings and paragraphs should be in separate segments."""
    html = "<html><body><h1>Title</h1><p>Body text</p></body></html>"
    text = parse_html(html)
    fragments = [f.strip() for f in text.split(SECTION_BREAK) if f.strip()]
    title_frags = [f for f in fragments if "Title" in f]
    body_frags = [f for f in fragments if "Body" in f]
    assert title_frags and body_frags
    assert title_frags[0] != body_frags[0]


def test_section_break_list_items():
    """Each <li> should be its own segment."""
    html = "<html><body><ul><li>Alpha</li><li>Beta</li><li>Gamma</li></ul></body></html>"
    text = parse_html(html)
    fragments = [f.strip() for f in text.split(SECTION_BREAK) if f.strip()]
    assert any("Alpha" in f for f in fragments)
    assert any("Beta" in f for f in fragments)
    assert any("Gamma" in f for f in fragments)
    # No single fragment should contain two different items.
    for frag in fragments:
        items_in_frag = sum(1 for w in ("Alpha", "Beta", "Gamma") if w in frag)
        assert items_in_frag <= 1, f"Multiple list items merged: {frag!r}"
