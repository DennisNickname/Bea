# Bea

Kleines FastAPI-Grundgeruest fuer Bea.

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

Starten:

```bash
./scripts/run.sh
```

Der Server laeuft auf Port `8010`.
