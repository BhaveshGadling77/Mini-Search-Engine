"""Tests for the Fetcher — mocked (no network required)."""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

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


# ─── Existing Tests (with print output) ──────────────────────────────


def test_fetch_returns_html_on_200():
    print("\n[TEST] test_fetch_returns_html_on_200")
    print("  Input:    URL='https://example.com/', mock HTTP 200 with body '<html>ok</html>'")
    expected = "<html>ok</html>"
    fetcher = Fetcher(politeness_delay_s=0, respect_robots=False)
    with patch.object(fetcher.session, "get", return_value=_make_response(200, "<html>ok</html>")):
        html = fetcher.fetch("https://example.com/")
    print(f"  Expected: {expected!r}")
    print(f"  Actual:   {html!r}")
    assert html == expected
    print("  Status:   PASS [OK]")


def test_fetch_returns_none_on_404():
    print("\n[TEST] test_fetch_returns_none_on_404")
    print("  Input:    URL='https://example.com/missing', mock HTTP 404")
    fetcher = Fetcher(politeness_delay_s=0, respect_robots=False)
    with patch.object(fetcher.session, "get", return_value=_make_response(404)):
        result = fetcher.fetch("https://example.com/missing")
    print(f"  Expected: None")
    print(f"  Actual:   {result!r}")
    assert result is None
    print("  Status:   PASS [OK]")


def test_fetch_returns_none_on_request_exception():
    print("\n[TEST] test_fetch_returns_none_on_request_exception")
    print("  Input:    URL='https://example.com/', mock ConnectionError('offline')")
    fetcher = Fetcher(politeness_delay_s=0, respect_robots=False)
    fetcher.backoff_s = 0
    with patch.object(
        fetcher.session, "get", side_effect=requests.ConnectionError("offline")
    ):
        result = fetcher.fetch("https://example.com/")
    print(f"  Expected: None")
    print(f"  Actual:   {result!r}")
    assert result is None
    print("  Status:   PASS [OK]")


def test_fetch_retries_on_503():
    print("\n[TEST] test_fetch_retries_on_503")
    print("  Input:    URL='https://example.com/', mock [503, 200] sequence")
    expected = "<html>retry-ok</html>"
    fetcher = Fetcher(politeness_delay_s=0, respect_robots=False)
    fetcher.backoff_s = 0
    responses = [_make_response(503), _make_response(200, "<html>retry-ok</html>")]
    with patch.object(fetcher.session, "get", side_effect=responses):
        html = fetcher.fetch("https://example.com/")
    print(f"  Expected: {expected!r}")
    print(f"  Actual:   {html!r}")
    assert html == expected
    print("  Status:   PASS [OK]")


def test_fetch_respects_zero_delay():
    """Verify that passing delay=0 actually uses 0, not the config default."""
    print("\n[TEST] test_fetch_respects_zero_delay")
    print("  Input:    Fetcher(politeness_delay_s=0)")
    fetcher = Fetcher(politeness_delay_s=0, respect_robots=False)
    print(f"  Expected: politeness_delay_s == 0")
    print(f"  Actual:   politeness_delay_s == {fetcher.politeness_delay_s}")
    assert fetcher.politeness_delay_s == 0
    print("  Status:   PASS [OK]")


# ─── Additional Tests ────────────────────────────────────────────────


def test_fetch_returns_none_on_timeout():
    """Verify that a requests.Timeout exception returns None."""
    print("\n[TEST] test_fetch_returns_none_on_timeout")
    print("  Input:    URL='https://example.com/', mock Timeout exception")
    fetcher = Fetcher(politeness_delay_s=0, respect_robots=False)
    fetcher.backoff_s = 0
    with patch.object(
        fetcher.session, "get", side_effect=requests.Timeout("timed out")
    ):
        result = fetcher.fetch("https://example.com/")
    print(f"  Expected: None")
    print(f"  Actual:   {result!r}")
    assert result is None
    print("  Status:   PASS [OK]")


def test_fetch_returns_none_on_500():
    """Verify that a 500 Internal Server Error (after retries) returns None."""
    print("\n[TEST] test_fetch_returns_none_on_500")
    print("  Input:    URL='https://example.com/', mock HTTP 500 (all retries)")
    fetcher = Fetcher(politeness_delay_s=0, respect_robots=False)
    fetcher.backoff_s = 0
    # All retries return 500
    responses = [_make_response(500)] * fetcher.max_retries
    with patch.object(fetcher.session, "get", side_effect=responses):
        result = fetcher.fetch("https://example.com/")
    print(f"  Expected: None")
    print(f"  Actual:   {result!r}")
    assert result is None
    print("  Status:   PASS [OK]")


def test_fetch_retries_on_429():
    """Verify that a 429 Too Many Requests triggers retry and succeeds."""
    print("\n[TEST] test_fetch_retries_on_429")
    print("  Input:    URL='https://example.com/', mock [429, 200] sequence")
    expected = "<html>rate-limit-ok</html>"
    fetcher = Fetcher(politeness_delay_s=0, respect_robots=False)
    fetcher.backoff_s = 0
    responses = [_make_response(429), _make_response(200, expected)]
    with patch.object(fetcher.session, "get", side_effect=responses):
        html = fetcher.fetch("https://example.com/")
    print(f"  Expected: {expected!r}")
    print(f"  Actual:   {html!r}")
    assert html == expected
    print("  Status:   PASS [OK]")


def test_fetcher_close_closes_session():
    """Verify that close() calls session.close()."""
    print("\n[TEST] test_fetcher_close_closes_session")
    print("  Input:    Fetcher.close()")
    fetcher = Fetcher(politeness_delay_s=0, respect_robots=False)
    with patch.object(fetcher.session, "close") as mock_close:
        fetcher.close()
    called = mock_close.called
    print(f"  Expected: session.close() called = True")
    print(f"  Actual:   session.close() called = {called}")
    assert called
    print("  Status:   PASS [OK]")


def test_fetcher_uses_custom_user_agent():
    """Verify that a custom user-agent is set on the session headers."""
    print("\n[TEST] test_fetcher_uses_custom_user_agent")
    custom_ua = "TestBot/1.0"
    print(f"  Input:    Fetcher(user_agent='{custom_ua}')")
    fetcher = Fetcher(politeness_delay_s=0, respect_robots=False, user_agent=custom_ua)
    actual_ua = fetcher.session.headers.get("User-Agent")
    print(f"  Expected: User-Agent == '{custom_ua}'")
    print(f"  Actual:   User-Agent == '{actual_ua}'")
    assert actual_ua == custom_ua
    print("  Status:   PASS [OK]")


# ─── Robots & Politeness Tests ───────────────────────────────────────


def test_fetch_skipped_when_robots_disallows():
    """Verify a robots.txt disallow blocks the fetch without any HTTP call."""
    print("\n[TEST] test_fetch_skipped_when_robots_disallows")
    print("  Input:    URL='https://example.com/private', robots.txt disallows it")
    fetcher = Fetcher(politeness_delay_s=0, respect_robots=True)
    robots = MagicMock()
    robots.can_fetch.return_value = False
    with patch.object(Fetcher, "_load_robots", return_value=robots):
        with patch.object(fetcher.session, "get") as mock_get:
            result = fetcher.fetch("https://example.com/private")
    print(f"  Expected: None, and no HTTP request made")
    print(f"  Actual:   {result!r}, http_called={mock_get.called}")
    assert result is None
    assert not mock_get.called
    print("  Status:   PASS [OK]")


def test_fetch_politeness_sleeps_between_same_domain_requests():
    """Verify a politeness delay is applied before a same-domain request."""
    print("\n[TEST] test_fetch_politeness_sleeps_between_same_domain_requests")
    print("  Input:    politeness_delay_s=2.0, same domain hit twice in a row")
    fetcher = Fetcher(politeness_delay_s=2.0, respect_robots=False)
    # Pretend a request to this domain just happened.
    fetcher._last_request_time["example.com"] = time.monotonic()
    with patch.object(
        fetcher.session, "get", return_value=_make_response(200, "<html>ok</html>")
    ):
        with patch("crawler.fetcher.time.sleep") as mock_sleep:
            html = fetcher.fetch("https://example.com/")
    called = mock_sleep.called
    delay = mock_sleep.call_args[0][0] if called else None
    print(f"  Expected: sleep() called once with delay in (0, 2.0]")
    print(f"  Actual:   called={called}, delay={delay!r}, html={html!r}")
    assert called
    assert 0 < delay <= 2.0
    assert html == "<html>ok</html>"
    print("  Status:   PASS [OK]")
