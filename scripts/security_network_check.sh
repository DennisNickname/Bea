#!/usr/bin/env bash
set -euo pipefail

APP_PORT="${BEA_PORT:-8010}"
REQUIRE_LOCAL_BIND="${BEA_REQUIRE_LOCAL_BIND:-0}"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "Dieser Netzwerkcheck ist für Linux/Raspberry Pi gedacht."
  exit 0
fi

if ! command -v ss >/dev/null 2>&1; then
  echo "ss fehlt. Bitte iproute2 installieren."
  exit 1
fi

failures=0

echo "== Lauscher =="
ss -ltnp || true

echo
echo "== Prüfung Bea-Port $APP_PORT =="
app_lines="$(ss -ltnp | awk -v port=":$APP_PORT" '$4 ~ port {print}' || true)"
if [[ -z "$app_lines" ]]; then
  echo "WARN: Bea-Port $APP_PORT wurde nicht als Listener gefunden."
else
  echo "$app_lines"
  if echo "$app_lines" | grep -Ev '127\.0\.0\.1|::1' >/dev/null; then
    if [[ "$REQUIRE_LOCAL_BIND" == "1" ]]; then
      echo "KRITISCH: Bea lauscht im Netzwerk. Für Reverse-Proxy-Betrieb BEA_HOST=127.0.0.1 setzen."
      failures=$((failures + 1))
    else
      echo "WARN: Bea lauscht im Netzwerk. Das ist für LAN-Betrieb ok, aber nicht für Portfreigabe ins Internet."
      echo "      Für gehärteten HTTPS-Betrieb: BEA_HOST=127.0.0.1 plus Caddy/nginx/VPN verwenden."
    fi
  else
    echo "OK: Bea-Port ist nur lokal gebunden."
  fi
fi

echo
echo "== Prüfung HTTPS-Port 443 =="
https_lines="$(ss -ltnp | awk '$4 ~ /:443$/ {print}' || true)"
if [[ -z "$https_lines" ]]; then
  echo "WARN: Port 443 lauscht nicht. HTTPS/nginx ist offenbar nicht aktiv."
else
  echo "$https_lines"
  if [[ "$REQUIRE_LOCAL_BIND" == "1" ]]; then
    echo "OK: HTTPS-Port ist aktiv. Für öffentlichen Reverse-Proxy-Betrieb muss die Firewall 80/443 erlauben und $APP_PORT blockieren."
  else
    echo "OK: HTTPS-Port ist aktiv. Firewall muss trotzdem passend zum Betrieb begrenzt werden."
  fi
fi

echo
echo "== Ergebnis =="
if (( failures > 0 )); then
  echo "$failures kritische Netzwerkbefunde gefunden."
  exit 1
fi

echo "Keine kritischen Befunde. Hinweise oben trotzdem beachten."
