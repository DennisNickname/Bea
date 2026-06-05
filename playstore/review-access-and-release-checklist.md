# Review- und Release-Checkliste

Stand: 5. Juni 2026.

## Öffentliche Bea-Instanz

- echte Domain festlegen, zum Beispiel `https://bea.example.de`
- HTTPS mit gültigem Zertifikat einrichten
- `/datenschutz`, `/konto-loeschung`, `/impressum` und `/gesundheitshinweis` öffentlich erreichbar machen
- produktive Login- und Passwort-Reset-Funktion mit E-Mail-Versand testen
- Konto- und Datenlöschung per E-Mail-Code testen
- keine echten Gesundheitsdaten oder Fotos in Demo-Daten verwenden

## Android Release

Der Release-Build darf nicht mit einer lokalen `.local`-Adresse gebaut werden. Deshalb erwartet der Gradle-Build jetzt eine öffentliche HTTPS-Adresse:

```bash
cd android
gradle bundleRelease -PBEA_RELEASE_SERVER_URL=https://bea.example.de
```

Für lokale Debug-Builds kann die Raspberry-Pi-Adresse überschrieben werden:

```bash
cd android
gradle assembleDebug -PBEA_DEBUG_SERVER_URL=http://raspidiss.local:8010
```

Sobald ein Gradle Wrapper vorhanden ist, sollten die Befehle mit `./gradlew` ausgeführt werden.

## App Access in der Play Console

Für Google Review vorbereiten:

- Demo-Konto mit stabiler E-Mail-Adresse
- Demo-Passwort
- Hinweis, dass die App eine WebView mit Bea-Serveradresse nutzt
- öffentliche Serveradresse
- kurze Klickanleitung:
  - App starten
  - Serveradresse eintragen
  - Verbinden
  - mit Demo-Konto anmelden
  - Startseite, Gruppen, Training, Ernährung, Fortschritt und Konto-löschen-Link prüfen

## Store und Richtlinien

- Data-Safety-Formular anhand `data-safety-entwurf.md` ausfüllen
- Health-Apps-Deklaration anhand `health-apps-declaration-entwurf.md` ausfüllen
- Inhaltsbewertung ausfüllen
- Datenschutz-URL eintragen
- Konto-löschen-URL eintragen
- Support-E-Mail eintragen
- App signieren und Play App Signing aktivieren
- geschlossene Testphase erfüllen, falls das Entwicklerkonto dazu verpflichtet ist

## Technischer Smoke-Test vor Upload

- Release-App startet
- HTTPS-Server wird geladen
- HTTP wird in Release abgewiesen
- Datenschutzbutton öffnet `/datenschutz`
- Konto-löschen-Button öffnet `/konto-loeschung`
- Fotoauswahl funktioniert
- Zurück-Taste navigiert innerhalb der WebView
- Serverwechsel funktioniert
- Login und Passwort-Reset funktionieren im Produktivmodus
