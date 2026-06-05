# Data-Safety-Entwurf

Stand: 5. Juni 2026.

Dies ist eine Arbeitsvorlage für die Google-Play-Console. Sie muss vor dem Absenden mit dem tatsächlichen Produktionsbetrieb, den eingebundenen Drittanbietern und der finalen Datenschutzerklärung abgeglichen werden.

## Grundannahmen

- Die Android-App ist eine WebView-Hülle und speichert lokal nur die eingetragene Serveradresse.
- Der Bea-Server verarbeitet die eigentlichen Konto-, Fitness-, Ernährungs-, Gruppen- und Fotodaten.
- Release-Builds erzwingen HTTPS und blockieren unverschlüsselte Serveradressen.
- Es gibt keine Werbung und aktuell kein separates Analytics-SDK in der Android-Hülle.
- Nutzer können Konto- und Datenlöschung über `/konto-loeschung` anfordern und per E-Mail-Code bestätigen.

## Datenerhebung

### Personenbezogene Daten

Erhoben:

- Name
- angezeigter Spitzname
- E-Mail-Adresse
- Geburtstag
- Passwort-Hash

Zwecke:

- App-Funktionalität
- Kontoverwaltung
- Passwort-Zurücksetzung
- Missbrauchs- und Zugriffsschutz

### Gesundheits- und Fitnessdaten

Erhoben:

- Gewicht, Größe, BMI
- Hals, Schulter, Brust, Taille, Hüfte
- linker und rechter Oberschenkel
- Trainingsdaten, Sportart, Übungen, Ausdauer- und Kraftwerte
- Ernährungsdaten, Mahlzeiten, Kalorien, Flüssigkeitszufuhr
- Zielangaben, Alltag, Schlaf, Regeneration, Hobbys
- Verletzungshistorie und Trainingsfokus

Zwecke:

- personalisierte Trainings- und Ernährungspläne
- Fortschrittsauswertung
- Gamification, Level, Aufgaben und Challenges
- Gruppenranking, soweit vom Nutzer genutzt

### Fotos und Videos

Erhoben:

- private Vergleichsfotos
- Avatar- und Körperbau-Grundlagen aus Ganzkörperbildern

Zwecke:

- persönlicher Fortschrittsvergleich
- Avatar-Erstellung
- optionale spätere Community-Freigabe durch den Nutzer

Hinweis für die Play Console: Körper- und Vergleichsfotos sind besonders sensibel. Die Datenschutzerklärung muss klar erklären, wer Zugriff hat, wo gespeichert wird und wie gelöscht wird.

### App-Aktivität und soziale Daten

Erhoben:

- Gruppenmitgliedschaften
- Challenges
- Kommentare
- Likes
- Aufgabenabschlüsse
- Belohnungen und XP

Zwecke:

- Gruppenfunktionen
- Motivation
- Rankings
- Spielmechanik

### Geräte- oder andere IDs

Die aktuelle Android-Hülle fordert keine Geräte-ID-Berechtigungen an. Falls später Analytics, Push-Benachrichtigungen, Crash-Reporting oder Advertising-ID ergänzt werden, muss dieser Abschnitt neu bewertet werden.

## Datenweitergabe

Aktueller Entwurf:

- Keine Datenweitergabe für Werbung.
- Keine Verkäufe von Daten.
- Externe Dienste können beteiligt sein, wenn Nutzer sie aktiv verwenden:
  - Strava für verbundene Ausdauereinheiten
  - YouTube für verlinkte Trainings- und Mahlzeitenvideos
  - Wetterdienst, falls die Wettervorhersage produktiv über einen externen Anbieter geladen wird

Für die Play Console muss geprüft werden, ob diese Integrationen als Datenweitergabe gelten oder ob Daten ausschließlich vom Drittanbieter zum Bea-Server importiert werden.

## Sicherheitspraktiken

Anzugeben, sobald produktiv erfüllt:

- Daten werden bei Übertragung verschlüsselt: Ja, wenn die öffentliche Bea-Instanz ausschließlich über HTTPS erreichbar ist.
- Nutzer können Datenlöschung anfordern: Ja.
- Datenlöschung außerhalb der App möglich: Ja, über öffentliche URL `/konto-loeschung`.
- Daten werden nicht für Werbung verkauft: Ja.

## Noch vor Absenden prüfen

- echte Datenschutz-URL öffentlich erreichbar, nicht als PDF, nicht login-geschützt
- Betreibername in Store Listing und Datenschutztext identisch
- vollständige Speicherfristen und Löschfristen im Datenschutztext
- produktive E-Mail-Zustellung für Passwort-Reset und Löschcodes
- Umgang mit anonymisierten Gruppen- und Challenge-Spuren rechtlich geprüft
- Strava-, YouTube- und Wetterdaten in Datenschutz und Data Safety korrekt beschrieben
