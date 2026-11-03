#!/bin/sh
# Starts one Claudia app server.
#
#   CLAUDIA_APP   computes (default), composes or creates
#
# Arguments after the image name are passed on to `python -m claudia_server` and win over the
# defaults below (for example `--no-tls` behind a TLS proxy, `--tls-name claudia.example.org`,
# `--ai /models/qwen` or `--shapes /data/shapes`).
set -eu

app="${CLAUDIA_APP:-computes}"

case "$app" in
    computes) model="claudia_computes.model:WorkbookModel" ;;
    composes) model="claudia_composes:TextModel" ;;
    creates) model="claudia_creates:SlideModel" ;;
    *)
        echo "error: CLAUDIA_APP must be computes, composes or creates, not '$app'" >&2
        exit 2
        ;;
esac

# One web app is the client of all three servers; --dir keeps the documents sealed (encrypted).
exec python -m claudia_server --model "$model" --host 0.0.0.0 --dir /data/documents --web /app/web "$@"
