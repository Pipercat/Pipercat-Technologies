# Provisioning / Image Tooling (HQ)

Platzhalter-Modul für die HQ-Flash-/Provisioning-Funktion (Notion-Aufgabe `S1V2-03-005 · HQ-Flash- und Provisioning-Engine für neue SystemONE-Geräte bauen`).

## Grenzen (bereits jetzt verbindlich, aus Notion-Vorgabe)

- Provisioning-Schlüssel nur im HQ, nie in einem Kundensystem-Paket.
- Nie automatisch beliebige angeschlossene Datenträger überschreiben — jede Flash-Aktion braucht eine eindeutige Bestätigung und sichtbare Geräteinformationen, bevor sie ausgeführt wird.

## Status

Nur Verzeichnis-Platzhalter aus `S1V2-01-002`. Implementierung ist eigene, spätere Aufgabe (`S1V2-03-005`) — hier bewusst nicht vorgezogen, um keine ungeprüfte Datenträger-Schreiblogik ohne Sicherheits-Review einzuführen.
