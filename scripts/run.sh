#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  echo "Virtuelle Umgebung fehlt. Bitte zuerst ausfuehren: bash scripts/install_pi.sh"
  exit 1
fi

. .venv/bin/activate
exec uvicorn app.main:app --host 0.0.0.0 --port 8010
