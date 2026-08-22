# Service-/Repository-Schicht mit Transaktionen und Berechtigungs-Hooks (Stand 17.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-003 · Service- und Repository-Schicht mit Transaktionen und Berechtigungs-Hooks aufbauen`.
> Quellen: `DEC-119–120`, `DEC-138`. Implementierung: `apps/customer-backend/app/{repositories,uow.py,authorization.py,audit.py,services}`.

## Bausteine

- **Repository-Interfaces** (`app/repositories/protocols.py`) — `RoomRepository`, `DeviceRepository` als `typing.Protocol` (wie schon `DeviceAdapterPort` in `S1V2-02-002`). Rückgabewerte sind eigene, persistenzunabhängige DTOs (`app/repositories/records.py::RoomRecord`/`DeviceRecord`), nicht SQLAlchemy-ORM-Objekte direkt — Services bleiben so von der Persistenzimplementierung entkoppelt.
- **`SqlAlchemyRoomRepository`/`SqlAlchemyDeviceRepository`** (`app/repositories/sqlalchemy_repo.py`) — echte Implementierung gegen `app/db/models.py` aus `S1V2-02-001`.
- **`UnitOfWork`** (`app/uow.py`) — eine Transaktion pro Use Case, kann mehrere Repository-Schreibvorgänge zusammenfassen (S1V2-02-003: „Transaktionen für zusammengehörige Änderungen"). `SqlAlchemyUnitOfWork` bündelt Session + beide Repositories; bei einer Exception im `with`-Block wird automatisch zurückgerollt.
- **Autorisierung an der Use-Case-Grenze** (`app/authorization.py`) — `Actor` (bewusst framework-agnostisch, kein FastAPI-/Session-Bezug — das kommt erst mit `S1V2-02-008`/`-009`), `require_permission(actor, permission)`. Jeder Service ruft das **selbst** auf, nicht nur der API-Router — ein Aufruf direkt aus Testcode ohne API-Schicht ist genauso geschützt.
- **Audit-Hook** (`app/audit.py`) — `AuditRecorder`-Protokoll, `SqlAlchemyAuditRecorder` (schreibt in die `audit_events`-Tabelle aus `S1V2-02-001`) und `InMemoryAuditRecorder` für Tests. Bewusst eine **eigene** Transaktion, getrennt von der `UnitOfWork` der auditierten Aktion — ein fehlgeschlagener Audit-Schreibvorgang darf eine sonst erfolgreiche Zustandsänderung nicht zurückrollen, und ein abgelehnter Zugriff muss trotzdem auditierbar bleiben (aktuell wird bei Autorisierungsfehlern bewusst **nicht** auditiert, siehe „Bekannte Grenzen").
- **Services/Use Cases** (`app/services/`) — `RoomService` (`create_room`, `list_rooms`) und `DeviceRegistrationService` (`register_device`, **idempotent** bzgl. `(integration_id, external_id)` — ein wiederholter Registrierungsversuch, etwa nach einem Netzwerkfehler beim Provisioning, liefert die bestehende Registrierung statt eines Duplikats oder Fehlers zurück; als Muster für spätere Provisioning-/Remote-/Update-Use-Cases gedacht, siehe `S1V2-02-003`: „Idempotente Operationen für Provisioning/Remote/Update").

## Ablauf eines Use Case (Beispiel `RoomService.create_room`)

1. `require_permission(actor, "rooms:manage")` — Autorisierung zuerst, vor jedem Repository-Zugriff.
2. `with self._uow_factory() as uow:` — Transaktion öffnen.
3. `uow.rooms.add(...)`, `uow.commit()` — Schreiben + Commit innerhalb der Transaktion.
4. Audit-Eintrag **nach** erfolgreichem Commit.

## API-Routen bleiben dünn (Definition of Done)

Diese Aufgabe fügt bewusst **keine neuen FastAPI-Routen** hinzu — die bestehenden `/api/v1/devices*`-Routen aus `S1V2-02-002` bleiben unverändert (sie nutzen weiterhin direkt `DeviceService`/`SimulationDeviceAdapter`, nicht diese neue Registrierungs-/Persistenz-Schicht). Die Verdrahtung von `RoomService`/`DeviceRegistrationService` hinter echten API-Routen (inkl. Extraktion eines `Actor` aus der Session) ist Teil der jeweiligen fachlichen Aufgaben (Räume-/Geräteverwaltung, Phase „06 Clients & Integrationen") und der Session-/Rollen-Aufgaben `S1V2-02-008`/`-009` — hier wird nur die Schicht selbst gebaut und isoliert getestet, damit spätere Router-Handler nur noch `service.methode(actor, ...)` aufrufen müssen.

## Tests

- **Unit-Tests mit Fake-Repositories** (`tests/fakes.py`, `tests/test_room_service.py`, `tests/test_device_registration_service.py`) — kein SQLAlchemy, keine Datenbank. Decken ab: erfolgreicher Use Case committet + auditiert; fehlende Berechtigung wird abgelehnt **und** erreicht nie das Repository (`uow.committed is False`, kein Audit-Eintrag); Idempotenz der Geräteregistrierung.
- **Integrationstest gegen echtes PostgreSQL** (`tests/test_services_sqlalchemy.py`) — dieselben Services, diesmal mit `SqlAlchemyUnitOfWork`, beweist, dass die echten Repository-Implementierungen (nicht nur die Fakes) funktionieren.
- Gesamt `apps/customer-backend`: **56/56 Tests bestanden** (Python 3.12, siehe `docs/architecture/data-model.md` für den weiterhin geltenden Python-3.14-Sandbox-Hinweis).

## Bewusst nicht Teil dieser Aufgabe / bekannte Grenzen

- Autorisierungsfehler werden aktuell **nicht** auditiert (nur erfolgreiche Aktionen). Ob ein „Zugriff verweigert"-Ereignis ebenfalls audit-pflichtig ist, ist eine Sicherheitsentscheidung, die sinnvollerweise zusammen mit dem vollständigen Auth-Modell (`S1V2-02-008`/`-009`) und dem manipulationsgeschützten Audit-Kern (`S1V2-02-014`) getroffen wird — hier nicht vorweggenommen.
- `Actor` wird noch manuell konstruiert (kein Extrakt aus einer echten Session/einem echten Rollenmodell) — folgt mit `S1V2-02-008`/`-009`.
- Audit-Schreibvorgang läuft in einer separaten Transaktion von der auditierten Aktion — strikte Selbe-Transaktion-Konsistenz ist `S1V2-02-014`s Aufgabe (Manipulationsschutz/Hash-Chaining).
- Nur zwei Beispiel-Services (Räume, Geräteregistrierung) — weitere Use Cases folgen demselben Muster (Autorisierung zuerst, `UnitOfWork`, Audit danach), keine neue Struktur nötig.
