# Notfallmodus-State-Machine (Stand 17.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-007 · Notfallmodus-State-Machine für schwere Störungen implementieren`.
> Quellen: `DEC-184–190`. Implementierung: `apps/customer-backend/app/emergency.py`.

## Zustände

`NORMAL → ENTERING_EMERGENCY → EMERGENCY → RECOVERING → {NORMAL | AWAITING_APPROVAL} → NORMAL`, mit einem Rücksprung `RECOVERING`/`AWAITING_APPROVAL → EMERGENCY`, falls sich eine Wiederherstellung als unsicher herausstellt. Erlaubte Übergänge sind als explizite Tabelle (`ALLOWED_TRANSITIONS`) hinterlegt — jeder nicht gelistete Übergang wirft `EmergencyTransitionError`, es gibt keine impliziten/stillen Zustandswechsel.

## Auslösung: manuell und automatisch

- **`enter_manually(actor, reason_code)`** — verlangt `emergency:manage` (Autorisierung an der Grenze, Muster aus `S1V2-02-003`). Jeder `EmergencyReasonCode` ist manuell auslösbar.
- **`enter_automatically(reason_code)`** — nur für eine **fest definierte** Teilmenge (`AUTOMATIC_ENTRY_REASONS`: Sicherheitsvorfall erkannt, Storage-Korruption erkannt, Selbstheilung erschöpft/`S1V2-02-006`). Ein nicht gelisteter Grund wirft sofort `ValueError` — „automatisch nur bei eindeutig definierten Gefahrzuständen" ist damit im Code erzwungen, nicht nur dokumentiert.

## Eintrittsaktionen: kontrolliert stoppen, einschränken, schützen

Beim Übergang `ENTERING_EMERGENCY → EMERGENCY` werden alle registrierten Eintrittsaktionen ausgeführt (z. B. `stop_non_essential_services`, `restrict_access`, `protect_backups` — konkrete Implementierungen sind spätere, fachliche Aufgaben; hier nur die Ausführungs-/Fehlerlogik). **Fail-safe:** Scheitert eine einzelne Aktion, wird das **nicht** zum Abbruch — der Zustand erreicht trotzdem zuverlässig `EMERGENCY` (im Zweifel lieber vollständig im Notfallmodus als in einem unklaren Zwischenzustand hängen). Jedes Aktionsergebnis (Erfolg/Fehlschlag) landet im Audit-Eintrag `emergency.entered`.

## Rückkehr: automatisch nur eindeutig sicher, sonst Freigabe

`attempt_automatic_recovery(safety_check)` — `safety_check` ist ein injizierter Prädikat-Callback (die eigentliche „ist es sicher"-Logik ist eine spätere, fachliche Aufgabe, hier nur die Entscheidungsstruktur):

- `True` → automatischer Übergang zu `NORMAL`.
- `False` → Übergang zu `AWAITING_APPROVAL`; nur `approve_recovery(actor)` mit `emergency:manage`-Berechtigung führt zurück zu `NORMAL`.

## Neustart während Emergency (Definition of Done)

`EmergencyStateSnapshot` (Zustand, Grund, Eintrittszeitpunkt) ist die serialisierbare Grundlage. `EmergencyStateMachine.from_snapshot(snapshot, entry_actions, audit)` rekonstruiert eine Maschine **ausschließlich aus dem Snapshot** — im Test `test_restart_during_emergency_resumes_in_emergency_not_normal` wird eine neue Maschineninstanz (neuer `AuditRecorder`, wie ein frischer Prozess) aus dem Snapshot einer im `EMERGENCY`-Zustand befindlichen Maschine gebaut und bestätigt, dass sie **im `EMERGENCY`-Zustand verbleibt**, nicht auf `NORMAL` zurückfällt. Der Wiederaufnahme-Vorgang selbst wird auditiert (`emergency.resumed_after_restart`).

## Alles auditieren

Jeder Zustandsübergang erzeugt einen `AuditRecorder`-Eintrag (`S1V2-02-003`): `emergency.entering`, `emergency.entered`, `emergency.recovery_started`, `emergency.recovered_automatically`, `emergency.awaiting_approval`, `emergency.recovery_approved`, `emergency.recovery_aborted`, `emergency.resumed_after_restart`. Ein vollständiger Lebenszyklus ist damit lückenlos nachvollziehbar (`test_full_lifecycle_is_fully_audited`).

## Tests (Definition of Done)

`apps/customer-backend/tests/test_emergency_state_machine.py` (10 Tests): manueller Eintritt inkl. Eintrittsaktionen, fehlende Berechtigung, automatischer Eintritt nur für definierte Gründe, fehlschlagende Eintrittsaktion blockiert `EMERGENCY` nicht, automatische Rückkehr bei eindeutiger Sicherheit, Freigabepflicht bei Unsicherheit (inkl. verweigerter Freigabe ohne Berechtigung), Abbruch der Wiederherstellung zurück zu `EMERGENCY`, ungültiger Übergang wird abgelehnt, **Neustart-während-Emergency-Szenario**, vollständige Audit-Kette. Gesamt `apps/customer-backend`: **87/87 Tests bestanden**.

## Bewusst nicht Teil dieser Aufgabe

- Konkrete Eintrittsaktionen (welche Dienste tatsächlich gestoppt werden) und die konkrete „ist Rückkehr sicher"-Prüfung — beides fachliche Folgeaufgaben, hier nur als injizierbare Callbacks modelliert.
- Persistenz des Snapshots (wo/wie er zwischen Prozessneustarts tatsächlich gespeichert wird) — die Aufgabe verlangt, dass die State Machine bei einem gegebenen Snapshot sicher wiederaufsetzt, nicht die Speicherung selbst.
- Verknüpfung mit `SelfHealingService` (`S1V2-02-006`) — `CRITICAL_SELF_HEAL_EXHAUSTED` existiert bereits als automatischer Grund, die tatsächliche Verdrahtung „X aufeinanderfolgende Selbstheilungsfehlschläge lösen automatischen Notfallmodus aus" ist eine spätere Integrationsaufgabe.
