# Manipulationsgeschützter Audit-Log-Kern (Stand 18.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-014 · Manipulationsgeschützten Audit-Log-Kern implementieren`.
> Quellen: `DEC-115`, `DEC-136–138`, `DEC-183`, `DEC-185–186`. Implementierung: `apps/customer-backend/app/audit.py`.

## Hash-Chain als Manipulationsnachweis

`AuditEvent` (bereits seit `S1V2-02-001` append-only, kein `updated_at`/`deleted_at`) bekommt drei neue Spalten: `sequence_number` (monoton, `UNIQUE`), `previous_hash`, `record_hash`. Jeder Datensatz hasht seine eigenen Felder **plus** den Hash des vorherigen Datensatzes (`app/audit.py::_canonical_payload` + `_hash_record`, SHA-256 über eine deterministische, sortierte JSON-Serialisierung). Der allererste Datensatz verkettet sich mit einer benannten Genesis-Konstante (`GENESIS_HASH`, kein Allnullen-Wert — eindeutig von einem versehentlich leeren Feld unterscheidbar).

Dadurch wird **jede** nachträgliche Änderung erkennbar:
- Ändern eines Feldes → der neu berechnete `record_hash` weicht vom gespeicherten ab.
- Löschen eines Datensatzes → der `previous_hash` des nächsten Datensatzes passt zu keinem noch vorhandenen Datensatz mehr.
- Einfügen/Umsortieren → dieselbe `previous_hash`-Prüfung schlägt fehl.

`SqlAlchemyAuditRecorder.record()` ist die **einzige** Stelle, die `sequence_number`/`previous_hash`/`record_hash` berechnet — kein anderer Codepfad kann eine gültige Kette erzeugen. Der Zugriff auf den letzten Datensatz läuft über `SELECT ... ORDER BY sequence_number DESC LIMIT 1 FOR UPDATE`, damit zwei gleichzeitige Schreibvorgänge nie denselben `sequence_number`/`previous_hash` berechnen (der zweite wartet, statt eine inkonsistente Kette zu erzeugen).

`verify_chain_integrity(session_factory)` liest die gesamte Kette, rekonstruiert jeden Hash aus den gespeicherten Feldern und vergleicht ihn mit dem gespeicherten `record_hash` bzw. dem erwarteten `previous_hash`. Ergebnis: `ChainVerificationResult(intact, checked, broken_at_sequence, reason)`.

**Wichtige Klarstellung**: Kein Anwendungsmechanismus kann eine Änderung durch jemanden mit direktem Datenbankzugriff *verhindern* — das leistet auch keine Signatur ohne externen, unveränderlichen Anker. „Manipulationsgeschützt" bedeutet hier: **jede** Manipulation wird zuverlässig **erkannt**, nicht dass sie unmöglich gemacht wird. Das entspricht exakt der Notion-Formulierung „Integritätsverkettung/Signatur oder gleichwertigem Manipulationsnachweis".

## Zeitzone-Falle (gefunden und behoben)

Erster Testlauf schlug fehl, obwohl nichts manipuliert war: `occurred_at.isoformat()` wurde einmal beim Schreiben (immer UTC, `datetime.now(UTC)`) und einmal beim Verifizieren nach einem Postgres-Roundtrip gehasht — Letzteres kam mit einem anderen Offset zurück (abhängig von der Session-`TimeZone`-Einstellung), obwohl es derselbe Zeitpunkt war. Behoben durch `occurred_at.astimezone(UTC).isoformat()` an beiden Stellen, sodass derselbe Zeitpunkt immer identisch serialisiert wird.

## Einsicht in Auditdaten wird selbst auditiert

`AuditLogService.list_events(actor)` (neu) verlangt `audit:read` (neue Permission, vergeben an `owner`/`administrator`/`root`/`pipercat_support` — Letzteres gemäß `DEC-136`: ein autorisierter Pipercat-Support-Mitarbeiter darf im Rahmen einer freigegebenen Fernwartung Logs einsehen). Jeder Aufruf erzeugt **selbst** einen neuen, verketteten `audit.viewed`-Eintrag über den injizierten `AuditRecorder` — die Einsicht ist damit Teil derselben manipulationsgeschützten Kette, nicht drumherum protokolliert.

## Mindestens auditieren — bereits abgedeckt vs. noch nicht existent

| Kategorie | Status |
|---|---|
| PIN-/Rechteänderungen | ✅ bereits vorhanden (`household_pin.py`, `roles.py`) |
| Adminaktionen (Admin-Bereich-Freischaltung) | ✅ bereits vorhanden (`admin_area.py`) |
| Kritische Geräteaktionen (geschützte Aktionen) | ✅ bereits vorhanden (`protected_action.py`) |
| Automatische Schutzmaßnahmen (Selbstheilung) | ✅ bereits vorhanden (`selfhealing.py`) |
| Notfallmodus (Ein-/Austritt) | ✅ bereits vorhanden (`emergency.py`) |
| Einsicht in Auditdaten | ✅ neu in dieser Aufgabe (`AuditLogService`) |
| Remote-Zugriffe, Logexporte | ⏳ Feature existiert noch nicht (`S1V2-05-*`) — sobald gebaut, muss es `audit.record()` aufrufen |
| Updatefreigaben | ⏳ Feature existiert noch nicht (spätere Update-Aufgabe) |
| Root-Elevation | ⏳ `root`-Rolle ist bisher rein konzeptionell, wird durch keinen Codepfad tatsächlich zugewiesen |

Diese Aufgabe härtet den **Kern** (Speicherung, Manipulationsnachweis, Meta-Audit) — sie fügt keine Audit-Aufrufe in Features ein, die selbst noch nicht existieren. Jede der ⏳-Kategorien bekommt ihre `audit.record()`-Aufrufe automatisch, sobald ihre jeweilige Aufgabe implementiert wird (der bestehende `AuditRecorder`-Port ändert sich nicht).

## Schutzfrist / Löschschutz

„Geschützte Auditdaten vor Schutzfrist nicht löschbar": aktuell existiert **keinerlei** Lösch-/Purge-Methode für `AuditEvent` in Repository, Service oder API — die Anforderung ist damit strukturell erfüllt (nichts kann sie löschen). Die konkrete Aufbewahrungsdauer (wann Löschung nach Ablauf einer Schutzfrist *erlaubt* wird) ist eine separate, spätere Compliance-Entscheidung (`S1V2-05-001 · Log-Speicherklassen und Aufbewahrungsregeln`) — hier bewusst nicht vorweggenommen, um keine Aufbewahrungsfrist zu erfinden, die eigentlich eine rechtliche/geschäftliche Entscheidung ist.

## Tests (Definition of Done)

`apps/customer-backend/tests/test_audit.py` (11 Tests), gegen echtes PostgreSQL 16:

- **Tamper-Test (wörtliche DoD)**: `test_tampering_with_a_historical_record_is_detected` — `SqlAlchemyAuditRecorder` schreibt drei Events, dann wird ein historischer Datensatz per direktem `UPDATE` verändert (am `AuditRecorder` vorbei, wie ein Angreifer mit Datenbankzugriff), `verify_chain_integrity()` erkennt es exakt am richtigen `sequence_number`.
- Zusätzlich: Manipulation von `metadata` erkannt, Manipulation propagiert als Kettenbruch, Löschen eines historischen Datensatzes erkannt, unveränderte Kette bleibt intakt, leere Kette ist trivial intakt, Sequenznummern/Verkettung über mehrere Records korrekt.
- `AuditLogService`: `audit:read` erforderlich, Ergebnisse neueste zuerst, Einsicht erzeugt selbst einen verketteten `audit.viewed`-Eintrag.

`tests/test_models.py` angepasst (zwei direkte `AuditEvent(...)`-Konstruktionen um die drei neuen Pflichtfelder ergänzt).

Gesamt `apps/customer-backend`: **183/183 Tests bestanden**. `python3 scripts/check-import-boundaries.py`: keine Verletzung. `python3 scripts/check-secrets.py`: kein Fund. `docker compose config`: erfolgreich validiert.

## Architekturentscheidungen

- Hash-Chain statt digitaler Signatur: keine Schlüsselverwaltung nötig, gleichwertiger Manipulationsnachweis für den hier verlangten Zweck (Erkennung, nicht Verhinderung), passt zum bereits etablierten „so einfach wie möglich, aber korrekt"-Stil dieses Projekts.
- `AuditRecorder`-Protocol-Signatur unverändert — alle ~10 bestehenden Aufrufer (`household_pin.py`, `admin_area.py`, `protected_action.py`, `selfhealing.py`, `emergency.py`, `roles.py`, `secret_store.py`, u. a.) brauchten keine Änderung, nur `SqlAlchemyAuditRecorder`s interne Implementierung wuchs.
- `InMemoryAuditRecorder` bleibt bewusst ungekettet — die Manipulationsschutz-Garantie betrifft das, was dauerhaft auf Platte landet; eine prozesslokale Liste hat zwischen Prozess-Neustarts nichts, was ein Angreifer manipulieren könnte.
- `.with_for_update()` für die Tail-Abfrage: verhindert eine Race-Condition zwischen zwei gleichzeitigen Schreibern auf `sequence_number`/`previous_hash`.

## Bekannte Grenzen / offene Punkte

- Migration `0003` setzt die drei neuen Spalten als `NOT NULL` ohne Default — das setzt eine leere `audit_events`-Tabelle voraus (überall zutreffend, da es noch keine Produktionsumgebung gibt). Eine Migration mit Backfill für eine bereits befüllte Tabelle ist nicht Teil dieser Aufgabe.
- Konkrete Aufbewahrungsfrist/Löschregeln: siehe oben, bewusst `S1V2-05-001` überlassen.
- API-Route für `AuditLogService.list_events()` noch nicht verdrahtet (etabliertes Muster: dünne Router folgen später).
- Kategorien ohne existierendes Feature (Remote-Zugriffe, Logexporte, Updatefreigaben, echte Root-Elevation) sind bewusst nicht vorgezogen — siehe Tabelle oben.
