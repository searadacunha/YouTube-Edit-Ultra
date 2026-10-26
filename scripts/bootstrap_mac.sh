#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

PY="/opt/homebrew/bin/python3.12"

if [[ ! -x "$PY" ]]; then
  echo "ERREUR : Python 3.12 introuvable"
  exit 1
fi

for bin in ffmpeg ffprobe; do
  if ! command -v "$bin" >/dev/null 2>&1 ||
     ! "$bin" -version >/dev/null 2>&1; then
    echo "ERREUR : $bin absent ou inutilisable"
    exit 1
  fi
done

"$PY" -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e '.[all,dev]'

ultra init
ultra doctor
