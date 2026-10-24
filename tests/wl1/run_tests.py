from __future__ import annotations

import datetime
import os
import subprocess
import sys
import time
from pathlib import Path


def _resolve_project_root() -> Path:
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "wl1").is_dir() and (parent / "tests").is_dir():
            return parent
    return Path(__file__).resolve().parents[2]


def run_tests() -> int:
    root = _resolve_project_root()
    test_dir = root / "tests" / "wl1"
    logs_dir = root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    output_file_wl1 = test_dir / "test_output.txt"
    output_file_logs = logs_dir / "wl1_test_report.txt"

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sep = "=" * 80
    header = (
        f"{sep}\n"
        " MINI SEARCH ENGINE - WORKLET 1 (CRAWLER) TEST SUITE\n"
        f" Date / Time : {timestamp}\n"
        f" Target Dir  : {test_dir}\n"
        f" Python Exec : {sys.executable}\n"
        f" Platform    : {sys.platform}\n"
        f"{sep}\n"
    )

    print(header, end="")

    recorded_lines: list[str] = [header]

    # Run pytest with -s to capture all print statements from tests
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-s",
        "-v",
        str(test_dir),
    ]

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"

    start_time = time.time()

    process = subprocess.Popen(
        cmd,
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
    )

    if process.stdout:
        for line in process.stdout:
            # Echo to console
            sys.stdout.write(line)
            sys.stdout.flush()
            recorded_lines.append(line)

    process.wait()
    elapsed = time.time() - start_time

    status_str = "SUCCESS (ALL PASSED)" if process.returncode == 0 else f"FAILED (Exit Code: {process.returncode})"

    footer = (
        f"\n{sep}\n"
        " TEST EXECUTION SUMMARY\n"
        f" Status      : {status_str}\n"
        f" Duration    : {elapsed:.2f} seconds\n"
        " Output Files:\n"
        f"   - {output_file_wl1}\n"
        f"   - {output_file_logs}\n"
        f"{sep}\n"
    )

    print(footer, end="")
    recorded_lines.append(footer)

    full_output = "".join(recorded_lines)

    # Save documented output
    try:
        output_file_wl1.write_text(full_output, encoding="utf-8")
        output_file_logs.write_text(full_output, encoding="utf-8")
        print(f"\n[INFO] Documented test output successfully written to:\n  - {output_file_wl1}\n  - {output_file_logs}\n")
    except Exception as e:
        print(f"\n[WARNING] Could not write output files: {e}\n")

    return process.returncode


if __name__ == "__main__":
    code = run_tests()
    # If run in an interactive terminal where someone might have double clicked,
    # wait if standard input is attached and not in CI
    if os.environ.get("AUTOPAUSE", "0") == "1":
        input("Press Enter to exit...")
    sys.exit(code)
