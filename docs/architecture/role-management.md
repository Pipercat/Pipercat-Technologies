# Kundenrollen und geschützte Systemrollen (Stand 18.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-009 · Kundenrollen und geschützte Systemrollen vollständig umsetzen`.
> Quellen: `DEC-119`, `DEC-120`. Implementierung: `apps/customer-backend/app/roles.py`.

## Rollenkatalog

| Rolle | Kategorie | Berechtigungsumfang |
|---|---|---|
| `owner` | kundenseitig | umfassendste Kundenrechte (Räume, Geräte, Automationen, Nutzer, Notfallmodus, Backup, Update-Freigabe) |
| `administrator` | kundenseitig | wie `owner` ohne `backup:manage`/`updates:approve` |
| `member` | kundenseitig | Räume/Geräte lesen und steuern, Automationen lesen |
| `guest` | kundenseitig | Räume/Geräte nur lesen |
| `display` | kundenseitig | nur Räume lesen (Kiosk-/Wanddisplay) |
| `service` | **geschützt** | kleinste Berechtigungsmenge im gesamten Katalog (least-privilege) |
| `system` | **geschützt** | interne Systemprozesse (Health/Metrics/Selbstheilung) |
| `pipercat_support` | **geschützt** | Pipercat-eigene Fernwartungsidentität, komplett außerhalb des Kundenrollensystems gesteuert (`S1V2-05-*`) |
| `root` | **geschützt** | konzeptionelle Maximal-Rolle für internes Break-Glass-Tooling außerhalb dieses Dienstes — **niemals ein Kundenfeature** |

Jede Berechtigungsmenge ist **endlich und aufgezählt** — auch `root` hält keine Wildcard-Berechtigung (zusätzlich strukturell durch `Actor`s `WildcardPermissionError` aus `S1V2-02-008` abgesichert).

## Schutzmechanismus

`RoleManagementService.assign_role()`:

1. **Autorisierung zuerst:** `require_permission(actor, "users:manage")`.
2. **Geschützte-Rolle-Prüfung als Verteidigung in der Tiefe:** Selbst ein Actor, der `users:manage` legitim besitzt, kann über diesen Weg **niemals** eine Rolle aus `PROTECTED_ROLE_KEYS` zuweisen — geprüft im Code (`role_key in PROTECTED_ROLE_KEYS`), nicht nur dokumentiert. Das deckt sowohl einen kompromittierten/böswilligen Admin-Account als auch eine manipulierte Anfrage ab, die einen unerwarteten Rollen-Schlüssel im Payload trägt.
3. Unbekannte Rollen-Schlüssel werden ebenfalls abgelehnt (`UnknownRoleError`), nicht stillschweigend ignoriert.
4. Jeder Versuch — erfolgreich, geschützt-blockiert oder unbekannt — wird auditiert (`roles.assigned` / `roles.assignment_blocked`).

Selbst-Eskalation (ein Nutzer versucht, sich selbst eine geschützte Rolle zuzuweisen) wird identisch behandelt wie eine Eskalation eines fremden Kontos — `target_user_id == actor.user_id` bewirkt keine Ausnahme.

## Persistenz

`assign_role()` schreibt über die Repository-/`UnitOfWork`-Schicht aus `S1V2-02-003` (`UserRepository.set_role`, neues `RoleRepository.get_id_by_key`) direkt in die `users`-Tabelle aus `S1V2-02-001` — kein Zwischenschritt, der umgangen werden könnte.

## Tests (Definition of Done: „Negativtests versuchen Rolleneskalation über manipulierte API-Aufrufe; alle Wege blockiert und auditierbar")

`apps/customer-backend/tests/test_role_management.py`:

- Erfolgreiche Zuweisung einer kundenseitigen Rolle (Positivfall, persistiert + auditiert).
- Fehlende Berechtigung wird vor jeder weiteren Prüfung abgelehnt.
- **Parametrisiert über alle vier geschützten Rollen** (`system`, `service`, `root`, `pipercat_support`): jede wird blockiert, selbst für einen Actor mit `users:manage`, Ziel-Nutzer bleibt unverändert, Audit-Eintrag vorhanden.
- Selbst-Eskalationsversuch auf `root` blockiert.
- Unbekannter Rollen-Schlüssel abgelehnt, nicht ignoriert.
- `list_assignable_roles()` liefert nachweislich nie eine geschützte Rolle.
- `service`-Rolle ist nachweislich die Rolle mit den wenigsten Berechtigungen im Katalog.
- Keine Rolle hält jemals eine Wildcard-Berechtigung.
- `root` existiert im Katalog, ist aber nachweislich nie in der kundenseitig zuweisbaren Menge.

## Bewusst nicht Teil dieser Aufgabe

- Seed-Migration, die die vier kundenseitigen `roles`-Zeilen (`owner`/`administrator`/`member`/`guest`/`display`) und ihre `role_permissions`-Verknüpfungen tatsächlich in einer frischen Datenbank anlegt — bislang existieren nur die Tabellen (`S1V2-02-001`), nicht die Startdaten. Folgt als eigene, kleine Migrationsaufgabe.
- API-Routen für Rollenverwaltung — folgt dem etablierten Muster dünner Router.
- Feingranulare Verwaltung eigener, vom Kunden benannter Rollen (nur die fünf festen Rollen sind aktuell vorgesehen, keine frei definierbaren Rollen).
