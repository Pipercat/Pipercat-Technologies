# Eigener-Haushalt-Pilot: Runbook und Evidenz

## Vorprüfung (hardwarefrei, 2026-08-13)

`npm run pilot:dry-run` erzeugt in einem frischen temporären Datenverzeichnis einen lokalen Zustand mit Raum, Lampe und Automation, schreibt atomar, erzeugt/rotiert ein Backup, führt den vollständigen Restore-Test aus, beschädigt kontrolliert die primäre State-Datei und beweist die Recovery aus der letzten Sicherung. IDs und Gerätedaten müssen nach simuliertem Neustart stabil bleiben. Das Skript gibt maschinenlesbare JSON-Evidenz sowie priorisierte offene Gates aus und enthält keine Secrets.

## Physischer Lauf (noch offen)

1. Raspberry-Pi-Zieldatenträger frisch installieren; Version, Imagehash und Hardware notieren.
2. Ohne vorhandenes Datenverzeichnis starten, QR-pairen, Raum/Lampe/Automation anlegen.
3. Backup auf freigegebenes externes Ziel schreiben und Restore-Test prüfen.
4. Pi vollständig neu installieren; ausschließlich aus geprüftem Backup wiederherstellen; IDs, Räume, Automation und Theme vergleichen.
5. Internet trennen, LAN erhalten: lokale Steuerung/Automation/Backup prüfen.
6. LAN trennen und wiederherstellen: Offlinezustand, keine unkontrollierte Aktion, Reconnect prüfen.
7. Router neu starten: Backoff und automatische Erholung mit Zeitstempeln dokumentieren.
8. SystemONE-Prozess und Pi geordnet neu starten: Persistenz und Scheduler-Duplikatschutz prüfen.
9. Während eines A/B-Candidate-Boots kontrolliert Strom unterbrechen: bestätigten Rollbackslot und Datenpartition prüfen.
10. Jede Abweichung mit P0–P3, Zeit, Version, Reproduktion, Erwartung, Istzustand und redigierter Diagnose als Notion-Aufgabe erfassen.

## Freigaberegel

Aufgabe 46 bleibt `In progress`, bis alle zehn Schritte auf realer Zielhardware im eigenen Haushalt protokolliert sind. Hardwarefreie Tests oder Simulation ersetzen diese Abnahme nicht.
