# A/B-Update und Rollback auf dem Ziel-Pi

Stand: 13.08.2026 · Bearbeitet von: Pipercat Technologies

## Modell

- Zwei unveränderliche Anwendungsslots A/B; nur der inaktive Slot wird beschrieben.
- Die lokale Datenpartition `systemone-data` liegt außerhalb beider Slots. Ein Slotwechsel verändert ihre Generation nicht.
- Nach Signaturprüfung und Adminfreigabe wird der inaktive Slot `staged`, anschließend einmalig als `candidate` gebootet.
- Innerhalb von fünf Minuten müssen Prozess-, API-, Speicher- und Migrationscheck erfolgreich sein. Erst dann wird der Slot `confirmed`.
- Fehlerhafter Healthcheck oder Migration rollt sofort zurück. Ein Stromausfall/Neustart mit unbestätigtem Boot wird konservativ als Fehler behandelt und rollt ebenfalls zurück.

## Praktisches Pilotprotokoll auf Raspberry Pi

1. Vollständiges Backup der separaten Datenpartition erstellen und Prüfsumme protokollieren.
2. Bestätigten Slot und Version erfassen; signiertes Paket in den inaktiven Slot schreiben und dessen Hash erneut prüfen.
3. Bootziel einmalig auf den Candidate-Slot setzen, Watchdog/Bootzähler aktivieren und neu starten.
4. `/api/health`, lokalen Speicher, Automationen und Migrationsstatus innerhalb des Fünf-Minuten-Fensters prüfen.
5. Erfolgsfall: Candidate bestätigen und Bootzähler löschen. Fehlerfall: vorherigen Slot setzen und neu starten.
6. Stromausfalltest während „staged“, während Slotwechsel und vor Bestätigung durchführen; jeweils vorherigen Slot und unveränderte Datenprüfsumme belegen.
7. Eine absichtlich fehlschlagende Migration testen; Rollback und unveränderte Datengeneration dokumentieren.

Der Codezustandsautomat und alle Fehlerpfade sind hardwarefrei getestet. Der praktische Stromausfallnachweis muss auf dem endgültigen Pi-/Speicherlayout wiederholt und im Pilotprotokoll ergänzt werden.
