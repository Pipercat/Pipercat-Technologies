# Website (Konfigurator/Lead-Erfassung)

Platzhalter für die öffentliche Pipercat-/SystemONE-Website inkl. Website-Konfigurator (siehe [`docs/product-manifest.md`](../../docs/product-manifest.md), Abschnitt 8: Konfigurator ist Lead-Erfassung, **kein Checkout** — jede Anfrage wird zu einem Projektvorgang in SystemONE HQ).

## Status

Nur Verzeichnis-Platzhalter aus `S1V2-01-002`. Umsetzung folgt in `S1V2-04-001` (datengetriebener Konfigurator für Pi/Mini/Server/Rack) und `S1V2-08-002` (produktionsreife Website). Framework-Wahl bewusst nicht in dieser Strukturierungsaufgabe vorweggenommen.

## Grenzen (bereits jetzt verbindlich)

- Übergibt Leads ausschließlich an `apps/hq-backend` (Lead → HQ → Angebotsworkflow), speichert keine Kundendaten selbst dauerhaft.
