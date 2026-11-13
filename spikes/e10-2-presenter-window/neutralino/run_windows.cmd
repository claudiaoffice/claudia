@echo off
rem Starts the Neutralino shell around the E10.2 presenter-window spike (Windows). Needs Node.js (for the "neu" tool).
rem The page is the same as in a browser; it opens inside a frame, as the product's shell pages do.
setlocal
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js was not found. Install it from https://nodejs.org and run this file again.
  pause
  exit /b 1
)
if not exist resources mkdir resources
robocopy "..\page" "resources" /E /NFL /NDL /NJH /NJS /NP >nul
if not exist bin (
  echo Downloading Neutralino binaries ...
  call npx --yes @neutralinojs/neu@11.8.0 update
)
echo Starting ...
call npx --yes @neutralinojs/neu@11.8.0 run
echo.
echo Neutralino exited. A log may be in neutralinojs.log in this folder.
pause
