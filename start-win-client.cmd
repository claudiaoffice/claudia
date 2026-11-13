@echo off
rem   start-win-client.cmd [composes|computes|creates] [--server URL] [--debug]      (the app defaults to composes)
rem
rem Starts the Windows desktop client (clients\windows, the Neutralino shell) directly -- the Windows counterpart
rem of start-mac-client.sh (macOS) and start-client.sh (Linux/GTK), with the same arguments. Like macOS and unlike
rem Linux, there is no second system interpreter to hand off to here: the Windows client itself is plain
rem Node/TypeScript, not Python at all (clients\windows\README.md's "Running it from a checkout" is the step-by-step
rem this script automates).
rem
rem   * .venv (via "uv sync") is what the *server* runs on -- same Python 3.14 requirement as Linux and macOS, same
rem     reason (D116): the server is outside the uv workspace's own Node/TS half. Synced with --no-dev: the root
rem     "dev" dependency group (pytest, mypy, ruff, vulture, sphinx, myst-parser...) is for working on the repo's
rem     own code and docs, not for running a client to test it, and myst-parser's own pyyaml dependency has no
rem     prebuilt wheel yet for every Python/OS combination (hit on a real Windows run, 2026-11-09: PyYAML 6.0.3
rem     tried to compile its optional C extension and failed with "Microsoft Visual C++ 14.0 or greater is
rem     required" -- no C toolchain on that machine, and none should be needed just to start this client).
rem   * The web frontend is rebuilt every run, not just built once and left stale -- see start-client.sh's own
rem     comment on the 2026-11-06 report that caught exactly that bug for the Linux client. Skip with
rem     CLAUDIA_SKIP_WEB_BUILD=1 once you know your build is current.
rem   * The Windows client's own TypeScript and the three app pages (tsc, then the shell page and the core of each
rem     app) are rebuilt every run for the same reason. Skip with CLAUDIA_SKIP_WINDOWS_BUILD=1.
rem   * The Neutralino binary and client library (not checked into the repo, D157) are fetched automatically with
rem     "npx @neutralinojs/neu update" the first time they are missing -- the step clients\windows\README.md otherwise
rem     has you run by hand in apps\<app>.
rem
rem "--server URL" connects to a server (https; plain http only for this computer) instead of starting one here.
rem The checkout must be in a folder without spaces in its path. The arguments after the app are handed on unchanged.
rem
rem (No labels and no goto in this file: it is checked in with LF line endings, and cmd can lose its place in a
rem batch file that has them when it jumps to a label.)
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem The first argument names the app if it is one; anything else (--debug...) is for the launcher, and the app is composes.
set "APP=composes"
set "ARGS=%*"
for %%A in (composes computes creates) do (
    if /i "%~1"=="%%A" (
        set "APP=%%A"
        set "ARGS=!ARGS:*%%A=!"
    )
)
set "APP_DIR=clients\windows\apps\!APP!"

where node >nul 2>nul
if errorlevel 1 (
    echo Claudia's Windows client needs Node.js ^(version 22 or newer^), and none was found on PATH. 1>&2
    echo Install it from https://nodejs.org and run this again. 1>&2
    exit /b 1
)

call uv sync --quiet --no-dev
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

set "NEEDS_NEUTRALINO="
if not exist "!APP_DIR!\js\neutralino.js" set "NEEDS_NEUTRALINO=1"
if "%CLAUDIA_NEUTRALINO_BIN%"=="" if not exist "!APP_DIR!\bin\neutralino-win_x64.exe" set "NEEDS_NEUTRALINO=1"
if defined NEEDS_NEUTRALINO (
    echo Fetching Neutralino for !APP! ^(npx @neutralinojs/neu update^)...
    pushd "!APP_DIR!"
    call npx --yes @neutralinojs/neu update
    if errorlevel 1 (
        popd
        exit /b 1
    )
    popd
)

node clients\windows\dist\launch.js !APP! !ARGS!
exit /b %errorlevel%
