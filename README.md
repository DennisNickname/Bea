# Bea

FastAPI-App fuer gemeinsames Fitness-Tracking mit Freunden, Challenges, Leveln, Sport- und Nahrungseintraegen.

## Bereiche

- `Dashboard`: Rangliste, Team-XP, aktive Challenges und Motivation
- `Fragebogen`: Kalorienbedarf, Trainingsplan und Ernaehrungsplan erstellen
- `Freunde`: Mitgliedervergleich, Motivation senden und Uebungen zuweisen
- `Challenges`: Gemeinsame Fortschritte eintragen und XP-Boni sammeln
- `Fitnessplan`: Wettervorhersage fuer Outdoor- oder Studio-Entscheidungen
- `Sport`: Ausdauer- und Krafttraining getrennt erfassen und YouTube-Trainingsvideos anhaengen
- `Nahrung`: Lebensmittel-Datenbank, Gerichtauswahl, Mahlzeiten, Makros, Wasser und YouTube-Mahlzeitenvideos tracken
- `Fotos`: Private Vergleichsfotos mit PIN-Schutz und optionaler Community-Freigabe
- `Integrationen`: Strava verbinden und externe Ausdauereinheiten importieren

Die App speichert Live-Daten lokal in `data/bea_state.json`. Diese Datei wird nicht in Git committed.
Private Fotos werden lokal unter `data/photos/` gespeichert und ebenfalls nicht committed.

Der Fragebogen berechnet den Kalorienbedarf mit einer Mifflin-St-Jeor-Schaetzung, Aktivitaetsfaktor und Zielanpassung.
Die Werte sind Startpunkte und sollten nach einigen Wochen anhand von Gewicht, Energie und Trainingsleistung angepasst werden.

## Lokal starten

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8010
```

Danach im Browser oeffnen:

```text
http://localhost:8010
```

## Raspberry Pi

Auf dem Raspberry Pi:

```bash
git clone https://github.com/DennisNickname/Bea.git bea
cd bea
bash scripts/install_pi.sh
```

Das Skript installiert die Abhaengigkeiten, richtet `bea.service` ein und startet den Dienst auf Port `8010`.

Manuell starten, falls kein Systemd verfuegbar ist:

```bash
./scripts/run.sh
```

Der Server laeuft auf Port `8010`.

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

Auf dem Raspberry Pi koennen die Werte in `/etc/default/bea` gesetzt werden:

```bash
STRAVA_CLIENT_ID=...
STRAVA_CLIENT_SECRET=...
STRAVA_REDIRECT_URI=http://<raspberry-pi-host>:8010/integrationen/strava/callback
```

Danach den Dienst neu starten:

```bash
sudo systemctl restart bea.service
```

Die Wettervorhersage im Fitnessplan nutzt Open-Meteo und benoetigt keinen API-Key.

## GitHub Update

Oben rechts in der App gibt es einen Button `GitHub Update`.

Der Button fuehrt auf dem Server aus:

```bash
git pull --ff-only
sudo systemctl restart bea.service
```

Das Installationsskript erlaubt dem Dienst gezielt diesen Neustart ohne Passwort.
