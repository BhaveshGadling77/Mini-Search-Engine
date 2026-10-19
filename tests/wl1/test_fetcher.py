"""Tests for the Fetcher — mocked (no network required)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

# Link tests to wl1/crawler
_wl1_dir = Path(__file__).resolve().parents[2] / "wl1"
if str(_wl1_dir) not in sys.path:
    sys.path.insert(0, str(_wl1_dir))

from crawler.fetcher import Fetcher


def _make_response(status_code: int, text: str = "<html></html>") -> MagicMock:
    """Create a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


def test_fetch_returns_html_on_200():
    fetcher = Fetcher(politeness_delay_s=0, respect_robots=False)
    with patch.object(fetcher.session, "get", return_value=_make_response(200, "<html>ok</html>")):
        html = fetcher.fetch("https://example.com/")
    assert html == "<html>ok</html>"


def test_fetch_returns_none_on_404():
    fetcher = Fetcher(politeness_delay_s=0, respect_robots=False)
    with patch.object(fetcher.session, "get", return_value=_make_response(404)):
        result = fetcher.fetch("https://example.com/missing")
    assert result is None


def test_fetch_returns_none_on_request_exception():
    fetcher = Fetcher(politeness_delay_s=0, respect_robots=False)
    with patch.object(
        fetcher.session, "get", side_effect=requests.ConnectionError("offline")
    ):
        result = fetcher.fetch("https://example.com/")
    assert result is None


def test_fetch_retries_on_503():
    fetcher = Fetcher(politeness_delay_s=0, respect_robots=False)
    responses = [_make_response(503), _make_response(200, "<html>retry-ok</html>")]
    with patch.object(fetcher.session, "get", side_effect=responses):
        html = fetcher.fetch("https://example.com/")
    assert html == "<html>retry-ok</html>"


def test_fetch_respects_zero_delay():
    """Verify that passing delay=0 actually uses 0, not the config default."""
    fetcher = Fetcher(politeness_delay_s=0, respect_robots=False)
    assert fetcher.politeness_delay_s == 0
