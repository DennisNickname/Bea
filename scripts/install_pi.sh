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
  env_file="/etc/default/bea"
  if [ ! -f "$env_file" ]; then
    sudo tee "$env_file" >/dev/null <<ENV
# Optionaler Speicherort für Live-Daten
# BEA_STATE_PATH=$project_dir/data/bea_state.json
# BEA_PHOTO_PATH=$project_dir/data/photos
# BEA_BACKUP_PATH=$project_dir/data/backups

# Netzwerk
BEA_HOST=0.0.0.0
BEA_PORT=8010

# Sicherheit
BEA_AUTH_REQUIRED=0
# Optionaler Entwicklungsnutzer ohne Login
# BEA_DEV_MEMBER_ID=bea
# BEA_PRIVATE_NETWORK_ONLY=1
# BEA_SECURE_COOKIE=1
# BEA_TRUST_PROXY_HEADERS=1
# BEA_ENABLE_HSTS=1

# Strava OAuth App Credentials
# STRAVA_CLIENT_ID=
# STRAVA_CLIENT_SECRET=
# STRAVA_REDIRECT_URI=http://raspberrypi.local:8010/integrationen/strava/callback
ENV
  fi

  sudo tee "/etc/systemd/system/$service_name" >/dev/null <<SERVICE
[Unit]
Description=Bea FastAPI
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$project_dir
ExecStart=$project_dir/scripts/run.sh
Environment=BEA_SERVICE_NAME=$service_name
Environment=BEA_RESTART_STRATEGY=self-terminate
Environment=BEA_HOST=0.0.0.0
Environment=BEA_PORT=8010
Environment=BEA_AUTH_REQUIRED=0
EnvironmentFile=-$env_file
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

  echo "Installation fertig. Dienst läuft als $service_name auf Port 8010 bzw. BEA_PORT."
  echo "Sicherheitscheck: bash scripts/security_network_check.sh"
else
  echo "Installation fertig. Starte manuell mit: ./scripts/run.sh"
fi
