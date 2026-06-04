#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

host="${BEA_HOST:-0.0.0.0}"
port="${BEA_PORT:-8010}"
service_name="${BEA_SERVICE_NAME:-bea.service}"

if [ ! -d ".venv" ]; then
  echo "Virtuelle Umgebung fehlt. Bitte zuerst ausführen: bash scripts/install_pi.sh"
  exit 1
fi

. .venv/bin/activate
export BEA_SERVICE_NAME="$service_name"

set +e
python -c 'import errno, socket, sys
host = sys.argv[1]
port = int(sys.argv[2])
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.bind((host, port))
except OSError as exc:
    sys.exit(2 if exc.errno in (errno.EADDRINUSE, 10048) else 1)
finally:
    sock.close()
' "$host" "$port"
port_status=$?
set -e

if [ "$port_status" -eq 2 ]; then
  echo "Port $port ist bereits belegt."
  if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet "$service_name"; then
    echo "Bea läuft bereits als systemd-Dienst: $service_name"
    echo "Nach einem git pull bitte den Dienst neu starten:"
    echo "  sudo systemctl restart $service_name"
    echo "Status prüfen:"
    echo "  systemctl status $service_name"
    exit 0
  fi
  echo "Bitte prüfe, welcher Prozess den Port nutzt:"
  echo "  sudo ss -ltnp 'sport = :$port'"
  echo "Oder starte Bea testweise auf einem anderen Port:"
  echo "  BEA_PORT=8011 ./scripts/run.sh"
  exit 1
elif [ "$port_status" -ne 0 ]; then
  echo "Port $port konnte nicht geprüft werden. Starte trotzdem."
fi

exec uvicorn app.main:app --host "$host" --port "$port"
