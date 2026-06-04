#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

service_name="${BEA_SERVICE_NAME:-bea.service}"
project_dir="$(pwd)"
service_user="${SUDO_USER:-$(whoami)}"

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

systemctl_path="$(command -v systemctl || true)"
sudo_path="$(command -v sudo || true)"

if [ -n "$systemctl_path" ] && [ -n "$sudo_path" ]; then
  sudo tee "/etc/systemd/system/$service_name" >/dev/null <<SERVICE
[Unit]
Description=Bea FastAPI
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$project_dir
ExecStart=$project_dir/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8010
Environment=BEA_SERVICE_NAME=$service_name
Restart=always
RestartSec=3
User=$service_user

[Install]
WantedBy=multi-user.target
SERVICE

  sudo systemctl daemon-reload
  sudo systemctl enable "$service_name"
  sudo systemctl restart "$service_name"

  sudoers_file="/etc/sudoers.d/bea-update"
  echo "$service_user ALL=(root) NOPASSWD: $systemctl_path restart $service_name" | sudo tee "$sudoers_file" >/dev/null
  sudo chmod 440 "$sudoers_file"
  sudo visudo -cf "$sudoers_file" >/dev/null

  echo "Installation fertig. Dienst laeuft als $service_name auf Port 8010."
else
  echo "Installation fertig. Starte manuell mit: ./scripts/run.sh"
fi
