@echo off
REM FX Bias Desk — Daily Data Update
REM Place this .bat file anywhere on your PC.
REM Task Scheduler runs it daily at 07:00 (adjust as needed).
REM Requires: Bloomberg Terminal open, Python installed, blpapi installed.

REM ── CONFIG ────────────────────────────────────────────────────────────────
REM Path to your local copy of the fx-desk-data repo
set REPO_DIR=C:\Users\%USERNAME%\Documents\fx-desk-data

REM Set to 1 to auto-push to GitHub after fetching (recommended)
set AUTO_GIT=1

REM ── RUN ───────────────────────────────────────────────────────────────────
echo [%date% %time%] Starting FX Desk data update...

cd /d "%REPO_DIR%"

REM Fetch data from Bloomberg
python scripts\fetch_bloomberg.py
if errorlevel 1 (
    echo ERROR: Python script failed. Is Bloomberg Terminal open?
    exit /b 1
)

echo [%date% %time%] Done.
pause
