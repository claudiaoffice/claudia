#!/bin/sh
# Starts one Claudia app server.
#
#   CLAUDIA_APP         computes (default), composes or creates
#   PORT                the port to listen on (default 8765); serverless platforms set it
#   CLAUDIA_ALLOW_HOST  the name people type in the address bar, more than one separated by commas; needed behind a
#                       proxy or on a platform that gives the container its own address, because the server answers
#                       only to localhost, IP addresses and the names it is told about
#   CLAUDIA_DEMO=1      a demo for serverless platforms: documents live in memory (gone when the container stops,
#                       at most 100 of them), no disk is needed, and the traffic is plain HTTP because the platform
#                       encrypts in front of the container (--no-tls --behind-proxy)
#
# Arguments after the image name are passed on to `python -m claudia_server` and win over the
# defaults below (for example `--no-tls --behind-proxy` behind a TLS proxy, `--tls-name claudia.example.org`,
# `--allow-host myserver` for a name that people type and that is not a certificate name, `--ai /models/qwen` or
# `--shapes /data/shapes`). The server answers only to localhost, IP addresses and the names it is told about.
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

# What the command line adds comes last, so that it wins.
if [ "${CLAUDIA_DEMO:-}" = 1 ]; then
    set -- --no-tls --behind-proxy --max-documents 100 "$@"
else
    set -- --dir /data/documents "$@" # sealed (encrypted) documents
fi

if [ -n "${CLAUDIA_ALLOW_HOST:-}" ]; then
    set -f # a host name is not a pattern
    old_ifs=$IFS
    IFS=,
    for name in $CLAUDIA_ALLOW_HOST; do
        set -- --allow-host "$name" "$@"
    done
    IFS=$old_ifs
    set +f
fi

# One web app is the client of all three servers.
exec python -m claudia_server --model "$model" --host 0.0.0.0 --port "${PORT:-8765}" --web /app/web --fonts /app/fonts --hyphenation /app/hyphenation "$@"
