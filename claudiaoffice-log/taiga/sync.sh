#!/usr/bin/env bash
# Sync the backlog and the bug tracker with Taiga (see README.md next to this file).
#
#   sync.sh pull [--dry-run]     Taiga's changes into the repo's files
#   sync.sh push [--dry-run]     what is new in the repo into Taiga
#
# Any other option (--theirs, --only backlog|bugs) is passed on to sync.py.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    sed -n '2,8s/^# \{0,1\}//p' "${BASH_SOURCE[0]}"
    exit "${1:-0}"
}

case "${1:-}" in
    pull | push) ;;
    -h | --help | help) usage 0 ;;
    *) usage 2 ;;
esac

exec python3 "$here/sync.py" "$@"
