"""Tests for the Worklet 1 CLI entry point (wl1/main.py) — seed file parsing only.

``main.py`` is loaded by file path (not ``import main``) because the module
name is too generic to import safely from ``sys.path``.
"""

import importlib.util
import sys
from pathlib import Path

# Link tests to wl1/crawler
_wl1_dir = Path(__file__).resolve().parents[2] / "wl1"
if str(_wl1_dir) not in sys.path:
    sys.path.insert(0, str(_wl1_dir))

_spec = importlib.util.spec_from_file_location("wl1_main", _wl1_dir / "main.py")
main = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(main)


# ─── Seed File Loading Tests ─────────────────────────────────────────


def test_load_seeds_ignores_comments_and_blank_lines(tmp_path):
    """Comments (#), blank lines and trailing spaces are all ignored."""
    print("\n[TEST] test_load_seeds_ignores_comments_and_blank_lines")
    seed_file = tmp_path / "seeds.txt"
    content = (
        "# A full-line comment\n"
        "\n"
        "https://example.com/1\n"
        "https://example.com/2  # trailing comment\n"
        "   https://example.com/3   \n"
    )
    seed_file.write_text(content, encoding="utf-8")
    print("  Input:    seed file containing:")
    for line in content.splitlines():
        print(f"              {line!r}")
    seeds = main.load_seeds(str(seed_file))
    expected = [
        "https://example.com/1",
        "https://example.com/2",
        "https://example.com/3",
    ]
    print(f"  Expected: {expected}")
    print(f"  Actual:   {seeds}")
    assert seeds == expected
    print("  Status:   PASS [OK]")


def test_load_seeds_comments_only_file_returns_empty_list(tmp_path):
    """A seed file with no usable URLs yields an empty list (no crash)."""
    print("\n[TEST] test_load_seeds_comments_only_file_returns_empty_list")
    seed_file = tmp_path / "seeds.txt"
    seed_file.write_text("# only comments\n\n# nothing else\n", encoding="utf-8")
    print("  Input:    seed file with only comments and blank lines")
    seeds = main.load_seeds(str(seed_file))
    print(f"  Expected: []")
    print(f"  Actual:   {seeds}")
    assert seeds == []
    print("  Status:   PASS [OK]")
