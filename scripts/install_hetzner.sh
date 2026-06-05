#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

domain="${BEA_DOMAIN:-}"
if [[ -z "$domain" || "$domain" == "bea.example.de" || "$domain" == http://* || "$domain" == https://* ]]; then
  echo "Bitte mit echter Domain ohne Protokoll starten, z.B.:"
  echo "  BEA_DOMAIN=bea.deinedomain.de BEA_ACME_EMAIL=admin@deinedomain.de bash scripts/install_hetzner.sh"
  exit 2
fi

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "Dieses Skript ist für Debian/Ubuntu auf einem Hetzner-Server gedacht."
  exit 2
fi

if ! command -v sudo >/dev/null 2>&1; then
  echo "sudo fehlt. Bitte als Benutzer mit sudo-Rechten ausführen."
  exit 1
fi

if [[ "$(id -u)" -eq 0 && -z "${BEA_SERVICE_USER:-}" ]]; then
  echo "Bitte nicht direkt als root ausführen."
  echo "Nutze einen normalen Benutzer mit sudo oder setze bewusst BEA_SERVICE_USER=<benutzer>."
  exit 2
fi

project_dir="$(pwd)"
service_name="${BEA_SERVICE_NAME:-bea.service}"
service_user="${BEA_SERVICE_USER:-$(whoami)}"
app_port="${BEA_PORT:-8010}"
admin_ids="${BEA_ADMIN_MEMBER_IDS:-bea}"
acme_email="${BEA_ACME_EMAIL:-}"
env_file="/etc/default/bea"
caddy_file="/etc/caddy/Caddyfile"

echo "== Pakete installieren =="
sudo apt-get update
sudo apt-get install -y ca-certificates curl git gpg python3 python3-pip python3-venv

if ! command -v caddy >/dev/null 2>&1; then
  echo "== Caddy installieren =="
  sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
  sudo rm -f /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  sudo apt-get update
  sudo apt-get install -y caddy
fi

echo "== Python-Umgebung vorbereiten =="
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
mkdir -p data/photos data/backups

echo "== Bea-Umgebung schreiben =="
if [[ -f "$env_file" && "${BEA_OVERWRITE_ENV:-0}" != "1" ]]; then
  echo "$env_file existiert bereits und bleibt unverändert."
  echo "Setze BEA_OVERWRITE_ENV=1, wenn das Skript die Datei neu schreiben soll."
else
  sudo tee "$env_file" >/dev/null <<ENV
# Bea Produktivumgebung für Hetzner
BEA_HOST=127.0.0.1
BEA_PORT=$app_port
BEA_AUTH_REQUIRED=1
BEA_PRIVATE_NETWORK_ONLY=0
BEA_SECURE_COOKIE=1
BEA_TRUST_PROXY_HEADERS=1
BEA_ENABLE_HSTS=1
BEA_ADMIN_MEMBER_IDS=$admin_ids
BEA_STATE_PATH=$project_dir/data/bea_state.json
BEA_PHOTO_PATH=$project_dir/data/photos
BEA_BACKUP_PATH=$project_dir/data/backups

# E-Mail für Passwort-Reset und Konto-Löschcodes
# BEA_MAIL_HOST=smtp.example.com
# BEA_MAIL_PORT=587
# BEA_MAIL_USER=
# BEA_MAIL_PASS=
# BEA_MAIL_FROM=noreply@$domain
# BEA_MAIL_USE_TLS=1

# Strava
# STRAVA_CLIENT_ID=
# STRAVA_CLIENT_SECRET=
# STRAVA_REDIRECT_URI=https://$domain/integrationen/strava/callback
ENV
fi

echo "== systemd-Dienst schreiben =="
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
EnvironmentFile=$env_file
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
systemctl_path="$(command -v systemctl)"
echo "$service_user ALL=(root) NOPASSWD: $systemctl_path restart $service_name" | sudo tee "$sudoers_file" >/dev/null
sudo chmod 440 "$sudoers_file"
sudo visudo -cf "$sudoers_file" >/dev/null

echo "== Caddy konfigurieren =="
if [[ -f "$caddy_file" && ! -f "$caddy_file.bea-original" ]]; then
  sudo cp "$caddy_file" "$caddy_file.bea-original"
fi

if [[ -f "$caddy_file" ]] && ! grep -q "# Bea Hetzner deployment" "$caddy_file"; then
  backup_file="$caddy_file.backup.$(date +%Y%m%d%H%M%S)"
  sudo cp "$caddy_file" "$backup_file"
  echo "Bestehende Caddyfile wurde gesichert: $backup_file"
fi

if [[ -n "$acme_email" ]]; then
  acme_block="{
    email $acme_email
}"
else
  acme_block=""
fi

sudo tee "$caddy_file" >/dev/null <<CADDY
# Bea Hetzner deployment
$acme_block

$domain {
    encode zstd gzip

    header {
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        Referrer-Policy "same-origin"
        Permissions-Policy "camera=(self), microphone=(), geolocation=()"
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
    }

    reverse_proxy 127.0.0.1:$app_port {
        header_up X-Forwarded-Proto {scheme}
        header_up X-Forwarded-Host {host}
    }
}
CADDY

sudo caddy fmt --overwrite "$caddy_file"
sudo caddy validate --config "$caddy_file"
sudo systemctl enable caddy
sudo systemctl reload caddy || sudo systemctl restart caddy

echo "== Netzwerkcheck =="
BEA_REQUIRE_LOCAL_BIND=1 BEA_PORT="$app_port" bash scripts/security_network_check.sh || true

echo
echo "Installation fertig."
echo "Bea: https://$domain"
echo "Dienst: systemctl status $service_name"
echo "Caddy:  systemctl status caddy"
