@echo off
rem =====================================================================
rem  Mini Search Engine - Worklet 1 test suite (clickable launcher)
rem
rem  Double-click this file to run every test in tests\wl1.
rem  The complete run is recorded to:
rem      tests\wl1\reports\wl1_test_report_<timestamp>.txt
rem      tests\wl1\reports\wl1_junit_<timestamp>.xml
rem      tests\wl1\reports\latest_report.txt
rem =====================================================================
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found on this machine.
    echo Install Python 3.10+ from https://www.python.org/downloads/ and try again.
    pause
    exit /b 1
)

python "run_wl1_tests.py"
set RESULT=%errorlevel%

echo.
if "%RESULT%"=="0" (
    echo All tests passed. Full output recorded in tests\wl1\reports\
) else (
    echo Some tests failed or the run was interrupted - see the report above.
)
pause
exit /b %RESULT%
