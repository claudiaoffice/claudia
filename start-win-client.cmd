@echo off
rem Starts the Windows desktop client (clients\windows, the Neutralino shell) directly -- the Windows counterpart
rem of start-mac-client.sh (macOS) and start-client.sh (Linux/GTK). Like macOS and unlike Linux, there is no
rem second system interpreter to hand off to here: the Windows client itself is plain Node/TypeScript, not Python
rem at all (clients\windows\README.md's "Running it from a checkout" is the step-by-step this script automates).
rem
rem   * .venv (via "uv sync") is what the *server* runs on -- same Python 3.14 requirement as Linux and macOS, same
rem     reason (D116): the server is outside the uv workspace's own Node/TS half.
rem   * The web frontend is rebuilt every run, not just built once and left stale -- see start-client.sh's own
rem     comment on the 2026-11-06 report that caught exactly that bug for the Linux client. Skip with
rem     CLAUDIA_SKIP_WEB_BUILD=1 once you know your build is current.
rem   * The Windows client's own TypeScript (tsc, then the injected-script bundle) is rebuilt every run for the
rem     same reason. Skip with CLAUDIA_SKIP_WINDOWS_BUILD=1.
rem   * The Neutralino binary (not checked into the repo, D157) is fetched automatically with
rem     "npx @neutralinojs/neu update" the first time it is missing -- the step clients\windows\README.md otherwise
rem     has you run by hand in apps\<app>.
rem
rem Usage: start-win-client.cmd [app]   -- app defaults to "composes", the only one built so far (E5.11).
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "APP=%~1"
if "%APP%"=="" set "APP=composes"
set "APP_DIR=clients\windows\apps\%APP%"

where node >nul 2>nul
if errorlevel 1 (
    echo Claudia's Windows client needs Node.js, and none was found on PATH. 1>&2
    echo Install it from https://nodejs.org and run this again. 1>&2
    exit /b 1
)

call uv sync --quiet
if errorlevel 1 exit /b 1

if not "%CLAUDIA_SKIP_WEB_BUILD%"=="1" (
    echo Building the web app...
    pushd web
    call npm ci && call npm run build
    if errorlevel 1 (
        popd
        exit /b 1
    )
    popd
)

if not "%CLAUDIA_SKIP_WINDOWS_BUILD%"=="1" (
    echo Building the Windows client...
    pushd clients\windows
    call npm ci && call npm run build
    if errorlevel 1 (
        popd
        exit /b 1
    )
    popd
)

if not exist "%APP_DIR%" (
    echo '%APP%' has no Windows client yet -- this first version only covers composes ^(E5.11^). 1>&2
    exit /b 1
)

if "%CLAUDIA_NEUTRALINO_BIN%"=="" if not exist "%APP_DIR%\bin\neutralino-win_x64.exe" (
    echo Fetching the Neutralino binary for %APP% ^(npx @neutralinojs/neu update^)...
    pushd "%APP_DIR%"
    call npx --yes @neutralinojs/neu update
    if errorlevel 1 (
        popd
        exit /b 1
    )
    popd
)

node clients\windows\dist\launch.js %APP%
