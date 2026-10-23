"""One-click test runner for the Worklet 1 (crawler & document model) suite.

Runs every test in tests/wl1 and *records* the complete run so it can be kept
as a log, pasted into documentation, or attached to a report:

    tests/wl1/reports/wl1_test_report_<timestamp>.txt
        Human-readable record. Every test prints its Input / Expected /
        Actual values, and the file ends with a machine-parsed RECORD
        SUMMARY (totals, pass/fail, duration, file paths).

    tests/wl1/reports/wl1_junit_<timestamp>.xml
        Machine-readable record (JUnit XML) — openable by CI systems
        (GitHub Actions, GitLab, Jenkins) and test-report viewers.

    tests/wl1/reports/latest_report.txt / latest_junit.xml
        Copies of the most recent run, so the newest record is easy to find.

How to run
----------
* Windows : double-click ``run_wl1_tests.bat`` (same folder as this file)
* Any OS  : ``python tests/wl1/run_wl1_tests.py`` (works from any directory)
* Plain   : ``python -m pytest tests/wl1 -v -s``

The exit code is 0 only when every test passes, so the runner can also be
used in CI pipelines.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent           # .../tests/wl1
PROJECT_ROOT = TESTS_DIR.parent.parent               # repository root
REPORTS_DIR = TESTS_DIR / "reports"

# pytest flags:
#   -v              one line per test (name + PASSED/FAILED)
#   -s              let each test's [TEST] prints flow through (recorded live)
#   -ra             short summary of failures/errors, if any
#   --durations=10  list the slowest tests (useful for documenting performance)
PYTEST_ARGS = ["-v", "-s", "-ra", "--durations=10"]


def _pytest_version() -> str:
    try:
        import pytest

        return pytest.__version__
    except ImportError:
        return "not installed"


def _junit_stats(junit_path: Path) -> dict | None:
    """Parse pytest's JUnit XML into a small stats dict (None if unreadable)."""
    try:
        root = ET.parse(junit_path).getroot()
    except (ET.ParseError, OSError):
        return None
    suite = root if root.tag == "testsuite" else root.find(".//testsuite")
    if suite is None:
        return None

    def _num(key: str) -> int:
        return int(float(suite.get(key, "0")))

    total = _num("tests")
    failed = _num("failures")
    errors = _num("errors")
    skipped = _num("skipped")
    return {
        "total": total,
        "passed": max(total - failed - errors - skipped, 0),
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
        "time_s": float(suite.get("time", 0.0)),
    }


def _summary_lines(
    stats: dict | None,
    exit_code: int,
    started_at: datetime,
    elapsed_s: float,
    report_path: Path,
    junit_path: Path,
) -> list[str]:
    """Build the RECORD SUMMARY block shown on screen and written to the report."""
    stats = stats or {}
    overall = "ALL TESTS PASSED" if exit_code == 0 else "TEST FAILURES DETECTED"
    return [
        "",
        "=" * 78,
        "RECORD SUMMARY",
        "=" * 78,
        f"Run started : {started_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Duration    : {elapsed_s:.1f} s (wall clock)",
        f"Total tests : {stats.get('total', '?')}",
        f"Passed      : {stats.get('passed', '?')}",
        f"Failed      : {stats.get('failed', '?')}",
        f"Errors      : {stats.get('errors', '?')}",
        f"Skipped     : {stats.get('skipped', '?')}",
        f"Exit code   : {exit_code} (0 = success)",
        f"Overall     : {overall}",
        "-" * 78,
        f"Text record : {report_path}",
        f"JUnit XML   : {junit_path}",
        f"Latest copy : {REPORTS_DIR / 'latest_report.txt'}",
        "=" * 78,
    ]


def main() -> int:
    # UTF-8 console output so the PASS tick renders everywhere.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    started_at = datetime.now()
    stamp = started_at.strftime("%Y%m%d_%H%M%S")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"wl1_test_report_{stamp}.txt"
    junit_path = REPORTS_DIR / f"wl1_junit_{stamp}.xml"

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        *PYTEST_ARGS,
        f"--junitxml={junit_path}",
        str(TESTS_DIR),
    ]

    print("Mini Search Engine - Worklet 1 test run")
    print(f"  Test directory : {TESTS_DIR}")
    print(f"  Recording to   : {report_path}")
    print("=" * 78)

    # Force UTF-8 in the child so the tests' '✓' glyph survives the pipe.
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    wall_start = time.perf_counter()
    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        bufsize=1,
    )

    # Tee the run: everything streams to the console AND lands in the report.
    with report_path.open("w", encoding="utf-8", newline="\n") as report:
        header = [
            "=" * 78,
            " MINI SEARCH ENGINE - WORKLET 1 (CRAWLER & DOCUMENT MODEL) TEST REPORT",
            "=" * 78,
            f" Generated : {started_at.strftime('%Y-%m-%d %H:%M:%S')}",
            " Platform  : "
            f"{platform.platform()} / Python {platform.python_version()} "
            f"/ pytest {_pytest_version()}",
            f" Test dir  : {TESTS_DIR.relative_to(PROJECT_ROOT)}",
            f" Command   : {' '.join(cmd)}",
            "-" * 78,
        ]
        for line in header:
            report.write(line + "\n")

        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            report.write(line)

        exit_code = proc.wait()
        elapsed = time.perf_counter() - wall_start

        stats = _junit_stats(junit_path)
        for line in _summary_lines(
            stats, exit_code, started_at, elapsed, report_path, junit_path
        ):
            report.write(line + "\n")

    # Keep an always-fresh copy of the newest record.
    shutil.copyfile(report_path, REPORTS_DIR / "latest_report.txt")
    if junit_path.exists():
        shutil.copyfile(junit_path, REPORTS_DIR / "latest_junit.xml")

    print("\n".join(_summary_lines(stats, exit_code, started_at, elapsed, report_path, junit_path)))
    return 0 if exit_code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
