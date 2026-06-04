# Bea

FastAPI-App fuer gemeinsames Fitness-Tracking mit Freunden, Challenges, Leveln, Sport- und Nahrungseintraegen.

## Bereiche

- `Dashboard`: Rangliste, Team-XP, aktive Challenges und Motivation
- `Freunde`: Mitgliedervergleich, Motivation senden und Uebungen zuweisen
- `Challenges`: Gemeinsame Fortschritte eintragen und XP-Boni sammeln
- `Sport`: Ausdauer- und Krafttraining getrennt erfassen
- `Nahrung`: Mahlzeiten, Protein, Kalorien und Wasser tracken

Die App speichert Live-Daten lokal in `data/bea_state.json`. Diese Datei wird nicht in Git committed.

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

## GitHub Update

Oben rechts in der App gibt es einen Button `GitHub Update`.

Der Button fuehrt auf dem Server aus:

```bash
git pull --ff-only
sudo systemctl restart bea.service
```

Das Installationsskript erlaubt dem Dienst gezielt diesen Neustart ohne Passwort.
