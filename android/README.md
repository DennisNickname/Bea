# Bea Android

Native Android-Hülle für die Bea-Webapp auf dem Raspberry Pi.

Die App enthält keinen eigenen Fitness-Server und keine eigene Datenbank. Sie lädt die zentrale Bea-Instanz per WebView, damit Daten, Login, GitHub-Update und Fotos weiterhin auf dem Raspberry Pi bleiben.

## Funktionen

- Erster Start fragt nach der Server-Adresse, z.B. `http://raspidiss.local:8010`.
- Server-Adresse wird lokal auf dem Gerät gespeichert und kann über den Button `Server` geändert werden.
- `Neu laden` aktualisiert die WebView.
- Android-Zurück-Taste navigiert innerhalb der Bea-Seiten zurück.
- Foto- und Avatar-Uploads öffnen die Android-Dateiauswahl für Bilder.
- Debug-Builds erlauben HTTP zu lokalen Raspberry-Pi-Adressen.
- Release-Builds erzwingen HTTPS und blockieren unverschlüsselte `http://`-Server.

## Bauen

1. Android Studio installieren.
2. Ordner `android/` als Projekt öffnen.
3. Bei Bedarf Android SDK 35 installieren lassen.
4. `Build > Build Bundle(s) / APK(s) > Build APK(s)` ausführen.

Alternativ mit installiertem Gradle:

```bash
cd android
gradle assembleDebug
```

Für eine Store- oder Release-Version:

```bash
cd android
gradle bundleRelease
```

Der Release-Build erwartet eine Bea-Instanz hinter HTTPS, VPN oder Reverse Proxy mit gültigem Zertifikat.

Das Debug-APK liegt danach unter:

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

## Auf dem Handy nutzen

Der Raspberry Pi muss im selben WLAN oder per VPN erreichbar sein. In der App nicht `localhost` eintragen, sondern den Hostnamen oder die IP-Adresse des Pi:

```text
http://raspidiss.local:8010
http://192.168.178.40:8010
```

Wenn die Android-App keine Verbindung bekommt, zuerst im Handy-Browser dieselbe Adresse testen.
