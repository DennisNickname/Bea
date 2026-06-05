# To-do für Bea

Offene Punkte, die noch externe Daten, echte Konten, rechtliche Angaben oder eine größere Umsetzung brauchen.

## Play Store Pflichtaufgaben

- Echte öffentliche HTTPS-Adresse für Bea festlegen, z.B. `https://bea.example.de`.
- Raspberry-Pi- oder Serverbetrieb hinter HTTPS/VPN/Reverse Proxy für Google Review erreichbar machen.
- Echtes Impressum mit realem Betreiber, Anschrift, Kontakt und Verantwortlichen ersetzen.
- Öffentliche Datenschutz-URL finalisieren und in Play Console hinterlegen.
- Data-Safety-Formular in Play Console anhand `playstore/data-safety-entwurf.md` ausfüllen.
- Health-Apps-Deklaration in Play Console anhand `playstore/health-apps-declaration-entwurf.md` ausfüllen.
- Inhaltsbewertung in Play Console ausfüllen.
- Support-E-Mail-Adresse für den Store festlegen.
- Store-Beschreibung, Kurzbeschreibung, Screenshots, App-Icon und Feature Graphic erstellen.
- Falls nötig: Closed Test mit mindestens 12 Testern über 14 Tage abschließen.

## App- und Code-Aufgaben

- Produktive Betreiber-IDs in `BEA_ADMIN_MEMBER_IDS` festlegen und testen.
- E-Mail-Zustellung für Lösch-Codes produktiv konfigurieren und testen.
- Löschprotokoll rechtlich prüfen: Welche anonymisierten Gruppen-/Challenge-Spuren dürfen bleiben, welche müssen komplett entfernt werden?
- Demo-/Review-Konto für Google anlegen und dokumentieren.
- Release-Build mit echter öffentlicher HTTPS-Adresse bauen: `-PBEA_RELEASE_SERVER_URL=https://...`.
- Signiertes `.aab` bauen und Play App Signing einrichten.
- Upload-Key sicher ablegen und Wiederherstellungsweg dokumentieren.
- Release-Build mit Login, Datenschutzlink, Gesundheitshinweis, Serverwechsel und Foto-Upload testen.

## Rechtliche Prüfung

- Datenschutztext, Impressum, Gesundheitshinweis und Belohnungsmechaniken rechtlich prüfen lassen.
- Klären, ob die App nur privat/für eine Gruppe oder öffentlich für beliebige Nutzer angeboten wird.
- Klären, ob Strava, YouTube-Einbettungen und Wetterdaten in Datenschutz und Store-Deklaration erwähnt werden müssen.
