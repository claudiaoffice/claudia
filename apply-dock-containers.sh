#!/bin/sh
# Applies the six patches that bring `dock` and `containers` into main, as identity "m".
#
#   git switch -c <your feature branch> main        # a branch from main at 2af2ef2 or later
#   sh apply-dock-containers.sh dock-containers.mbox
#
# Authors stay as the commits had them; the committer is m. Nothing is pushed.
set -eu
mbox=${1:?usage: apply-dock-containers.sh dock-containers.mbox}
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "the working tree is not clean" >&2; exit 1; }
git merge-base --is-ancestor 2af2ef2 HEAD || { echo "this branch does not contain main's 2af2ef2 (Bring clients up to date)" >&2; exit 1; }
GIT_COMMITTER_NAME=m GIT_COMMITTER_EMAIL=claudiaoffice.ai@gmail.com \
  git -c user.name=m -c user.email=claudiaoffice.ai@gmail.com -c commit.gpgsign=false am --3way "$mbox"
echo "applied. Then: uv sync && uv run python scripts/check_debt.py --fast   (and, in web/: npm ci && npx nuxt prepare && npx vitest run)"
