# PostgreSQL-Datenmodell und Migrationsstrategie (Stand 17.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-001 · PostgreSQL-Datenmodell und Migrationstrategie für SystemONE-Kern erstellen`.
> Quellen: `DEC-4`, `DEC-9`, `DEC-120–139`. Implementierung: `apps/customer-backend/app/db/`, Migrationen: `apps/customer-backend/alembic/`.

## Werkzeug: Alembic + SQLAlchemy 2.0

Standardwerkzeug für SQLAlchemy-Migrationen, keine ungewöhnliche/neue Tooling-Entscheidung. `app/db/models.py` enthält die deklarativen Modelle (SQLAlchemy-2.0-`Mapped[...]`-Syntax), `alembic/versions/0001_initial_schema.py` ist die erste, per `alembic revision --autogenerate` erzeugte Migration.

## Schema-Grundsätze (aus der Notion-Vorgabe)

- **Stabile IDs:** jede Tabelle hat eine UUID-Primärspalte (`UUIDPrimaryKeyMixin`) statt fortlaufender Integer-IDs — verrät keine Zeilenanzahl/Erstellreihenfolge nach außen.
- **Zeitstempel:** `created_at`/`updated_at` (`TimestampMixin`) auf allen fachlichen Tabellen, serverseitig gesetzt.
- **Soft-Delete nur wo fachlich nötig** (`SoftDeleteMixin`, `deleted_at`): angewendet auf `Room`, `User`, `ClientDevice`, `Integration`, `Device`, `Automation` — **nicht** auf reine Lookup-Tabellen (`Role`, `Permission`, `Capability`) oder auf kurzlebige/Audit-Datensätze (`RemoteApproval`, `AuditEvent`).
- **Audit-Events getrennt von veränderbaren Fachdatensätzen:** `AuditEvent` ist eine eigene, **append-only** Tabelle ohne `updated_at`/`deleted_at`. Fremdschlüssel auf `household_id`/`actor_user_id` sind `ON DELETE SET NULL`, damit ein gelöschter Haushalt/Nutzer den historischen Audit-Eintrag nie mitreißt — nur die Referenz wird `NULL`, die Zeile bleibt.
- **Passwörter/PINs nie Klartext:** `User` hat ausschließlich `password_hash`/`pin_hash` (Text-Spalten). Es gibt keine `password`/`pin`-Spalte im Schema (automatisiert getestet, siehe unten). Das eigentliche Hashing-Verfahren ist `S1V2-02-008`, hier wird nur die Spaltenform festgelegt.

## Entitäten (mindestens laut Notion-Vorgabe, alle umgesetzt)

`Household`, `Room`, `Role`, `Permission`, `RolePermission` (Zuordnungstabelle), `User`, `ClientDevice`, `Integration`, `Device`, `Capability`, `Automation`, `NotificationPreference`, `RemoteApproval`, `AuditEvent`. Details je Tabelle direkt in `app/db/models.py` als Docstrings/Kommentare, nicht hier dupliziert.

- `Household.product_class` ist ein einfacher, per `CHECK`-Constraint validierter String (`pi`/`mini`/`server`/`rack` — dieselben Werte wie `app.product_class.ProductClass` aus `S1V2-01-003`), bewusst **kein natives Postgres-`ENUM`** — neue Werte sind so eine einfache `CHECK`-Migration statt einer `ALTER TYPE`-Operation.
- `Device.external_id` + `Device.integration_id` haben eine `UNIQUE`-Constraint (ein Home-Assistant-Entity kann pro Integration nur einmal existieren).
- `Integration.config`/`Automation.trigger|conditions|actions`/`AuditEvent.event_metadata` sind `JSONB` (Postgres) — **niemals Secrets**: Zugangsdaten gehören ins Secret-/Schlüsselmanagement aus `S1V2-02-013`, nicht in diese Spalten.

## Migrationsstrategie

- `alembic/env.py` liest `DATABASE_URL` ausschließlich aus der Umgebung (`app/db/session.py::database_url()`), nie aus einer eingecheckten Datei mit echten Zugangsdaten.
- Jede Schemaänderung ist eine neue, im Repository versionierte Alembic-Revision — keine manuellen `ALTER TABLE`-Schritte gegen eine laufende Datenbank.
- **Reproduzierbarkeit verifiziert** (siehe „Tests" unten): eine leere Datenbank migriert deterministisch auf den aktuellen Stand; `downgrade base` entfernt alles wieder vollständig; ein erneutes `upgrade head` landet exakt beim selben Tabellenstand.

## Tests (Definition of Done: „Leere DB migriert reproduzierbar auf aktuellen Stand; Migrationstest vorhanden")

`apps/customer-backend/tests/test_migrations.py` (3 Tests) + `tests/test_models.py` (7 Tests), gegen eine **echte lokale PostgreSQL-16-Instanz** verifiziert (nicht simuliert/gemockt):

- Leere DB → `alembic upgrade head` → alle 14 erwarteten Tabellen vorhanden.
- `upgrade head` → `downgrade base` → `upgrade head` erneut → identischer Tabellenstand (Reproduzierbarkeit).
- `downgrade base` entfernt jede Fachtabelle vollständig.
- Schema-Tests: keine Klartext-Passwort-/PIN-Spalte; ungültige `product_class`/`outcome`/`status`-Werte werden von `CHECK`-Constraints abgelehnt; Household-Löschung kaskadiert korrekt zu Room/Integration/Device/Capability; doppelte `(integration_id, external_id)` wird abgelehnt; `AuditEvent` überlebt die Löschung des referenzierten Haushalts mit `household_id = NULL`.

Diese Tests benötigen `DATABASE_URL` (übersprungen mit klarer Meldung, wenn nicht gesetzt — `tests/db_conftest.py::requires_database`). CI (`.github/workflows/systemone-core-neubau.yml`, Job `customer-backend`) startet dafür einen `postgres:16-alpine`-Service-Container.

### Betriebshinweis: Sandbox-spezifischer Hänger unter Python 3.14

In der KI-Sandbox, in der diese Aufgabe umgesetzt wurde, ist `pyenv`-Standard-Python `3.14.2`. Unter dieser Version **hängt `pytest`s Testsammlung** (schon `--collect-only`, nicht erst die Testausführung) beim Importieren von `tests/db_conftest.py` bzw. `tests/test_migrations.py` reproduzierbar auf — nicht bei direkter Skriptausführung derselben Imports außerhalb von pytest, nur unter pytests Import-/Collection-Mechanismus. Ein `sample`-Stacktrace zeigte den Prozess aktiv, aber dauerhaft in `PyImport_ImportModuleLevelObject`, ein klassisches Import-Lock-Deadlock-Muster.

**Verifiziert als python-3.14-spezifisch:** Mit lokal zusätzlich installiertem Python **3.12.11** (`pyenv install 3.12.11`, separates `.venv312`) lief exakt dieselbe Testsuite reproduzierbar in unter 1 Sekunde durch (37/37 bestanden). Die CI (`python-version: '3.12'`) ist davon nicht betroffen. **Empfehlung für lokale Entwicklung:** Python 3.12 verwenden, nicht die Sandbox-Default-3.14, bis diese Inkompatibilität (vermutlich `psycopg[binary]`-C-Extension mit sehr neuem CPython) anderweitig geklärt ist. Nicht tiefer diagnostiziert (kein Repository-Fehler, sondern eine lokale Toolchain-Kombination) — bei Bedarf für spätere KIs: `docs/architecture/repo-structure.md` und dieser Abschnitt sind der Startpunkt.

Zwei weitere während der Verifikation gefundene und behobene echte Fehler (kein Sandbox-Artefakt):
- `alembic/env.py`s `fileConfig()` deaktivierte standardmäßig **alle** nicht in `alembic.ini` gelisteten Logger — darunter `app/observability.py`s `"systemone"`-Logger, sobald Alembic im selben Prozess wie die App lief. Behoben mit `disable_existing_loggers=False`.
- Tests, die einen DB-seitigen Cascade/`SET NULL`-Effekt nach `session.delete()` prüfen, müssen die SQLAlchemy-Identity-Map vorher leeren (`session.expunge_all()`), sonst liefert `session.get()` veraltete In-Memory-Objekte statt den echten (aktualisierten oder fehlenden) DB-Zustand.

## Bewusst nicht Teil dieser Aufgabe

- Domain-/Service-/Repository-Schicht mit Geschäftslogik (`S1V2-02-002`, `S1V2-02-003`).
- Echtes Passwort-/PIN-Hashing (`S1V2-02-008`).
- Secret-/Schlüsselmanagement für `Integration.config` (`S1V2-02-013`).
- Manipulationsschutz (Hash-Chaining) für `AuditEvent` (`S1V2-02-014`) — diese Aufgabe legt nur die Speicherform fest.
