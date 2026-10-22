"""Tests for the tokenizer — lowercasing, punctuation stripping, stop-words, and segments."""

import sys
from pathlib import Path

# Link tests to wl1/crawler
_wl1_dir = Path(__file__).resolve().parents[2] / "wl1"
if str(_wl1_dir) not in sys.path:
    sys.path.insert(0, str(_wl1_dir))

from crawler.tokenizer import tokenize, tokenize_segments
from crawler.parser import SECTION_BREAK


# ─── Existing Tests (with print output) ──────────────────────────────


def test_tokenize_lowercases_and_strips_punctuation():
    print("\n[TEST] test_tokenize_lowercases_and_strips_punctuation")
    input_text = "Hello, WORLD! 123"
    print(f"  Input:    '{input_text}'")
    expected = ["hello", "world", "123"]
    actual = tokenize(input_text)
    print(f"  Expected: {expected}")
    print(f"  Actual:   {actual}")
    assert actual == expected
    print("  Status:   PASS [OK]")


def test_tokenize_removes_stopwords():
    print("\n[TEST] test_tokenize_removes_stopwords")
    input_text = "the quick brown fox jumps over the lazy dog"
    print(f"  Input:    '{input_text}'")
    expected = ["quick", "brown", "fox", "jumps", "lazy", "dog"]
    actual = tokenize(input_text)
    print(f"  Expected: 'the', 'over' removed -> {expected}")
    print(f"  Actual:   {actual}")
    assert "the" not in actual
    assert actual == expected
    print("  Status:   PASS [OK]")


def test_tokenize_handles_empty_and_none():
    print("\n[TEST] test_tokenize_handles_empty_and_none")
    print("  Input:    '' and None")
    r1 = tokenize("")
    r2 = tokenize(None)
    print(f"  Expected: tokenize('') == [], tokenize(None) == []")
    print(f"  Actual:   empty -> {r1}, None -> {r2}")
    assert r1 == []
    assert r2 == []
    print("  Status:   PASS [OK]")


# ─── tokenize_segments tests ─────────────────────────────────────────


def test_tokenize_segments_splits_on_sentinel():
    """Tokens separated by SECTION_BREAK must end up in different segments."""
    print("\n[TEST] test_tokenize_segments_splits_on_sentinel")
    text = f"Contact{SECTION_BREAK}Support SEP"
    print(f"  Input:    'Contact<SECTION_BREAK>Support SEP'")
    expected = [["contact"], ["support", "sep"]]
    segments = tokenize_segments(text)
    print(f"  Expected: {expected} (len=2)")
    print(f"  Actual:   {segments} (len={len(segments)})")
    assert len(segments) == 2
    assert segments[0] == ["contact"]
    assert segments[1] == ["support", "sep"]
    print("  Status:   PASS [OK]")


def test_tokenize_segments_no_sentinel():
    """Without sentinels, all tokens belong to one segment."""
    print("\n[TEST] test_tokenize_segments_no_sentinel")
    text = "Hello World foo bar"
    print(f"  Input:    '{text}'")
    expected = [["hello", "world", "foo", "bar"]]
    segments = tokenize_segments(text)
    print(f"  Expected: {expected}")
    print(f"  Actual:   {segments}")
    assert len(segments) == 1
    assert segments[0] == ["hello", "world", "foo", "bar"]
    print("  Status:   PASS [OK]")


def test_tokenize_segments_empty_fragments_are_skipped():
    """Multiple consecutive sentinels should not produce empty segments."""
    print("\n[TEST] test_tokenize_segments_empty_fragments_are_skipped")
    text = f"Alpha{SECTION_BREAK}{SECTION_BREAK}{SECTION_BREAK}Beta"
    print(f"  Input:    'Alpha<BREAK><BREAK><BREAK>Beta'")
    expected = [["alpha"], ["beta"]]
    segments = tokenize_segments(text)
    print(f"  Expected: {expected} (len=2)")
    print(f"  Actual:   {segments} (len={len(segments)})")
    assert len(segments) == 2
    assert segments[0] == ["alpha"]
    assert segments[1] == ["beta"]
    print("  Status:   PASS [OK]")


def test_tokenize_segments_stopwords_removed():
    """Stop-words are removed within each segment."""
    print("\n[TEST] test_tokenize_segments_stopwords_removed")
    text = f"the quick brown{SECTION_BREAK}the lazy dog"
    print(f"  Input:    'the quick brown<BREAK>the lazy dog'")
    expected = [["quick", "brown"], ["lazy", "dog"]]
    segments = tokenize_segments(text)
    print(f"  Expected: {expected}")
    print(f"  Actual:   {segments}")
    assert segments[0] == ["quick", "brown"]
    assert segments[1] == ["lazy", "dog"]
    print("  Status:   PASS [OK]")


def test_tokenize_segments_handles_empty_and_none():
    print("\n[TEST] test_tokenize_segments_handles_empty_and_none")
    print("  Input:    '' and None")
    r1 = tokenize_segments("")
    r2 = tokenize_segments(None)
    print(f"  Expected: tokenize_segments('') == [], tokenize_segments(None) == []")
    print(f"  Actual:   empty -> {r1}, None -> {r2}")
    assert r1 == []
    assert r2 == []
    print("  Status:   PASS [OK]")


def test_tokenize_flat_matches_segments():
    """tokenize() should return the same tokens as flattening segments."""
    print("\n[TEST] test_tokenize_flat_matches_segments")
    text = f"Hello World{SECTION_BREAK}foo bar"
    print(f"  Input:    'Hello World<BREAK>foo bar'")
    flat = tokenize(text)
    segments = tokenize_segments(text)
    flattened = [t for seg in segments for t in seg]
    print(f"  Expected: flat == flattened ({flattened})")
    print(f"  Actual:   flat={flat}, flattened={flattened}")
    assert flat == flattened
    print("  Status:   PASS [OK]")


# ─── Additional Tests ────────────────────────────────────────────────


def test_tokenize_special_characters_and_symbols():
    """Alphanumeric tokens extracted while dropping punctuation and symbols."""
    print("\n[TEST] test_tokenize_special_characters_and_symbols")
    input_text = "Crawler-v1.0: extracts #python & $data (at 100% accuracy)!"
    print(f"  Input:    '{input_text}'")
    # 'at' is in config.STOPWORDS, rest are kept
    expected = ["crawler", "v1", "0", "extracts", "python", "data", "100", "accuracy"]
    actual = tokenize(input_text)
    print(f"  Expected: {expected}")
    print(f"  Actual:   {actual}")
    assert actual == expected
    print("  Status:   PASS [OK]")


def test_tokenize_all_stopwords():
    """Input consisting solely of stop-words returns empty token list."""
    print("\n[TEST] test_tokenize_all_stopwords")
    input_text = "this is an and but or if then so what why when"
    print(f"  Input:    '{input_text}' (all stop-words)")
    actual = tokenize(input_text)
    print(f"  Expected: []")
    print(f"  Actual:   {actual}")
    assert actual == []
    print("  Status:   PASS [OK]")


def test_tokenize_pure_numbers():
    """Numeric tokens are preserved and normalized correctly."""
    print("\n[TEST] test_tokenize_pure_numbers")
    input_text = "1984 2001 2026 42"
    print(f"  Input:    '{input_text}'")
    expected = ["1984", "2001", "2026", "42"]
    actual = tokenize(input_text)
    print(f"  Expected: {expected}")
    print(f"  Actual:   {actual}")
    assert actual == expected
    print("  Status:   PASS [OK]")


def test_tokenize_segments_all_stopwords_fragment_omitted():
    """A segment that contains only stopwords is skipped."""
    print("\n[TEST] test_tokenize_segments_all_stopwords_fragment_omitted")
    text = f"Search Engine{SECTION_BREAK}is a and the{SECTION_BREAK}Retrieval System"
    print(f"  Input:    'Search Engine<BREAK>is a and the<BREAK>Retrieval System'")
    expected = [["search", "engine"], ["retrieval", "system"]]
    segments = tokenize_segments(text)
    print(f"  Expected: {expected} (middle segment omitted)")
    print(f"  Actual:   {segments}")
    assert segments == expected
    print("  Status:   PASS [OK]")


def test_tokenize_whitespace_newlines_tabs():
    """Multiple whitespaces, tabs, and newlines are cleanly handled."""
    print("\n[TEST] test_tokenize_whitespace_newlines_tabs")
    input_text = " \t\r\n  Hello  \t\t\n  World \r\n  "
    print(f"  Input:    raw string with tabs and newlines")
    expected = ["hello", "world"]
    actual = tokenize(input_text)
    print(f"  Expected: {expected}")
    print(f"  Actual:   {actual}")
    assert actual == expected
    print("  Status:   PASS [OK]")


def test_tokenize_hyphenated_and_compound_words():
    """Hyphenated words are split into constituent alphanumeric parts."""
    print("\n[TEST] test_tokenize_hyphenated_and_compound_words")
    input_text = "state-of-the-art multi-threading"
    print(f"  Input:    '{input_text}'")
    # 'of' and 'the' are stopwords
    expected = ["state", "art", "multi", "threading"]
    actual = tokenize(input_text)
    print(f"  Expected: {expected}")
    print(f"  Actual:   {actual}")
    assert actual == expected
    print("  Status:   PASS [OK]")
