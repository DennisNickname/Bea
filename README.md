# Bea

FastAPI-App für gemeinsames Fitness-Tracking mit Freunden, Challenges, Leveln, Sport- und Nahrungseinträgen.

## Bereiche

- `Dashboard`: Rangliste, Team-XP, aktive Challenges und Motivation
- `Heute`: Persönliches Questboard mit Coach-Hinweis, Tageskiste, Loot, Ausrüstung, Story, Achievements und Gruppen-Raids
- `Check-in`: Beim ersten Anmelden den Startplan erstellen und alle 90 Tage Fortschritte neu bewerten
- `Glossar`: Levelnamen, XP-Bereiche, Tagesbosse und wöchentliche Endgegner
- `Freunde`: Mitgliedervergleich, Motivation senden und Übungen zuweisen
- `Challenges`: Gemeinsame Fortschritte eintragen und XP-Boni sammeln
- `Fitnessplan`: Wettervorhersage für Outdoor- oder Studio-Entscheidungen
- `Sport`: Ausdauer- und Krafttraining getrennt erfassen und YouTube-Trainingsvideos anhängen
- `Nahrung`: Lebensmittel-Datenbank, Gerichtauswahl, Mahlzeiten, Makros, Wasser und YouTube-Mahlzeitenvideos tracken
- `Fotos`: Private Vergleichsfotos mit PIN-Schutz und optionaler Community-Freigabe
- `Integrationen`: Strava verbinden und externe Ausdauereinheiten importieren

Challenge-Bonus-XP sind Richtwerte: Bea berechnet sie aus Zielwert, Einheit und Bereich, begrenzt Eingaben
serverseitig und verteilt Fortschritts-XP proportional zum Aufwand. So kann niemand durch frei gewählte Fantasie-XP
schneller hochleveln.

Die App speichert Live-Daten lokal in `data/bea_state.json`. Diese Datei wird nicht in Git committed.
Private Fotos werden lokal unter `data/photos/` gespeichert und ebenfalls nicht committed.

Der Check-in berechnet den Kalorienbedarf mit einer Mifflin-St-Jeor-Schätzung, Aktivitätsfaktor und Zielanpassung.
Er erscheint beim ersten Anmelden und danach alle 90 Tage auf dem Dashboard. Nach jeder Antwort werden Trainingsplan,
Ernährungsplan, Regeneration und progressive Steigerungen neu berechnet.

## Datensicherheit

Bea läuft in der Entwicklungsphase standardmäßig ohne Login. Dafür ist `BEA_AUTH_REQUIRED=0` gesetzt und Bea nutzt
`BEA_DEV_MEMBER_ID` oder den Testnutzer `bea` als aktiven Teilnehmer. Für den produktiven Betrieb setzt du
`BEA_AUTH_REQUIRED=1`; dann ist Bea passwortgeschützt. Bei der Erstanmeldung werden Name, angezeigter
Spitzname/Benutzername, Geburtstag, E-Mail-Adresse und ein sicheres Passwort abgefragt. Auf der Login-Seite werden
keine Mitglieder mehr aufgelistet; die Anmeldung läuft über Benutzername oder E-Mail-Adresse. Passwörter werden nicht
im Klartext gespeichert, sondern als Salt + PBKDF2-Hash in der lokalen State-Datei abgelegt. Bei aktiviertem Login
werden Seiten, APIs, Fotos und der GitHub-Update-Endpunkt ohne gültige Anmeldung blockiert.

Zusätzlich setzt Bea Sicherheitsheader, prüft bei schreibenden Anfragen die Herkunft und begrenzt Login-,
Registrierungs- und Passwort-Reset-Versuche serverseitig. Vor einem GitHub-Update wird automatisch ein ZIP-Backup von
State-Datei und Fotos unter `data/backups/` angelegt. Details stehen in [`SECURITY.md`](SECURITY.md).

Wenn ein Passwort vergessen wurde, kann ein zeitlich begrenzter Code an die hinterlegte E-Mail-Adresse geschickt
werden. Dafür können auf dem Raspberry Pi SMTP-Daten in `/etc/default/bea` gesetzt werden:

```bash
BEA_MAIL_HOST=smtp.example.com
BEA_MAIL_PORT=587
BEA_MAIL_USER=...
BEA_MAIL_PASS=...
BEA_MAIL_FROM=noreply@example.com
BEA_MAIL_USE_TLS=1
```

Ohne SMTP-Konfiguration wird kein externer Mailversand erzwungen. Der Code wird dann für den lokalen Testbetrieb in
der internen Auth-Outbox der State-Datei abgelegt.

Für echte Nutzung sollte der Raspberry Pi nicht offen aus dem Internet erreichbar sein. Nutzt ein privates WLAN, VPN
oder einen Reverse Proxy mit HTTPS. Wenn HTTPS davor geschaltet ist, in `/etc/default/bea` zusätzlich setzen:

```bash
BEA_SECURE_COOKIE=1
```

Dann werden Session-Cookies nur noch über HTTPS übertragen.

Standardmäßig akzeptiert Bea nur Zugriffe aus privaten Netzen wie `192.168.x.x`, `10.x.x.x`, VPN oder `localhost`.
Nur wenn die App bewusst hinter einem sicheren Reverse Proxy betrieben wird, kann diese Sperre deaktiviert werden:

```bash
BEA_PRIVATE_NETWORK_ONLY=0
```

Wenn Bea hinter nginx/Caddy mit HTTPS läuft, sollte Uvicorn nur lokal lauschen:

```bash
BEA_HOST=127.0.0.1
BEA_SECURE_COOKIE=1
BEA_TRUST_PROXY_HEADERS=1
```

Eine nginx-Vorlage liegt unter `deploy/nginx/bea-https.conf.template`. Der Netzwerkcheck läuft auf dem Pi mit:

```bash
bash scripts/security_network_check.sh
```

## Lokal starten

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8010
```

Danach im Browser öffnen:

```text
http://localhost:8010
```

## Android App

Im Ordner `android/` liegt eine native Android-App als WebView-Hülle für Bea. Sie verbindet sich mit der laufenden
Bea-Instanz auf dem Raspberry Pi und nutzt dieselben Logins, Daten und Foto-Uploads.

Debug-Builds dürfen lokale HTTP-Adressen wie `http://raspidiss.local:8010` nutzen. Release-Builds erzwingen HTTPS und
blockieren unverschlüsselte `http://`-Serveradressen.

Build-Hinweise stehen in [`android/README.md`](android/README.md). Beim ersten Start der App als Server-Adresse nicht
`localhost`, sondern den Raspberry-Pi-Host eintragen, zum Beispiel:

```text
http://raspidiss.local:8010
```

## Raspberry Pi

Auf dem Raspberry Pi:

```bash
git clone https://github.com/DennisNickname/Bea.git bea
cd bea
bash scripts/install_pi.sh
```

Das Skript installiert die Abhängigkeiten, richtet `bea.service` ein und startet den Dienst auf Port `8010`.
Nach Änderungen an der Dienstvorlage kann das Skript erneut ausgeführt werden; vorhandene Daten bleiben erhalten.
Alternativ reicht danach ein Dienstneustart:

```bash
sudo systemctl restart bea.service
```

Status und Logs prüfen:

```bash
systemctl status bea.service
journalctl -u bea.service -f
```

Manuell starten, falls kein Systemd verfügbar ist:

```bash
./scripts/run.sh
```

Der Server läuft auf Port `8010`. Wenn `bea.service` bereits läuft, ist dieser Port schon belegt. Dann nicht zusätzlich
`./scripts/run.sh` starten, sondern den Dienst mit `sudo systemctl restart bea.service` neu starten. Für einen manuellen
Test zuerst den Dienst stoppen:

```bash
sudo systemctl stop bea.service
./scripts/run.sh
```

Optional kann ein anderer Speicherort gesetzt werden:

```bash
BEA_STATE_PATH=/home/pi/bea-data/state.json ./scripts/run.sh
```

Optional kann auch der Foto-Speicherort gesetzt werden:

```bash
BEA_PHOTO_PATH=/home/pi/bea-photos ./scripts/run.sh
```

## Strava verbinden

Lege in Strava eine API-Anwendung an und trage als Redirect URI ein:

```text
http://<raspberry-pi-host>:8010/integrationen/strava/callback
```

Auf dem Raspberry Pi können die Werte in `/etc/default/bea` gesetzt werden:

```bash
STRAVA_CLIENT_ID=...
STRAVA_CLIENT_SECRET=...
STRAVA_REDIRECT_URI=http://<raspberry-pi-host>:8010/integrationen/strava/callback
```

Danach den Dienst neu starten:

```bash
sudo systemctl restart bea.service
```

Die Wettervorhersage im Fitnessplan nutzt Open-Meteo und benötigt keinen API-Key.

## GitHub Update

In der linken Seitenleiste gibt es den Button `GitHub Update`.

Der Button führt auf dem Server aus:

```bash
git pull --ff-only
```

Nach einem erfolgreichen Pull fordert Bea automatisch einen Neustart an. Läuft Bea über `./scripts/run.sh`, startet
das Skript den Server direkt wieder neu. Läuft Bea als systemd-Dienst, beendet sich der Prozess und wird von systemd
oder dem `run.sh`-Supervisor neu gestartet.

Wichtig nach dem Update, das diese Neustartlogik einführt: Auf dem Raspberry Pi einmal ausführen, damit die neue
systemd-Unit `scripts/run.sh` als Supervisor nutzt:

```bash
cd ~/bea
git pull
bash scripts/install_pi.sh
```
