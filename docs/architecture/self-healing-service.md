# Systemstatus-, Fehler- und Selbstheilungsdienst (Stand 17.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-006 · Systemstatus-, Fehler- und sicheren Selbstheilungsdienst implementieren`.
> Quellen: `DEC-182`, `DEC-183`. Implementierung: `apps/customer-backend/app/selfhealing.py`.

## Severity

`Severity`: `info` / `warning` / `critical` — jedes `SystemIssue` (Komponente, Schweregrad, Nachricht, Erkennungszeitpunkt) trägt genau eine dieser Stufen.

## Allowlist sicherer automatischer Aktionen

`SelfHealAction` listet sowohl sichere als auch riskante Aktionen; `SAFE_ACTIONS` ist die **einzige Quelle der Wahrheit**, geprüft im Code, nicht nur dokumentiert:

| Sicher (automatisch erlaubt) | Riskant (nie automatisch) |
|---|---|
| `restart_component` | `factory_reset` |
| `clear_cache` | `delete_all_data` |
| `reconnect_integration` | `disable_tls` |
| `restart_device_adapter` | `install_update` (Updates verlangen ausdrückliche Kundenzustimmung, `docs/product-manifest.md` §6) |

`SelfHealingService.attempt()` prüft **vor** jedem Ausführungsversuch `action not in SAFE_ACTIONS` — der zugehörige Executor wird für eine riskante Aktion **nie aufgerufen**, selbst wenn versehentlich einer registriert wurde (im Test `test_risky_action_is_blocked_and_executor_never_runs` explizit nachgewiesen: der Executor hätte einen Marker gesetzt, tut es aber nicht).

## Auditierung

Jeder Aufruf von `attempt()` — erfolgreich, fehlgeschlagen oder blockiert — erzeugt genau einen Eintrag über den `AuditRecorder`-Hook aus `S1V2-02-003`, mit allen fünf geforderten Feldern: `trigger` (Auslösegrund/Issue-Nachricht), `triggeredAt` (Zeit), `component`, `action` (`selfheal.{action}`), `result`/`outcome`.

## Fehlschlag/Wiederholung → Alarm

Aufeinanderfolgende Fehlschläge **derselben Komponente** werden gezählt (`_consecutive_failures`); ab einem konfigurierbaren Schwellwert (Standard: 3) wird ein Alarm über `AlertSink` ausgelöst. Ein einzelner Fehlschlag alarmiert noch nicht — erst die Wiederholung, wie in der Aufgabenbeschreibung gefordert. Ein Erfolg setzt den Zähler zurück.

- **`InMemoryAlertSink`** — Test-/Dev-Stand-in.
- **`EventBusAlertSink`** — produktive Variante: veröffentlicht den Alarm als `system.alert`-Event über den bereits bestehenden `EventBus`-Port (`S1V2-01-004`/`-02-004`), statt einen zweiten Benachrichtigungskanal zu erfinden.

## Tests (Definition of Done: „Tests beweisen sichere Automatik und Blockade riskanter Aktionen")

`apps/customer-backend/tests/test_selfhealing.py` (9 Tests):

- Sichere Aktion läuft erfolgreich und wird auditiert.
- Riskante Aktion wird blockiert, **Executor läuft nachweislich nie**.
- Alle nicht in `SAFE_ACTIONS` gelisteten Aktionen werden pauschal geprüft (`test_every_risky_action_is_blocked`), nicht nur ein Einzelfall.
- Einzelner Fehlschlag alarmiert noch nicht.
- Drei aufeinanderfolgende Fehlschläge alarmieren.
- Erfolg setzt den Fehlschlagzähler zurück.
- Ein defekter Executor (wirft Exception) wird als Fehlschlag behandelt, bringt den Dienst nicht zum Absturz.
- `EventBusAlertSink` veröffentlicht korrekt über den echten `EventBus`.
- Historie enthält alle Versuche mit ihren Ergebnissen.

Gesamt `apps/customer-backend`: **77/77 Tests bestanden**.

## Bewusst nicht Teil dieser Aufgabe

- Konkrete Erkennung von `SystemIssue`s (welche Komponente wann als „gestört" gilt) — das ist Beobachtungslogik, die auf Metriken/Health-Checks aus `S1V2-01-005` aufbaut, hier wird nur die Reaktion darauf modelliert.
- Persistenz der Selbstheilungs-Historie in PostgreSQL — dieselbe bewusste Grenze wie bei der Automations-Historie (`S1V2-02-005`).
- Ein tatsächlicher Genehmigungsworkflow für riskante Aktionen (z. B. über `RemoteApproval` aus `S1V2-02-001`) — hier werden riskante Aktionen ausschließlich technisch ausgeschlossen, nicht in einen Freigabe-Workflow überführt.
