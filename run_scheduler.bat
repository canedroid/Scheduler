@echo off
rem ---------------------------------------------------------------------------
rem Project Scheduler - Solo Leveling themed markdown gate monitor
rem Launches the background monitor. Double-click or run from Task Scheduler.
rem ---------------------------------------------------------------------------
cd /d "%~dp0"

set "PY="
where py >nul 2>nul
if %errorlevel%==0 (
    for /f "delims=" %%i in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PY=%%i"
)
if not defined PY (
    where python >nul 2>nul
    if %errorlevel%==0 set "PY=python"
)
if not defined PY (
    echo [Scheduler] Python 3 not found. Install the launcher or add python to PATH.
    pause
    exit /b 1
)

start "Scheduler" /min "%PY%" main.py
exit /b 0