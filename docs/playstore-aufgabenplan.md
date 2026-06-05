# Bea Play-Store-Aufgabenplan

Stand: 5. Juni 2026, v1.0-Entwicklung, Android-WebView-App für die Bea-Webapp.

## Bereits umgesetzt

- Android-Version auf `versionName "1.0"` gesetzt und als Git-Tag `v1.0` markiert.
- Release-Build blockiert unverschlüsseltes HTTP.
- Release-Build verlangt jetzt `BEA_RELEASE_SERVER_URL`, damit keine lokale `.local`-Adresse versehentlich in eine Store-Version gelangt.
- Debug-Serveradresse kann über `BEA_DEBUG_SERVER_URL` überschrieben werden.
- Gradle Wrapper für reproduzierbare Android-Builds ergänzt.
- Android-App fragt nur die Berechtigung `INTERNET` an.
- Datenschutzseite unter `/datenschutz` ergänzt.
- Gesundheitshinweis unter `/gesundheitshinweis` ergänzt.
- Seite für Konto-/Datenlöschanfragen unter `/konto-loeschung` ergänzt.
- Android-Startmaske verlinkt Datenschutz, Gesundheitshinweis und Konto-löschen-Seite über die eingetragene Bea-Serveradresse.
- Admin-Ansicht unter `/admin/datenloeschung` ergänzt.
- Konto-/Datenlöschung entfernt Auth-Daten, Profile, Pläne, private Einträge, Strava-Verbindungen, Fotos und anonymisiert Gruppen-/Challenge-Referenzen.
- Automatische Self-Service-Löschung per E-Mail-Code unter `/konto-loeschung/bestaetigen` ergänzt.
- Admin-Bereich `/admin/datenloeschung` ist im Produktivbetrieb per Adminrolle bzw. `BEA_ADMIN_MEMBER_IDS` geschützt.
- Play-Store-Arbeitsunterlagen liegen unter `playstore/`.

## Phase 1: Recht und Datenschutz

- Echtes Impressum mit realem Betreiber, Anschrift und Kontakt ersetzen.
- Datenschutztext mit realem Betreiber, Rechtsgrundlage, Speicherdauer, Hosting, Empfängern und Löschfristen finalisieren.
- Konto- und Datenlöschung mit produktiven Betreiber-IDs und rechtlich geprüftem Audit-Prozess finalisieren.
- Medizinischen Hinweis und Grenzen der App final prüfen lassen.

## Phase 2: Android Release

- Signiertes Android App Bundle (`.aab`) bauen.
- Play App Signing einrichten.
- Upload-Key sicher speichern und dokumentieren.
- Release mit realer HTTPS-Serveradresse über `-PBEA_RELEASE_SERVER_URL=https://...` testen.

## Phase 3: Betrieb für Google Review

- Öffentliche HTTPS-Demo-Instanz bereitstellen.
- Review-Konto mit stabilen Zugangsdaten anlegen.
- In Play Console unter App Access die Zugangsdaten und Hinweise zur Bedienung hinterlegen.
- Sicherstellen, dass Demo-Daten keine echten Gesundheits- oder Fotodaten enthalten.

## Phase 4: Play Console

- Data-Safety-Formular anhand `playstore/data-safety-entwurf.md` ausfüllen.
- Health-Apps-Deklaration anhand `playstore/health-apps-declaration-entwurf.md` ausfüllen.
- Inhaltsbewertung ausfüllen.
- Store-Eintrag mit Beschreibung, Screenshots, Icon, Feature Graphic, Support-Mail und Kategorie erstellen.
- Store-Listing-Entwurf aus `playstore/store-listing-de-DE.md` finalisieren.
- Geschlossene Testphase durchführen, falls das Developer-Konto dazu verpflichtet ist.

## Phase 5: Qualitätssicherung

- Release-App auf mehreren Android-Versionen testen.
- Foto-Upload, Login, Passwort-Reset, Datenschutzlinks und Serverwechsel testen.
- Accessibility-Basischeck für WebView und zentrale Seiten durchführen.
- Keine echten Nutzerdaten in Test-, Demo- oder Store-Screenshots verwenden.
