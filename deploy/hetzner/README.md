# Bea auf Hetzner betreiben

Dieses Profil ist für einen öffentlichen Hetzner-Server mit Debian oder Ubuntu gedacht. Bea läuft dabei nicht direkt im Internet, sondern nur lokal auf `127.0.0.1:8010`. Caddy übernimmt HTTPS auf Port `443` und leitet intern an Bea weiter.

```text
Internet -> HTTPS 443 -> Caddy -> 127.0.0.1:8010 -> Bea/FastAPI
```

## Voraussetzungen

- Hetzner-Server mit Debian oder Ubuntu
- Domain oder Subdomain, z.B. `bea.deinedomain.de`
- DNS-A-Record auf die IPv4-Adresse des Servers
- optional DNS-AAAA-Record auf die IPv6-Adresse des Servers
- SSH-Zugang als normaler Benutzer mit `sudo`

## Hetzner Firewall

In der Hetzner Cloud Firewall nur diese eingehenden TCP-Ports öffnen:

- `22` für SSH, idealerweise nur von deiner eigenen IP
- `80` für HTTP-Validierung und HTTPS-Weiterleitung
- `443` für HTTPS

Port `8010` bleibt geschlossen. Bea lauscht auf Hetzner nur lokal.

## Installation

Auf dem Server:

```bash
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/DennisNickname/Bea.git Bea
cd Bea
BEA_DOMAIN=bea.deinedomain.de BEA_ACME_EMAIL=admin@deinedomain.de bash scripts/install_hetzner.sh
```

Wenn du schon eine Caddy-Konfiguration hast, legt das Skript vorher ein Backup unter `/etc/caddy/Caddyfile.backup.<zeit>` an. Für einen frischen Server ist das gewollt. Für einen Server mit mehreren Websites solltest du `deploy/hetzner/Caddyfile.template` lieber manuell in deine bestehende Caddy-Konfiguration integrieren.

## Wichtige Variablen

```bash
BEA_DOMAIN=bea.deinedomain.de
BEA_ACME_EMAIL=admin@deinedomain.de
BEA_ADMIN_MEMBER_IDS=bea
BEA_SERVICE_NAME=bea.service
```

Die Produktivumgebung steht danach in `/etc/default/bea`. Vorlage: `deploy/hetzner/bea.env.example`.

## Nach der Installation

Status prüfen:

```bash
systemctl status bea.service
systemctl status caddy
```

Sicherheitscheck:

```bash
cd ~/Bea
BEA_REQUIRE_LOCAL_BIND=1 bash scripts/security_network_check.sh
```

Bea sollte nur lokal auf `127.0.0.1:8010` lauschen. Öffentlich erreichbar ist nur:

```text
https://bea.deinedomain.de
```

## Android Release

Für die Play-Store-App muss dieselbe öffentliche HTTPS-Adresse in den Release-Build:

```bash
cd android
./gradlew bundleRelease -PBEA_RELEASE_SERVER_URL=https://bea.deinedomain.de
```

## Konto und Datenschutz

Für Internetbetrieb muss Login aktiv bleiben:

```bash
BEA_AUTH_REQUIRED=1
```

Außerdem solltest du vor echter Nutzung setzen und testen:

- `BEA_ADMIN_MEMBER_IDS`
- SMTP-Daten für Passwort-Reset und Konto-Löschcodes
- echtes Impressum
- echte Datenschutzerklärung
- Store-URLs für Datenschutz und Konto-Löschung
