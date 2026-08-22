# Automations-Kernmodell (Stand 17.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-005 · Automations-Kernmodell mit Triggern, Bedingungen, Aktionen und Historie implementieren`.
> Quelle: bestehende Automationsanforderungen aus dem Altplan (Node-Pilot `mvp/systemone-pi/lib/automations.js`/`scheduler.js`). Implementierung: `apps/customer-backend/app/domain/automation_*.py`.

## Modell

- **Trigger** (`automation_types.py`, diskriminierte Union): `DeviceStateTrigger` (Gerätezustand erreicht einen Vergleich), `TimeTrigger` (`HH:MM`, täglich), `SunEventTrigger` (`sunrise`/`sunset` + Offset in Minuten).
- **Bedingungen:** `DeviceStateCondition` — dieselbe Form wie ein `DeviceStateTrigger`, aber als „muss zum Ausführungszeitpunkt zutreffen"-Prüfung statt „löst bei Änderung aus". Operatoren `equals`/`not_equals`/`above`/`below` — bewusst dieselben vier wie im bestehenden Node-Piloten, für Kontinuität.
- **Aktionen:** `Action` = `device_id` + typisierter `CapabilityCommand` (aus `S1V2-02-002`) — eine Automation führt beliebig viele Aktionen sequenziell aus.
- **`Automation`:** `id`, `household_id`, `name`, `enabled`, `trigger`, `conditions: list[...]`, `actions: list[...]`.

## Verantwortungsgrenze zu Home Assistant

`AutomationEngine` spricht ausschließlich mit `DeviceService` (`S1V2-02-002`), nie mit einem Adapter direkt — die Engine weiß nicht, ob ein Gerät simuliert ist oder später über `HomeAssistantAdapter` läuft. Das ist die geforderte Kapselung „Verantwortung zwischen SystemONE und HA kapseln".

## Validierung gegen Capabilities

`AutomationEngine.register()` ruft zuerst `validate()` auf: jede in Trigger/Bedingungen/Aktionen referenzierte `device_id`/`capability`-Kombination muss auf einem existierenden Gerät tatsächlich vorhanden sein, sonst `AutomationValidationError` — eine Automation für ein nicht (mehr) vorhandenes Capability kann gar nicht erst registriert werden.

## Sichere Retry-Regeln

- **Permanente Fehler** (`DeviceNotFoundError`, `CapabilityNotSupportedError`) werden **nie** wiederholt — ein erneuter Versuch würde am selben Grund erneut scheitern.
- **Transiente Fehler** (`TransientDeviceError`, z. B. ein kurzzeitig nicht erreichbares Gerät) werden bis zu 3 Mal versucht, mit kurzer Pause dazwischen. Der `SimulationDeviceAdapter` kann solche Fehler gezielt injizieren (`inject_transient_fault(device_id, times=n)`) — genutzt in den Tests, um Retry-Erfolg und Retry-Erschöpfung ohne echte flakige Hardware zu prüfen.
- Da alle Capability-Commands aus `S1V2-02-002` idempotent sind (ein wiederholtes „setze Helligkeit auf 40 %" ist sicher), ist Retry hier grundsätzlich unbedenklich — anders als bei nicht-idempotenten Aktionen, für die Retry-Regeln separat zu bewerten wären.

## Ausführungshistorie

`AutomationHistory` (In-Memory, begrenzter Ring wie `InMemoryEventBus`) speichert `AutomationRun`: `automation_id`, `triggered_at`, `trigger_reason`, `outcome` (`success`/`failed`/`skipped_disabled`/`skipped_conditions_not_met`), `error_reason`, `attempts`. Bewusst **noch nicht in PostgreSQL persistiert** — dieselbe Scope-Grenze wie bei `DomainDevice` in `S1V2-02-002`: der Kern-Domänenlayer bleibt datenbankfrei testbar; Persistenz der `Automation`/`AutomationRun`-Datensätze folgt über die Service-/Repository-Schicht (`S1V2-02-003`s Muster), sobald eine fachliche Aufgabe dafür ansteht.

## Trigger-Auslösung

- **`on_device_event(event)`** — für Automationen mit `DeviceStateTrigger`, dessen `device_id` im Event-Payload (`payload["deviceId"]`) auftaucht; prüft den *aktuellen* Gerätezustand (nicht das Event-Payload selbst) gegen die Trigger-Bedingung.
- **`check_time(now)`** — feuert `TimeTrigger`-Automationen bei exakter `HH:MM`-Übereinstimmung, **höchstens einmal pro Minute** (Minuten-Schlüssel pro Automation gemerkt) — dieselbe Idempotenz-Eigenschaft wie im bestehenden Node-Scheduler.
- **`check_sun_event(event, now)`** — feuert `SunEventTrigger`-Automationen. Die eigentliche Sonnenauf-/-untergangsberechnung ist bewusst **nicht** Teil dieser Aufgabe (eigenständige, bereits im Altplan vorhandene Berechnung, `mvp/systemone-pi/lib/solar.js`) — der Aufrufer übergibt das Ereignis, die Engine kennt nur „es ist gerade Sonnenaufgang/-untergang".

## Tests (Definition of Done)

`apps/customer-backend/tests/test_automation_engine.py` (9 Tests, reine Domain-Tests ohne HTTP/DB/HA):

- Einfaches Wenn-Dann (`test_simple_if_then`)
- Mehrere Bedingungen und mehrere Aktionen (`test_multiple_conditions_and_actions`, `test_conditions_not_met_skips_actions`)
- Zeittrigger inkl. Idempotenz pro Minute (`test_time_trigger_fires_once_per_matching_minute`)
- Deaktivierte Automation (`test_disabled_automation_is_skipped`)
- Fehlerfall: transienter Fehler mit erfolgreichem Retry, transienter Fehler mit Retry-Erschöpfung, permanenter Fehler ohne Retry (`test_transient_error_is_retried_then_succeeds`, `test_transient_error_exhausts_retries_and_fails`, `test_permanent_error_is_not_retried`)
- Capability-Validierung (`test_validate_rejects_unknown_capability`)

Gesamt `apps/customer-backend`: **68/68 Tests bestanden**.

## Bewusst nicht Teil dieser Aufgabe

- Persistenz von `Automation`/`AutomationRun` in PostgreSQL.
- Ein laufender Hintergrund-Scheduler, der `check_time`/`check_sun_event` tatsächlich periodisch aufruft (reine Auswertungsfunktionen hier, kein Loop/Cronjob).
- Echte Sonnenzeiten-Berechnung (existiert bereits im Node-Piloten, wird bei Bedarf als eigener Baustein übernommen).
- API-Routen für Automationsverwaltung (folgt dem in `S1V2-02-003` etablierten Muster: dünne Router, die `AutomationEngine`/eine künftige Service-Schicht aufrufen).
