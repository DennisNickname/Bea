# ToDofuerBea

Offene Punkte, die noch externe Daten, echte Konten, rechtliche Angaben oder eine groessere Umsetzung brauchen.

## Play Store Pflichtaufgaben

- Echte oeffentliche HTTPS-Adresse fuer Bea festlegen, z.B. `https://bea.example.de`.
- Raspberry-Pi- oder Serverbetrieb hinter HTTPS/VPN/Reverse Proxy fuer Google Review erreichbar machen.
- Echtes Impressum mit realem Betreiber, Anschrift, Kontakt und Verantwortlichen ersetzen.
- Oeffentliche Datenschutz-URL finalisieren und in Play Console hinterlegen.
- Data-Safety-Formular in Play Console ausfuellen.
- Health-Apps-Deklaration in Play Console ausfuellen.
- Inhaltsbewertung in Play Console ausfuellen.
- Support-E-Mail-Adresse fuer den Store festlegen.
- Store-Beschreibung, Kurzbeschreibung, Screenshots, App-Icon und Feature Graphic erstellen.
- Falls noetig: Closed Test mit mindestens 12 Testern ueber 14 Tage abschliessen.

## App- und Code-Aufgaben

- Admin-Rollen/Rechte fuer `/admin/datenloeschung` bauen, bevor Login im Produktivbetrieb wieder aktiviert wird.
- Identitaetspruefung fuer Loeschanfragen definieren, z.B. E-Mail-Code oder manuelle Betreiberpruefung.
- Loeschprotokoll rechtlich pruefen: Welche anonymisierten Gruppen-/Challenge-Spuren duerfen bleiben, welche muessen komplett entfernt werden?
- Demo-/Review-Konto fuer Google anlegen und dokumentieren.
- Release-Default-Server von `https://raspidiss.local` auf die echte oeffentliche HTTPS-Adresse aendern.
- Gradle Wrapper hinzufuegen, damit der Android-Build reproduzierbar ohne lokal installiertes Gradle laeuft.
- Signiertes `.aab` bauen und Play App Signing einrichten.
- Upload-Key sicher ablegen und Wiederherstellungsweg dokumentieren.
- Release-Build mit Login, Datenschutzlink, Gesundheitshinweis, Serverwechsel und Foto-Upload testen.

## Rechtliche Pruefung

- Datenschutztext, Impressum, Gesundheitshinweis und Belohnungsmechaniken rechtlich pruefen lassen.
- Klaeren, ob die App nur privat/fuer eine Gruppe oder oeffentlich fuer beliebige Nutzer angeboten wird.
- Klaeren, ob Strava, YouTube-Einbettungen und Wetterdaten in Datenschutz und Store-Deklaration erwaehnt werden muessen.
