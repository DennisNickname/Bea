# Bea Play-Store-Aufgabenplan

Stand: v1.0-Entwicklung, Android-WebView-App fuer die Bea-Webapp.

## Bereits umgesetzt

- Android-Version auf `versionName "1.0"` gesetzt und als Git-Tag `v1.0` markiert.
- Release-Build blockiert unverschluesseltes HTTP.
- Android-App fragt nur die Berechtigung `INTERNET` an.
- Datenschutzseite unter `/datenschutz` ergaenzt.
- Gesundheitshinweis unter `/gesundheitshinweis` ergaenzt.
- Seite fuer Konto-/Datenloeschanfragen unter `/konto-loeschung` ergaenzt.
- Android-Startmaske verlinkt Datenschutz und Gesundheitshinweis ueber die eingetragene Bea-Serveradresse.

## Phase 1: Recht und Datenschutz

- Echtes Impressum mit realem Betreiber, Anschrift und Kontakt ersetzen.
- Datenschutztext mit realem Betreiber, Rechtsgrundlage, Speicherdauer, Hosting, Empfaengern und Loeschfristen finalisieren.
- Konto- und Datenloeschung als vollstaendige, bestaetigte Funktion umsetzen.
- Medizinischen Hinweis und Grenzen der App final pruefen lassen.

## Phase 2: Android Release

- Gradle Wrapper (`gradlew`, `gradlew.bat`, Wrapper-JAR/Properties) hinzufuegen.
- Signiertes Android App Bundle (`.aab`) bauen.
- Play App Signing einrichten.
- Upload-Key sicher speichern und dokumentieren.
- Release mit realer HTTPS-Serveradresse testen.

## Phase 3: Betrieb fuer Google Review

- Oeffentliche HTTPS-Demo-Instanz bereitstellen.
- Review-Konto mit stabilen Zugangsdaten anlegen.
- In Play Console unter App Access die Zugangsdaten und Hinweise zur Bedienung hinterlegen.
- Sicherstellen, dass Demo-Daten keine echten Gesundheits- oder Fotodaten enthalten.

## Phase 4: Play Console

- Data-Safety-Formular ausfuellen.
- Health-Apps-Deklaration ausfuellen.
- Inhaltsbewertung ausfuellen.
- Store-Eintrag mit Beschreibung, Screenshots, Icon, Feature Graphic, Support-Mail und Kategorie erstellen.
- Geschlossene Testphase durchfuehren, falls das Developer-Konto dazu verpflichtet ist.

## Phase 5: Qualitaetssicherung

- Release-App auf mehreren Android-Versionen testen.
- Foto-Upload, Login, Passwort-Reset, Datenschutzlinks und Serverwechsel testen.
- Accessibility-Basischeck fuer WebView und zentrale Seiten durchfuehren.
- Keine echten Nutzerdaten in Test-, Demo- oder Store-Screenshots verwenden.
