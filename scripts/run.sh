#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  echo "Virtuelle Umgebung fehlt. Bitte zuerst ausführen: bash scripts/install_pi.sh"
  exit 1
fi

. .venv/bin/activate
export BEA_SERVICE_NAME="${BEA_SERVICE_NAME:-bea.service}"
exec uvicorn app.main:app --host 0.0.0.0 --port 8010
