import sys
from pathlib import Path

# Link tests to wl1/crawler
_wl1_dir = Path(__file__).resolve().parents[2] / "wl1"
if str(_wl1_dir) not in sys.path:
    sys.path.insert(0, str(_wl1_dir))

from crawler.tokenizer import tokenize, tokenize_segments
from crawler.parser import SECTION_BREAK


def test_tokenize_lowercases_and_strips_punctuation():
    assert tokenize("Hello, WORLD! 123") == ["hello", "world", "123"]


def test_tokenize_removes_stopwords():
    result = tokenize("the quick brown fox jumps over the lazy dog")
    assert "the" not in result
    assert result == ["quick", "brown", "fox", "jumps", "lazy", "dog"]


def test_tokenize_handles_empty_and_none():
    assert tokenize("") == []
    assert tokenize(None) == []


# ─── tokenize_segments tests ─────────────────────────────────────────

def test_tokenize_segments_splits_on_sentinel():
    """Tokens separated by SECTION_BREAK must end up in different segments."""
    text = f"Contact{SECTION_BREAK}Support SEP"
    segments = tokenize_segments(text)
    assert len(segments) == 2
    assert segments[0] == ["contact"]
    assert segments[1] == ["support", "sep"]


def test_tokenize_segments_no_sentinel():
    """Without sentinels, all tokens belong to one segment."""
    segments = tokenize_segments("Hello World foo bar")
    assert len(segments) == 1
    assert segments[0] == ["hello", "world", "foo", "bar"]


def test_tokenize_segments_empty_fragments_are_skipped():
    """Multiple consecutive sentinels should not produce empty segments."""
    text = f"Alpha{SECTION_BREAK}{SECTION_BREAK}{SECTION_BREAK}Beta"
    segments = tokenize_segments(text)
    assert len(segments) == 2
    assert segments[0] == ["alpha"]
    assert segments[1] == ["beta"]


def test_tokenize_segments_stopwords_removed():
    """Stop-words are removed within each segment."""
    text = f"the quick brown{SECTION_BREAK}the lazy dog"
    segments = tokenize_segments(text)
    assert segments[0] == ["quick", "brown"]
    assert segments[1] == ["lazy", "dog"]


def test_tokenize_segments_handles_empty_and_none():
    assert tokenize_segments("") == []
    assert tokenize_segments(None) == []


def test_tokenize_flat_matches_segments():
    """tokenize() should return the same tokens as flattening segments."""
    text = f"Hello World{SECTION_BREAK}foo bar"
    flat = tokenize(text)
    segments = tokenize_segments(text)
    flattened = [t for seg in segments for t in seg]
    assert flat == flattened
