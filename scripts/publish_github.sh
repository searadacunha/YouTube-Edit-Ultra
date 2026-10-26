#!/usr/bin/env bash
# Publishes original project sources to the authenticated user's own GitHub.
set -euo pipefail
cd "$(dirname "$0")/.."
OWNER="${GITHUB_OWNER:-searadacunha}"
REPO="${GITHUB_REPO:-YouTube-Edit-Ultra}"
if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI absent: brew install gh && gh auth login" >&2
  exit 2
fi
if ! gh auth status >/dev/null 2>&1; then
  echo "Connecte ton compte via: gh auth login" >&2
  exit 2
fi
if [ ! -d .git ]; then
  git init -b main
fi
git add .
if ! git diff --cached --quiet; then
  git commit -m 'feat: sport-first one-prompt music montage pipeline'
fi
if gh repo view "$OWNER/$REPO" >/dev/null 2>&1; then
  git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$OWNER/$REPO.git"
  git push -u origin HEAD:main
else
  gh repo create "$OWNER/$REPO" --public --source=. --remote=origin --push
fi
echo "https://github.com/$OWNER/$REPO"
