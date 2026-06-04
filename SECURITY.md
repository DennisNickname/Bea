# Bea Sicherheit

Bea enthält Gesundheits-, Foto- und Gruppendaten. Der sichere Standard ist:
kein direkter Internetzugriff auf FastAPI, sondern privates WLAN, VPN oder ein
gehärteter HTTPS-Reverse-Proxy.

## Aktive Schutzmaßnahmen

- Anmeldung mit Benutzername oder E-Mail und starkem Passwort.
- Passwörter werden als Salt + PBKDF2-Hash gespeichert.
- Session-Cookies sind `HttpOnly` und `SameSite=Strict`; per `BEA_SECURE_COOKIE=1`
  zusätzlich nur über HTTPS.
- Login, Registrierung und Passwort-Reset haben serverseitige Rate-Limits.
- Seiten, APIs, Fotos und GitHub-Update sind ohne Anmeldung gesperrt.
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
