import sys
from pathlib import Path

# Link tests to wl1/crawler
_wl1_dir = Path(__file__).resolve().parents[2] / "wl1"
if str(_wl1_dir) not in sys.path:
    sys.path.insert(0, str(_wl1_dir))

from crawler.tokenizer import tokenize


def test_tokenize_lowercases_and_strips_punctuation():
    assert tokenize("Hello, WORLD! 123") == ["hello", "world", "123"]


def test_tokenize_removes_stopwords():
    result = tokenize("the quick brown fox jumps over the lazy dog")
    assert "the" not in result
    assert result == ["quick", "brown", "fox", "jumps", "lazy", "dog"]


def test_tokenize_handles_empty_and_none():
    assert tokenize("") == []
    assert tokenize(None) == []
