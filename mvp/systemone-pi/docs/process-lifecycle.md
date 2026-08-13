# SystemONE Pi – Prozess-Lifecycle

## Kontrollierter Stopp

SystemONE verarbeitet `SIGTERM` und `SIGINT` idempotent in dieser Reihenfolge:

1. Hue-Synchronisation und Backup-Timer stoppen.
2. Automations-Scheduler stoppen.
3. Offene SSE-Geräteströme sauber beenden.
4. Letzten gültigen lokalen Zustand atomar persistieren.
5. HTTP-/HTTPS-Server für neue Verbindungen schließen und laufende Requests abschließen.
6. Bei Erfolg mit Exitcode 0 enden; nach zehn Sekunden Timeout oder bei Fehler mit Exitcode 1 enden.

Ein zweites Signal startet keinen zweiten Persistenz- oder Close-Ablauf.

## systemd-Anforderung

Die Ziel-Pi-Unit verwendet `KillSignal=SIGTERM`, `TimeoutStopSec=15s` und `Restart=on-failure`. Vor Update, Backup-Restore oder Datenträgerwartung muss `systemctl stop systemone-pi` erfolgreich enden. Erst danach dürfen Slot oder Datenpartition getrennt beziehungsweise ersetzt werden.

## Praktischer Nachweis

```bash
PORT=4171 node server.js
# in einem zweiten Terminal
kill -TERM <pid>
```

Erwartetes Log: `SystemONE beendet: SIGTERM`. Anschließend muss der Port frei sein und ein Neustart denselben persistenten Raum-/Geräte-/Automationszustand laden.

Der lokale Entwicklungstest am 13.08.2026 bestätigte zusätzlich den SIGINT-Pfad mit `SystemONE beendet: SIGINT`. Der physische systemd-/Stromtest auf dem Ziel-Pi bleibt Teil des offenen Haushaltspiloten.
