"""Tests for the HTML parser — text extraction, link collection, section breaks."""

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


# ─── Existing Tests (with print output) ──────────────────────────────


def test_parse_html_strips_scripts_styles_and_tags():
    print("\n[TEST] test_parse_html_strips_scripts_styles_and_tags")
    text = parse_html(SAMPLE)
    plain = text.replace(SECTION_BREAK, " ")
    script_absent = "should be stripped" not in text
    has_hello = "Hello World" in plain
    has_test = "test" in plain
    print(f"  Input:    HTML with <script>, <style>, <h1>, <p> tags")
    print(f"  Expected: script text removed, visible text preserved")
    print(f"  Actual:   script_removed={script_absent}, 'Hello World' present={has_hello}, 'test' present={has_test}")
    assert script_absent
    assert has_hello
    assert has_test
    print("  Status:   PASS [OK]")


def test_parse_html_handles_none_and_malformed():
    print("\n[TEST] test_parse_html_handles_none_and_malformed")
    none_result = parse_html(None)
    malformed_result = parse_html("<<< not html >>>")
    print(f"  Input:    None and '<<< not html >>>'")
    print(f"  Expected: None -> '', malformed -> str (no exception)")
    print(f"  Actual:   None -> {none_result!r}, malformed -> {malformed_result!r} (type={type(malformed_result).__name__})")
    assert none_result == ""
    assert isinstance(malformed_result, str)
    print("  Status:   PASS [OK]")


def test_extract_links_resolves_relative():
    print("\n[TEST] test_extract_links_resolves_relative")
    base = "https://example.com/base"
    links = extract_links(SAMPLE, base)
    print(f"  Input:    base_url='{base}', HTML with '/relative' and 'https://other.com/abs'")
    print(f"  Expected: ['https://example.com/relative', 'https://other.com/abs'] in links")
    print(f"  Actual:   {links}")
    assert "https://example.com/relative" in links
    assert "https://other.com/abs" in links
    print("  Status:   PASS [OK]")


def test_extract_links_handles_none():
    print("\n[TEST] test_extract_links_handles_none")
    result = extract_links(None, "https://example.com/")
    print(f"  Input:    html=None")
    print(f"  Expected: []")
    print(f"  Actual:   {result}")
    assert result == []
    print("  Status:   PASS [OK]")


def test_parse_page_returns_text_and_links():
    """parse_page should return the same results as calling both functions."""
    print("\n[TEST] test_parse_page_returns_text_and_links")
    _title, text, links = parse_page(SAMPLE, "https://example.com/base")
    plain = text.replace(SECTION_BREAK, " ")
    has_hello = "Hello World" in plain
    no_script = "should be stripped" not in text
    has_relative = "https://example.com/relative" in links
    has_abs = "https://other.com/abs" in links
    print(f"  Input:    SAMPLE HTML, base='https://example.com/base'")
    print(f"  Expected: text has 'Hello World', no script text; links have relative + absolute")
    print(f"  Actual:   hello={has_hello}, no_script={no_script}, relative_link={has_relative}, abs_link={has_abs}")
    print(f"  Actual text (excerpt): {plain[:80]!r}...")
    print(f"  Actual links: {links}")
    assert has_hello
    assert no_script
    assert has_relative
    assert has_abs
    print("  Status:   PASS [OK]")


def test_parse_page_handles_none():
    print("\n[TEST] test_parse_page_handles_none")
    title, text, links = parse_page(None, "https://example.com/")
    print(f"  Input:    html=None")
    print(f"  Expected: title='', text='', links=[]")
    print(f"  Actual:   title={title!r}, text={text!r}, links={links}")
    assert title == ""
    assert text == ""
    assert links == []
    print("  Status:   PASS [OK]")


# ─── Section-break tests ─────────────────────────────────────────────


def test_section_break_between_block_elements():
    """Words in separate block elements must NOT be adjacent in the output."""
    print("\n[TEST] test_section_break_between_block_elements")
    html = "<html><body><div>Contact</div><div>Support SEP</div></body></html>"
    print(f"  Input:    <div>Contact</div><div>Support SEP</div>")
    text = parse_html(html)
    has_break = SECTION_BREAK in text
    fragments = [f.strip() for f in text.split(SECTION_BREAK) if f.strip()]
    contact_frag = [f for f in fragments if "Contact" in f]
    support_frag = [f for f in fragments if "Support" in f]
    separate = bool(contact_frag and support_frag and contact_frag[0] != support_frag[0])
    print(f"  Expected: SECTION_BREAK present, 'Contact' and 'Support' in separate fragments")
    print(f"  Actual:   break_present={has_break}, fragments={fragments}, separate={separate}")
    assert has_break
    assert contact_frag and support_frag
    assert contact_frag[0] != support_frag[0], "Contact and Support must be in separate segments"
    print("  Status:   PASS [OK]")


def test_no_section_break_within_inline_content():
    """Inline elements like <b>, <a>, <span> must NOT create breaks."""
    print("\n[TEST] test_no_section_break_within_inline_content")
    html = "<html><body><p>Contact <b>Support</b> here</p></body></html>"
    print(f"  Input:    <p>Contact <b>Support</b> here</p>")
    text = parse_html(html)
    fragments = [f.strip() for f in text.split(SECTION_BREAK) if f.strip()]
    found = [f for f in fragments if "Contact" in f and "Support" in f]
    print(f"  Expected: 'Contact' and 'Support' in same fragment")
    print(f"  Actual:   fragments={fragments}, same_fragment={bool(found)}")
    assert found, "Contact and Support should be in the same segment"
    print("  Status:   PASS [OK]")


def test_section_break_footer_columns():
    """Simulate the exact bug scenario from the issue: footer columns."""
    print("\n[TEST] test_section_break_footer_columns")
    html = """
    <html><body>
      <main><p>Main content here.</p></main>
      <footer>
        <div>Contact</div>
        <div>Support SEP</div>
      </footer>
    </body></html>
    """
    print("  Input:    footer with <div>Contact</div> and <div>Support SEP</div>")
    text = parse_html(html)
    fragments = [f.strip() for f in text.split(SECTION_BREAK) if f.strip()]
    merged = [f for f in fragments if "Contact" in f and "Support" in f]
    print(f"  Expected: 'Contact' and 'Support' NOT in same fragment")
    print(f"  Actual:   fragments={fragments}, incorrectly_merged={merged}")
    for frag in fragments:
        assert not ("Contact" in frag and "Support" in frag), (
            f"Contact and Support incorrectly merged: {frag!r}"
        )
    print("  Status:   PASS [OK]")


def test_section_break_across_headings_and_paragraphs():
    """Headings and paragraphs should be in separate segments."""
    print("\n[TEST] test_section_break_across_headings_and_paragraphs")
    html = "<html><body><h1>Title</h1><p>Body text</p></body></html>"
    print("  Input:    <h1>Title</h1><p>Body text</p>")
    text = parse_html(html)
    fragments = [f.strip() for f in text.split(SECTION_BREAK) if f.strip()]
    title_frags = [f for f in fragments if "Title" in f]
    body_frags = [f for f in fragments if "Body" in f]
    print(f"  Expected: 'Title' and 'Body text' in different fragments")
    print(f"  Actual:   fragments={fragments}")
    assert title_frags and body_frags
    assert title_frags[0] != body_frags[0]
    print("  Status:   PASS [OK]")


def test_section_break_list_items():
    """Each <li> should be its own segment."""
    print("\n[TEST] test_section_break_list_items")
    html = "<html><body><ul><li>Alpha</li><li>Beta</li><li>Gamma</li></ul></body></html>"
    print("  Input:    <ul> with 3 <li> items: Alpha, Beta, Gamma")
    text = parse_html(html)
    fragments = [f.strip() for f in text.split(SECTION_BREAK) if f.strip()]
    print(f"  Expected: each item in separate fragment, no merging")
    print(f"  Actual:   fragments={fragments}")
    assert any("Alpha" in f for f in fragments)
    assert any("Beta" in f for f in fragments)
    assert any("Gamma" in f for f in fragments)
    for frag in fragments:
        items_in_frag = sum(1 for w in ("Alpha", "Beta", "Gamma") if w in frag)
        assert items_in_frag <= 1, f"Multiple list items merged: {frag!r}"
    print("  Status:   PASS [OK]")


# ─── Additional Tests ────────────────────────────────────────────────


def test_parse_html_strips_noscript():
    """Verify <noscript> content is removed."""
    print("\n[TEST] test_parse_html_strips_noscript")
    html = "<html><body><noscript>JS required</noscript><p>Visible</p></body></html>"
    print("  Input:    <noscript>JS required</noscript><p>Visible</p>")
    text = parse_html(html)
    plain = text.replace(SECTION_BREAK, " ")
    noscript_stripped = "JS required" not in text
    visible_present = "Visible" in plain
    print(f"  Expected: noscript removed, 'Visible' present")
    print(f"  Actual:   noscript_stripped={noscript_stripped}, visible={visible_present}, text={text!r}")
    assert noscript_stripped
    assert visible_present
    print("  Status:   PASS [OK]")


def test_extract_links_skips_empty_href():
    """Verify anchors with empty or missing href are handled gracefully."""
    print("\n[TEST] test_extract_links_skips_empty_href")
    html = '<html><body><a href="">empty</a><a>no href</a><a href="/valid">valid</a></body></html>'
    print("  Input:    anchors with empty href, missing href, and '/valid'")
    links = extract_links(html, "https://example.com/")
    print(f"  Expected: '/valid' resolved, no crash from empty/missing href")
    print(f"  Actual:   links={links}")
    assert "https://example.com/valid" in links
    print("  Status:   PASS [OK]")


def test_parse_page_with_nested_tables():
    """Verify table cells create section breaks."""
    print("\n[TEST] test_parse_page_with_nested_tables")
    html = """
    <html><body>
      <table><tr><td>Cell1</td><td>Cell2</td></tr>
             <tr><td>Cell3</td><td>Cell4</td></tr></table>
    </body></html>
    """
    print("  Input:    2x2 table with Cell1..Cell4")
    _title, text, links = parse_page(html, "https://example.com/")
    fragments = [f.strip() for f in text.split(SECTION_BREAK) if f.strip()]
    print(f"  Expected: each cell in separate fragment")
    print(f"  Actual:   fragments={fragments}")
    assert any("Cell1" in f for f in fragments)
    assert any("Cell2" in f for f in fragments)
    # No single fragment should contain both Cell1 and Cell2
    for frag in fragments:
        cells_in_frag = sum(1 for w in ("Cell1", "Cell2", "Cell3", "Cell4") if w in frag)
        assert cells_in_frag <= 1, f"Multiple table cells merged: {frag!r}"
    print("  Status:   PASS [OK]")


def test_parse_html_preserves_text_in_article():
    """Verify <article> text is extracted correctly."""
    print("\n[TEST] test_parse_html_preserves_text_in_article")
    html = "<html><body><article><h2>Headline</h2><p>Story body goes here.</p></article></body></html>"
    print("  Input:    <article> with <h2>Headline</h2> and <p>Story body</p>")
    text = parse_html(html)
    plain = text.replace(SECTION_BREAK, " ")
    has_headline = "Headline" in plain
    has_story = "Story body goes here" in plain
    print(f"  Expected: 'Headline' and 'Story body goes here' present")
    print(f"  Actual:   headline={has_headline}, story={has_story}, text={plain!r}")
    assert has_headline
    assert has_story
    print("  Status:   PASS [OK]")
