@echo off
rem Starts the Neutralino shell with the shared test page (E0.3). Double-click this file.
rem Needs Node.js (only to download Neutralino's ~2 MB binaries with the "neu" tool).
rem "run_windows.cmd direct" starts the binary without the "neu run" harness.
rem Optional: "uv" (https://docs.astral.sh/uv/) or Python 3, for the local-server checks.
setlocal
cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 (
  echo Node.js was not found. Install it from https://nodejs.org and run this file again.
  pause
  exit /b 1
)

node "..\fetch-vendor.mjs"
if errorlevel 1 (
  echo Fetching plotly.js failed. See the message above.
  pause
  exit /b 1
)

echo Copying the shared page and the test server ...
if not exist resources mkdir resources
robocopy "..\page" "resources" /E /NFL /NDL /NJH /NJS /NP >nul
if not exist server mkdir server
robocopy "..\server" "server" /E /NFL /NDL /NJH /NJS /NP >nul

if not exist bin (
  echo Downloading Neutralino binaries ...
  call npx --yes @neutralinojs/neu@11.8.0 update
  if errorlevel 1 (
    echo Download failed. See the message above.
    pause
    exit /b 1
  )
)

if /i "%~1"=="direct" (
  rem Starts the binary itself, without the neu run development harness.
  echo Starting neutralino-win_x64.exe directly ...
  bin\neutralino-win_x64.exe --load-dir-res --path=.
  goto :done
)

echo Starting ...
call npx --yes @neutralinojs/neu@11.8.0 run
:done
echo.
echo Neutralino exited. A log may be in neutralinojs.log in this folder.
pause
