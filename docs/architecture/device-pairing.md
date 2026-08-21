# Sicherer QR-Erstkopplungsprozess (Stand 21.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-028 · Sicheren QR-Erstkopplungsprozess implementieren`.
> Quelle: `DEC-9` und QR-Entscheidungen (Notion, Bereich 06). Implementierung: `apps/customer-backend/app/services/device_pairing.py`.

## Baut direkt auf S1V2-02-027 auf

Diese Aufgabe komponiert ausschließlich bereits bestehende Bausteine — kein neuer kryptografischer Mechanismus:

- **`get_verified_device_identity()`** (`S1V2-02-027`) — offline, signaturgeprüfte Geräteidentität. `claim_device()` vergleicht die vom Aufrufer angegebene `serial_number` **zuerst** damit — „bindet App/Benutzer an echte Geräteidentität".
- **`DeviceSetupSecretService.claim()`** (`S1V2-02-027`) — der einmalige/rotierbare Setup-Secret. Genau diese bereits gebaute Ein-mal-Konsum-Garantie ist die eigentliche Umsetzung von „Erster Owner wird atomar gesetzt", „Replay ... verhindern" und „QR-Foto allein ermöglicht keinen Zugriff" — kein neuer Sperrmechanismus nötig.

## Reihenfolge der Prüfungen ist die eigentliche Sicherheitsentscheidung

```
1. Geräteidentität prüfen (serial_number == echte, signierte Identität?)
   → falsch: WrongDeviceError, Setup-Secret bleibt unangetastet
2. Setup-Secret konsumieren (einmalig, atomar)
   → falsch/bereits verbraucht: InvalidOrConsumedSetupSecretError
3. Erst danach: Household + Owner-User in einer DB-Transaktion anlegen
```

**Schritt 1 vor Schritt 2**: Ein falsches-Gerät-Versuch darf niemals ein echtes, noch gültiges Setup-Secret verbrauchen — sonst könnte ein Angriff auf das falsche Gerät den echten Besitzer aussperren.

**Schritt 2 vor Schritt 3**: Das Setup-Secret ist das, was Nebenläufigkeit tatsächlich verhindert — es gibt noch keinen Haushalts-Datensatz, auf den sich eine Datenbank-Sperre stützen könnte, bevor der Haushalt überhaupt existiert. `claim()` ist eine synchrone, nicht unterbrechende Operation; innerhalb eines Prozesses kann keine zweite Coroutine mitten in ihrer Ausführung dazwischenfunken — nur ein gleichzeitiger Versuch kann je ein noch unverbrauchtes Secret sehen und gewinnen. **Wichtige Grenze**: Das gilt nur innerhalb eines einzelnen Prozesses (das lokale Pi/Mini/Server/Rack-Modell, `docs/product-manifest.md` §2) — ein künftiges Mehrprozess-Deployment bräuchte eine echte Dateisperre in `DeviceSetupSecretService`, um dieselbe Garantie prozessübergreifend zu halten.

## „QR enthält keine langlebigen Admin-Credentials"

Der QR-Code trägt nur `serial_number` + das aktuelle, einmalige Setup-Secret — nie ein Passwort oder Session-Token. Das Admin-Passwort wird frisch von der Person gewählt, die koppelt, und zur Kopplungszeit in die App eingetippt — es steht nirgendwo im QR-Code.

## Kein neuer Fehler-Katalog

`WrongDeviceError` und `InvalidOrConsumedSetupSecretError` sind die einzigen zwei neuen Fehlertypen — genau die zwei im DoD genannten Fälle (falsches Gerät, ungültiges/verbrauchtes Secret — „Replay" und „bereits gekoppelt" sind derselbe Fehler, da beide bedeuten „dieses Secret ist nicht mehr gültig").

## Eine echte, vorher unentdeckte Lücke unterwegs gefunden und behoben

Beim Bau dieser Aufgabe zeigte sich: **nichts hatte je die `roles`/`permissions`/`role_permissions`-Tabellen befüllt**, obwohl `RoleManagementService.assign_role()` (`S1V2-02-009`) bereits `uow.roles.get_id_by_key(role_key)` voraussetzt. Der reale Katalog existierte nur als In-Memory-Dict (`app/roles.py::ROLE_PERMISSIONS`) — auf einer frischen echten Postgres-Instanz wäre `assign_role()` für **jede** Rolle fehlgeschlagen. Das war bisher unentdeckt, weil `tests/test_role_management.py` ausschließlich `FakeRoleRepository` nutzt (nie echtes Postgres).

**Behoben** mit `alembic/versions/0005_seed_role_catalog.py` — sät den Rollenkatalog als eingefrorenen Schnappschuss (nicht dynamisch aus `app.roles` importiert, damit sich das Verhalten dieser Migration nie durch spätere Codeänderungen stillschweigend ändert). Diese Aufgabe brauchte eine funktionierende „owner"-Rolle für den ersten Haushaltsbesitzer — die Behebung war also eine echte, blockierende Voraussetzung, keine beiläufige Erweiterung.

**Migrations-Downgrade-Detail**: Ein naives `DELETE ... WHERE id IN (...)` in der Downgrade-Funktion verletzt `users.role_id`s Fremdschlüssel (`ondelete="RESTRICT"`), sobald irgendein Test bereits einen echten `User` gegen eine gesäte Rolle angelegt hat. Gelöst mit `TRUNCATE TABLE users, role_permissions, roles, permissions RESTART IDENTITY CASCADE` — unbedenklich, da „downgrade to base" ohnehin immer mit vollständig gelöschtem Schema endet (`tests/test_migrations.py`).

## Neue Repository-Bausteine

- `HouseholdRepository` (Protocol + `SqlAlchemyHouseholdRepository` + `FakeHouseholdRepository`) — existierte bisher überhaupt nicht; `households` ist jetzt Teil von `UnitOfWork`.
- `UserRepository.add()` — existierte bisher nicht (nur Lese-/Änderungsmethoden). `tests/fakes.py::FakeUserRepository`s alte `add(user: UserRecord)`-Methode (ein test-only „ganzen Datensatz einfügen"-Helfer) wurde in `seed()` umbenannt, um nicht mit der neuen, echten `add(**kwargs)`-Signatur zu kollidieren — alle sieben betroffenen Testdateien entsprechend angepasst.

## Tests

`apps/customer-backend/tests/test_device_pairing.py` (9 Tests): erfolgreiche Kopplung legt Haushalt+Owner an, Passwort nur als Hash gespeichert, Erfolg wird auditiert (mit `actor=None`), falsches Gerät abgelehnt **und verbraucht das Secret nicht**, falsches Secret abgelehnt, Replay mit demselben Secret abgelehnt, **ein fotografierter/kopierter QR-Code kann ein bereits gekoppeltes Gerät nicht mehr übernehmen** (der zentrale DoD-Beweis), `rotate()` erlaubt einen bewussten Neukopplungszyklus.

Zusätzlich: `alembic/versions/0005_seed_role_catalog.py` gegen echtes PostgreSQL verifiziert (`tests/test_migrations.py`s Upgrade/Downgrade/Upgrade-Rundlauf), drei bestehende Testdateien (`test_audit.py`, `test_models.py`, `test_services_sqlalchemy.py`) angepasst, um die jetzt gesäten Rollen wiederzuverwenden statt Duplikate anzulegen.

Gesamt `apps/customer-backend`: **338/338 bestanden** (329 aus `S1V2-01-003`–`S1V2-02-027` + 9 neue). `python3 scripts/check-import-boundaries.py`: keine Verletzung. `python3 scripts/check-secrets.py`: kein Fund. `docker compose config`: erfolgreich validiert (unverändert).

## Architekturentscheidungen

- Reihenfolge Identität → Secret → DB-Transaktion (siehe oben) — die einzige Reihenfolge, die weder ein legitimes Secret an einen Falsches-Gerät-Versuch verschwendet noch ein Nebenläufigkeits-Fenster offenlässt.
- Rollenkatalog als eingefrorener Schnappschuss in der Migration, nicht dynamisch aus `app.roles` importiert — Migrationen dürfen sich nicht stillschweigend ändern, wenn späterer Anwendungscode sich ändert.
- Kein API-Endpunkt verdrahtet — `apps/customer-backend/app/main.py` hat aktuell **keinerlei** echte Datenbank-Anbindung (kein `uow_factory`, keine Session) für irgendeine Route; das ist ausdrücklich `S1V2-02-033`s Aufgabe (bereits in `S1V2-02-025`s Notion-Notiz als „Session/CSRF/Rollen-Wiring in main.py" benannt). Diesen Endpunkt jetzt isoliert zu verdrahten würde diesem bereits identifizierten, größeren Vorhaben vorgreifen.

## Bekannte Grenzen

- Kein API-Endpunkt (siehe oben) — `DevicePairingService` ist vollständig gebaut und getestet, wartet auf `S1V2-02-033`s Datenbank-/Session-Verdrahtung von `main.py`.
- Mehrprozess-Nebenläufigkeit des Setup-Secrets nicht abgedeckt (siehe oben) — nur innerhalb eines einzelnen Prozesses garantiert atomar.
- Kein automatisches Verknüpfen mit einer Login-Session nach erfolgreicher Kopplung — `claim_device()` legt Haushalt+Owner an und gibt deren IDs zurück; das tatsächliche Einloggen (Token-Ausstellung) ist `AuthenticationService.login()`s bestehende, separate Zuständigkeit (`S1V2-02-008`), hier bewusst nicht dupliziert.
