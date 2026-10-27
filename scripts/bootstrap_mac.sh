#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

ULTRA_PYTHON_BIN="${ULTRA_PYTHON:-}"
if [[ -z "$ULTRA_PYTHON_BIN" ]]; then
  for candidate in python3.12 python3.13 python3.11 python3 \
      /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
      ULTRA_PYTHON_BIN="$(command -v "$candidate")"
      break
    fi
  done
fi
if [[ -z "$ULTRA_PYTHON_BIN" ]] ||
   ! "$ULTRA_PYTHON_BIN" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
  echo "ERREUR : Python 3.11+ requis. Installer via brew install python@3.12" >&2
  echo "Ou définir ULTRA_PYTHON avec le chemin de votre Python compatible." >&2
  exit 1
fi

for bin in ffmpeg ffprobe; do
  if ! command -v "$bin" >/dev/null 2>&1 ||
     ! "$bin" -version >/dev/null 2>&1; then
    echo "ERREUR : $bin absent ou inutilisable"
    exit 1
  fi
done

"$ULTRA_PYTHON_BIN" -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e '.[all]'

ultra init
ultra doctor
