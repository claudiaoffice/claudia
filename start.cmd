@echo off
rem Start the Claudia demo (Windows). Options: see start.cmd --help
cd /d "%~dp0"
uv run python scripts/start.py %*
