# SystemONE Pi – Installation, Bedienung, Backup und Recovery

> Kurzanleitung: SystemONE Pi mit Strom und Heimnetz verbinden, im Browser `https://systemone.local` öffnen, den Schritten folgen, QR-Code koppeln, Simulation wählen und „Meine Lampe“ testen. Es ist kein Pipercat- oder Cloudkonto nötig.

## 1. Vorbereiten und starten

Benötigt werden ein SystemONE Pi mit Netzteil, ein Router/Heimnetz sowie ein Smartphone oder Computer im selben lokalen Netz. Für den Entwicklerlauf sind Node.js 20 oder neuer und dieses Projekt erforderlich.

```sh
npm ci
npm run verify
npm start
```

Öffne `http://systemone.local:4170` oder die am Gerät angezeigte lokale Adresse. Für Pilotgeräte ist HTTPS mit gerätelokaler Identität vorgesehen (`npm run tls:provision`); eine Zertifikatswarnung darf nicht unbesehen übergangen werden. Prüfe Gerätename und Fingerprint.

## 2. Erststart bis zur ersten Lampe

1. Wähle Sprache und Darstellung.
2. Vergib einen Namen für dein Zuhause. Räume und Standort bleiben lokal; der Standort ist optional.
3. Tippe auf „Admin-Pairing starten“. Scanne den nur fünf Minuten gültigen QR-Code. Lass ihn niemanden fotografieren.
4. Wähle für den ersten sicheren Test „SystemONE Simulation“. Reale Hue-Hardware bleibt bis zur Hardwarefreigabe getrennt.
5. Nenne die Lampe „Meine Lampe“, wähle einen Raum und tippe auf „Gerät testen“.
6. Nach der Bestätigung erscheint die Lampe unter „Räume & Geräte“. Teste Ein/Aus und Helligkeit.
7. Öffne „Mehr“ → „Backup & Restore“ und erstelle die erste geprüfte Sicherung.

## 3. Tägliche Bedienung

- **Home:** Überblick, Störungen, aktive Automationen und Backupstatus.
- **Räume & Geräte:** Ein/Aus, Helligkeit, Farbe, Weißton sowie Name/Raum – nur angebotene Funktionen erscheinen.
- **Automationen:** lokale Zeit-, Sonnen- und Geräteabläufe. Ohne Standort bleiben Sonnenabläufe sicher inaktiv.
- **Mehr:** Diagnose, Backup, optionale Module, Audit und Updates.
- **App installieren:** Im Browser „SystemONE installieren“ oder „Zum Home-Bildschirm“ wählen. Smartphone und Pi müssen für Steuerung im selben lokalen Netz sein.

Bei „Nicht erreichbar“ zuerst Strom, WLAN/LAN und dasselbe Heimnetz prüfen. Ein erneuter Befehl darf erst nach Zustandsabgleich erfolgen. Cloud-Ausfall ist unerheblich; ohne lokales Netz ist keine Fernsteuerung möglich, bereits laufende lokale Automationen arbeiten weiter.

## 4. Backup und Restore

SystemONE erstellt täglich ein lokales, rotiertes Backup und führt direkt einen zustandsneutralen Restore-Test aus. In „Backup“ zeigt „Restore geprüft“ die letzte erfolgreiche Prüfung. Mit „Jetzt lokal sichern“ kann ein Zyklus sofort gestartet werden.

Für USB/NAS müssen Administratoren das Ziel vor dem Start über `SYSTEMONE_EXPORT_ROOTS` freigeben. Exporte können mit einer Passphrase ab zwölf Zeichen AES-256-GCM-verschlüsselt werden. Bewahre Passphrase und Datenträger getrennt auf; verlorene Passphrasen können nicht wiederhergestellt werden.

Restore:

1. „Backup auswählen“ und höchstens 1 MiB große JSON-Datei wählen.
2. Prüfsumme, Schema, Datum, Räume und Geräte kontrollieren.
3. Erst wenn „Backup ist gültig“ erscheint, „Geprüftes Backup wiederherstellen“ wählen.
4. Den zweiten Bestätigungsklick bewusst ausführen.
5. Räume und Simulationsgeräte prüfen. Hue-/Kamera-/Pi-hole-Credentials sind absichtlich nie im Backup und müssen lokal neu verbunden werden.

## 5. Offlinebetrieb und Störungen

- Internet aus: Core, Geräte im lokalen Netz, Zeit-/Sonnenautomationen, Backup und PWA arbeiten weiter.
- Router/LAN aus: lokale Funk-/LAN-Steuerung kann ausfallen; Automationen dürfen Fehler protokollieren und später sicher fortfahren.
- Pi-hole/Kamera/YouDo aus: optionale Module beeinträchtigen den Smart-Home-Core nicht.
- Speicherfehler: Diagnose öffnen, Datenträger/Freiplatz prüfen; SystemONE versucht die letzte atomare Sicherung.
- Updatefehler/Stromausfall: A/B-Modell rollt auf den bestätigten Slot zurück; nicht wiederholt aktivieren, bevor Diagnose geprüft wurde.

## 6. Recovery bei verlorener Admin-Session

Normales Vorgehen mit noch gültiger Owner-Session: eine neue lokale Pairing-Sitzung starten und neu scannen. Für eine vollständig gesperrte Verwaltung verlangt Recovery **physischen Zugriff plus separaten, einmal verwendbaren Recovery-Code**. Nach fünf Fehlversuchen wird Recovery gesperrt.

1. Direkt am Gerät ein Terminal öffnen und im installierten SystemONE-Verzeichnis `npm run recovery:open` ausführen. Das lokale Recoveryfenster gilt zehn Minuten; niemals über einen fremden Link oder Fernzugriff öffnen.
2. Im selben Heimnetz „Mehr“ → „Owner-Recovery“ öffnen und den getrennt verwahrten Einmalcode eingeben. Ein Browserfeld `physicalPresence` wird nicht akzeptiert – ausschließlich die lokale Datei des CLI-Befehls beweist die physische Aktion.
3. Nach erfolgreicher Prüfung widerruft SystemONE alle alten Sessions und setzt eine neue Owner-Session als `HttpOnly`-Cookie.
4. Den neu angezeigten Recovery-Code sofort getrennt/offline verwahren; der alte Code ist endgültig verbraucht.
5. Nach fünf Fehlversuchen bleibt Recovery bis zu einem bewusst dokumentierten physischen Werksreset gesperrt.

Support darf nie nach Passwort, QR-Token, API-Key, Recovery-Code oder kompletter Backup-Passphrase fragen. Für Hilfe ausschließlich den vorschaupflichtigen, redigierten Diagnoseexport verwenden.

## 7. Sichere Abschaltung und Wartung

Vor dem Trennen der Stromversorgung laufende Schreib-, Backup- oder Updatevorgänge beenden. Updates nur aus vertrauenswürdiger Quelle, nach Ed25519-/SHA-256-Prüfung und lokaler Adminfreigabe installieren. Fernwartung bleibt im MVP deaktiviert.

## Kurzer Verständlichkeitstest (für eine externe Testperson)

Ohne zusätzliche Erklärung soll die Person: (1) SystemONE öffnen, (2) QR-Pairing finden, (3) eine Simulationslampe ein-/ausschalten, (4) ein geprüftes Backup erstellen, (5) erklären, was ohne Internet weiterläuft, und (6) sagen, welche Geheimnisse Support nie erhalten darf. Zeit, Rückfragen, Fehlklicks und missverständliche Begriffe protokollieren. Bestehen: alle sechs Ziele ohne sicherheitskritische Hilfe, maximal zwei nichtkritische Rückfragen.
