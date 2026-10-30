#!/usr/bin/env bash
# Push only reviewed commits to the already configured repository.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v gh >/dev/null || { echo 'Install GitHub CLI and authenticate first.' >&2; exit 2; }
gh auth status >/dev/null 2>&1 || { echo 'Run gh auth login first.' >&2; exit 2; }
git rev-parse --git-dir >/dev/null
OWNER="${GITHUB_OWNER:-searadacunha}"
REPO="${GITHUB_REPO:-YouTube-Edit-Ultra}"
REMOTE="$(git remote get-url origin)"
case "$REMOTE" in
  "https://github.com/$OWNER/$REPO"|"https://github.com/$OWNER/$REPO.git"|"git@github.com:$OWNER/$REPO.git") ;;
  *) echo 'Configured origin differs from the intended repository; nothing pushed.' >&2; exit 2 ;;
esac
if [ -n "$(git status --porcelain)" ]; then
  echo 'Review and commit explicit public paths first. This helper never stages files.' >&2
  exit 2
fi
git fetch origin
if ! git merge-base --is-ancestor origin/main HEAD; then
  echo 'Integrate origin/main first; history will not be rewritten.' >&2
  exit 2
fi
# Inspect every outgoing commit, including files deleted in the final tree.
if git log --format= --name-only origin/main..HEAD | grep -Ei '(^|/)(JOURNAL_AGENTS\.md|\.env[^/]*|token\.json|credentials\.json|client_secret[^/]*|library|output)(/|$)|\.(mp4|mov|mkv|mp3|m4a|wav|flac)$'; then
  echo 'Private state or media appears in outgoing history. Prepare a clean public branch.' >&2
  exit 2
fi
git diff --check origin/main..HEAD
git push origin HEAD:main
echo "https://github.com/$OWNER/$REPO"
