#!/bin/sh
# Starts the Neutralino shell around the E10.2 presenter-window spike (macOS). Needs Node.js (for the "neu" tool).
# The page is the same as in a browser; it opens inside a frame, as the product's shell pages do.
set -e
cd "$(dirname "$0")"
command -v node >/dev/null 2>&1 || { echo "Node.js was not found. Install it from https://nodejs.org" >&2; exit 1; }
mkdir -p resources
cp -R ../page/. resources/
[ -d bin ] || { echo "Downloading Neutralino binaries ..."; npx --yes @neutralinojs/neu@11.8.0 update; }
echo "Starting ..."
npx --yes @neutralinojs/neu@11.8.0 run
