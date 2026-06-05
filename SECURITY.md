# Bea Sicherheit

Bea enthält Gesundheits-, Foto- und Gruppendaten. In der Entwicklungsphase läuft
die App standardmäßig ohne Login (`BEA_AUTH_REQUIRED=0`), damit UI und Funktionen
schnell getestet werden können. Der sichere Produktivstandard ist:
`BEA_AUTH_REQUIRED=1`, kein direkter Internetzugriff auf FastAPI, sondern privates
WLAN, VPN oder ein gehärteter HTTPS-Reverse-Proxy.

## Aktive Schutzmaßnahmen

- Anmeldung mit Benutzername oder E-Mail und starkem Passwort, sobald
  `BEA_AUTH_REQUIRED=1` gesetzt ist.
- Passwörter werden als Salt + PBKDF2-Hash gespeichert.
- Session-Cookies sind `HttpOnly` und `SameSite=Strict`; per `BEA_SECURE_COOKIE=1`
  zusätzlich nur über HTTPS.
- Login, Registrierung und Passwort-Reset haben serverseitige Rate-Limits.
- Konto- und Datenlöschung wird per zeitlich begrenztem E-Mail-Code bestätigt.
- Admin-Bereiche sind im Produktivbetrieb nur für `BEA_ADMIN_MEMBER_IDS` oder explizite Admin-Rollen freigegeben.
- Seiten, APIs, Fotos und GitHub-Update sind bei aktiviertem Login ohne
  Anmeldung gesperrt.
- Standardmäßig sind nur private Netze, VPN/link-local und `localhost` erlaubt.
- State- und Foto-Backup wird vor dem GitHub-Update als ZIP abgelegt.
- Sicherheitsheader und Origin-Prüfung schützen gegen einfache XSS-/Clickjacking-/
  CSRF-Risiken.
- Private Vergleichsfotos benötigen zusätzlich einen Foto-PIN.

## Betriebsstufen

### Privat/LAN

Geeignet für Raspberry Pi im Heimnetz oder Vereinsnetz ohne Router-Portfreigabe.
Der Dienst darf auf `0.0.0.0:8010` lauschen, wenn nur vertrauenswürdige Geräte im
Netz sind.

### Gehärtet

Empfohlen für echte Gruppen mit sensiblen Daten:

- Login erzwingen: `BEA_AUTH_REQUIRED=1`.
- Betreiber festlegen: `BEA_ADMIN_MEMBER_IDS=<mitglied-id>`.
- FastAPI nur lokal binden: `BEA_HOST=127.0.0.1`.
- nginx/Caddy davor mit HTTPS.
- Zugriff von außen nur über VPN oder bewusst gehärteten Reverse Proxy.
- `BEA_SECURE_COOKIE=1` setzen.
- Bei stabilem HTTPS optional `BEA_ENABLE_HSTS=1` setzen.
- `scripts/security_network_check.sh` nach Änderungen ausführen.

### Android Release

Debug-Builds dürfen lokale HTTP-Pi-Adressen nutzen. Release-Builds erzwingen
HTTPS und blockieren `http://`, damit App-Store-/Außennutzung nicht unverschlüsselt
läuft.

## Wichtige Grenzen

- Bea ersetzt keine medizinische Beratung.
- Ein öffentlich erreichbarer Pi ohne HTTPS/VPN ist nicht vorgesehen.
- Backups sollten zusätzlich außerhalb des Pi gespeichert und regelmäßig getestet werden.
