#!/bin/sh
# Starts the Claudia server: all three apps (D430), each app's documents in /data/documents/<app>.
#
#   CLAUDIA_APP         optional: computes, composes or creates serves that one app only, with its documents
#                       directly in /data/documents (the old one-app container, D433)
#   PORT                the port to listen on (default 8765); serverless platforms set it
#   CLAUDIA_ALLOW_HOST  the name people type in the address bar, more than one separated by commas; needed behind a
#                       proxy or on a platform that gives the container its own address, because the server answers
#                       only to localhost, IP addresses and the names it is told about
#   CLAUDIA_DEMO=1      a demo for serverless platforms: documents live in memory (gone when the container stops,
#                       at most 100 of them), no disk is needed, and the traffic is plain HTTP because the platform
#                       encrypts in front of the container (--no-tls --behind-proxy)
#   CLAUDIA_ADMIN and CLAUDIA_ADMIN_PASSWORD
#                       name the first administrator at start if there is none (D1376), as a platform's secret
#                       variables give them: the password goes to a file only the server's account can read, and the
#                       variable is removed before the server starts. Without them the server says a setup code in its
#                       log (D1371). CLAUDIA_ADMIN with CLAUDIA_ADMIN_PASSWORD_FILE works as well (the server reads both)
#
# Arguments after the image name are passed on to `python -m claudia_server` and win over the
# defaults below (for example `--no-tls --behind-proxy` behind a TLS proxy, `--tls-name claudia.example.org`,
# `--allow-host myserver` for a name that people type and that is not a certificate name, `--ai /models/qwen` or
# `--shapes /data/shapes`). The server answers only to localhost, IP addresses and the names it is told about.
set -eu

model=""
case "${CLAUDIA_APP:-}" in
    "") ;;
    computes) model="claudia_computes.model:WorkbookModel" ;;
    composes) model="claudia_composes:TextModel" ;;
    creates) model="claudia_creates:SlideModel" ;;
    *)
        echo "error: CLAUDIA_APP must be computes, composes or creates (or not set: all three), not '$CLAUDIA_APP'" >&2
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

if [ -n "${CLAUDIA_ADMIN_PASSWORD:-}" ]; then
    if [ -z "${CLAUDIA_ADMIN:-}" ]; then
        echo "error: CLAUDIA_ADMIN_PASSWORD needs CLAUDIA_ADMIN, the name of the first administrator" >&2
        exit 2
    fi
    password_file=$(umask 077 && mktemp)
    printf '%s\n' "$CLAUDIA_ADMIN_PASSWORD" >"$password_file"
    unset CLAUDIA_ADMIN_PASSWORD
    set -- --admin "$CLAUDIA_ADMIN" --admin-password-file "$password_file" "$@"
fi

if [ -n "$model" ]; then
    set -- --model "$model" "$@"
fi

# The web app is the client of every app.
exec python -m claudia_server --host 0.0.0.0 --port "${PORT:-8765}" --web /app/web --hyphenation /app/hyphenation "$@"
