@echo off
setlocal enabledelayedexpansion

:: Switch console code page to UTF-8 for clean output
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

echo ================================================================================
echo  Executing Worklet 1 (Crawler) Test Suite...
echo ================================================================================

:: Ensure we are in project root
cd /d "%~dp0"

:: Check if Python is available
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    python tests\wl1\run_tests.py
    set EXIT_CODE=!ERRORLEVEL!
) else (
    where py >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        py -3 tests\wl1\run_tests.py
        set EXIT_CODE=!ERRORLEVEL!
    ) else (
        echo [ERROR] Python was not found in PATH. Please install or add Python to PATH.
        set EXIT_CODE=1
    )
)

echo.
echo ================================================================================
echo  Test run completed with exit code: %EXIT_CODE%
echo  Documented output recorded to:
echo    - tests\wl1\test_output.txt
echo    - logs\wl1_test_report.txt
echo ================================================================================
echo.
pause
exit /b %EXIT_CODE%
