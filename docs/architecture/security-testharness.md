# Security-Testharness und verbindliche Negativtests (Stand 18.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-015 · Security-Testharness und verbindliche Negativtests etablieren`.
> Quellen: `DEC-119–139`. Betrifft: `apps/customer-backend/app/authorization.py` und alle Services, die eine Actor-Berechtigung prüfen.

## Gefundene Lücke: Datenisolation zwischen Haushalten

Beim Aufbau des Testumfangs ("Datenisolation", "manipulierte IDs") fiel auf: `Actor` (`app/authorization.py`) hatte bis dahin **kein** `household_id`-Feld. Jeder Service, der einen aufrufer-übergebenen `household_id`-Parameter entgegennahm (`RoomService`, `DeviceRegistrationService`) oder eine `target_user_id`/`integration_id` auflöste (`RoleManagementService`, `HouseholdPinService`, `SecretStore`, `ProtectedActionGuard`), vertraute dieser Angabe bedingungslos. Ein Actor mit `users:manage` in Haushalt A hätte technisch einen beliebigen `target_user_id` in Haushalt B übergeben können — die RBAC-Prüfung (`require_permission`) prüft nur *welche Art* Aktion erlaubt ist, nie *wessen* Ressource.

Gemäß AGENTS.md-Arbeitsweise ("Jede später gefundene Lücke erhält zuerst Regressionstest") wurde dies nicht nur dokumentiert, sondern direkt behoben:

- `Actor` bekommt ein Pflichtfeld `household_id: str` (`app/authorization.py`).
- `require_same_household(actor, resource_household_id)` — neue Prüfung, wirft `CrossHouseholdAccessError`.
- `StoredSession`/`SessionStore.create()` tragen jetzt ebenfalls `household_id`; `AuthenticationService` befüllt es beim Login aus dem echten `User.household_id`.
- Verdrahtet in: `RoomService` (create_room/list_rooms), `DeviceRegistrationService` (register_device), `RoleManagementService.assign_role` (löst `target_user_id`s Haushalt auf), `HouseholdPinService` (enable_pin/disable_pin/reset_lockout), `SecretStore` (set_secret/revoke_secret, prüft `Integration.household_id`), `ProtectedActionGuard` (authorize_action/allow_biometric/disallow_biometric).

`AuditLogService.list_events()` bleibt bewusst außen vor — `AuditEvent.household_id` wird aktuell an keiner Aufrufstelle befüllt (bereits als Grenze in `docs/architecture/audit-log.md` dokumentiert); eine sinnvolle Haushalts-Filterung dort setzt das voraus und ist nicht Teil dieser Aufgabe.

## Security-Testmarker

Neuer Pytest-Marker `security` (`pyproject.toml`), gesetzt auf jede Testdatei, die eine der Testumfang-Kategorien abdeckt:

| Datei | Kategorie(n) |
|---|---|
| `test_auth.py` | Authentifizierung, Rate Limits, CSRF, Autorisierung |
| `test_role_management.py` | Autorisierung, Rolleneskalation |
| `test_household_pin.py` | Haushalts-PIN |
| `test_admin_area.py` | Autorisierung (Admin-Bereich) |
| `test_protected_action.py` | Haushalts-PIN pro Aktion, Biometrie |
| `test_secret_store.py` | Secret-Leaks |
| `test_diagnostics.py` | Secret-Leaks (Diagnoseexporte) |
| `test_audit.py` | Audit-Manipulation |
| `test_data_isolation.py` | Datenisolation, manipulierte IDs (neu) |
| `test_models.py::test_no_plaintext_password_or_pin_columns_exist` | Secret-Leaks (einzelne Funktion markiert) |

```bash
pytest -m security -q
```

Lokal: **106 von 193** Tests sind sicherheitsrelevant und laufen isoliert grün.

## CI-Sicherheitsschritt (Definition of Done)

Neuer Job `security-tests` in `.github/workflows/systemone-core-neubau.yml`, mit eigenem `postgres:16-alpine`-Service (mehrere sicherheitsrelevante Tests brauchen eine echte Datenbank) und `pytest -m security -q` als eigenem, unabhängig fehlschlagbarem Schritt — getrennt vom allgemeinen `customer-backend`-Job, damit eine Sicherheitsregression als eigener roter Check sichtbar wird, nicht in einem großen allgemeinen Testlauf untergeht.

## Testumfang: Positiv-/Negativtest-Abdeckung

| Kategorie | Positiv | Negativ |
|---|---|---|
| Authentifizierung | `test_login_with_correct_password_succeeds` | `test_login_with_wrong_password_fails`, `test_login_with_unknown_user_fails_with_the_same_error_type` |
| Autorisierung | jede `require_permission`-erfolgreiche Aktion | `AuthorizationError`-Tests in praktisch jeder Service-Testdatei |
| Rolleneskalation | `test_administrator_can_assign_a_customer_role` | `test_every_protected_role_is_blocked_even_for_an_authorized_actor`, `test_self_escalation_to_a_protected_role_is_blocked` |
| Haushalts-PIN | `test_correct_pin_verifies_after_admin_enables_it` | `test_wrong_pin_is_rejected`, `test_lockout_kicks_in_after_five_failures` |
| Rate Limits | `test_successful_login_resets_the_rate_limit` | `test_rate_limit_blocks_after_too_many_failed_attempts` |
| CSRF | `test_csrf_validation_accepts_the_matching_token` | `test_csrf_validation_rejects_missing_or_mismatched_token` |
| Manipulierte IDs | reguläre ID-basierte Aufrufe überall | `IntegrationNotFoundError`/`UnknownRoleError`/`PinNotEnabledError`/`SecretNotFoundError` + alle neuen `test_data_isolation.py`-Tests |
| Datenisolation | `test_secret_operations_are_scoped_per_integration` | **neu**: `test_data_isolation.py` (8 Tests) + zwei neue Cross-Household-Tests in `test_secret_store.py` |
| Audit-Manipulation | `test_verify_chain_integrity_passes_for_untampered_records` | `test_tampering_with_a_historical_record_is_detected` (S1V2-02-014) |
| Secret-Leaks | `test_set_and_get_secret_roundtrips` | `test_secret_is_never_stored_in_plaintext`, `test_diagnostic_export_does_not_contain_the_secret_value` + `scripts/check-secrets.py` |

Jede Zeile hat mindestens einen automatisierten Positiv- und einen Negativtest — die Definition of Done ist damit für alle bisherigen P0-Sicherheitsanforderungen (S1V2-02-008 bis S1V2-02-014) erfüllt.

## Tests

- `apps/customer-backend/tests/test_data_isolation.py` (neu, 8 Tests): Cross-Household-Zugriff auf Räume, Geräte, Rollenzuweisung, PIN-Verwaltung und geschützte Aktionen wird konsequent abgelehnt.
- `apps/customer-backend/tests/test_secret_store.py`: 2 neue Tests (`test_set_secret_on_another_households_integration_is_rejected`, `test_revoke_secret_on_another_households_integration_is_rejected`).
- Alle bestehenden Tests, die `Actor`/`make_actor`/`SessionStore.create` direkt verwenden, an das neue Pflichtfeld `household_id` angepasst (siehe Geänderte Dateien) — `tests/fakes.py::make_actor()` bekommt einen Default (`household_id="hh-1"`, passend zum bereits durchgängig verwendeten Fixture-Muster), sodass die überwältigende Mehrheit unverändert grün blieb.

Gesamt `apps/customer-backend`: **193/193 Tests bestanden** (183 aus `S1V2-01-003`–`S1V2-02-014` + 8 neue Datenisolations-Tests + 2 neue Secret-Store-Cross-Household-Tests). `python3 scripts/check-import-boundaries.py`: keine Verletzung. `python3 scripts/check-secrets.py`: kein Fund. `docker compose config`: erfolgreich validiert.

## Architekturentscheidungen

- `require_same_household()` ist bewusst eine eigenständige Prüfung, nie in `require_permission()` verschmolzen — RBAC ("welche Art Aktion") und Ressourcen-Eigentümerschaft ("wessen Ressource") sind unabhängige Fragen; ein Service kann durchaus einen wollen, den anderen nicht (z. B. `verify_pin()` bleibt actor-los, da es keine eigene Identität zum Vergleichen gibt).
- `household_id` als Pflichtfeld auf `Actor` (kein Default) — erzwingt, dass jeder Konstruktionsort bewusst gesetzt wird, statt eines stillschweigenden, potenziell falschen Default-Werts.
- Kein neues Multi-Tenancy-Konzept eingeführt — die Prüfung ist Verteidigung in der Tiefe für ein Szenario, das in der local-first-Architektur (ein Kundensystem = eine Instanz) praktisch nicht auftreten sollte, aber vom Schema technisch nicht ausgeschlossen ist und explizit im Testumfang gefordert wurde.

## Bekannte Grenzen / offene Punkte

- `AuditLogService.list_events()` filtert nicht nach Haushalt — abhängig von einer noch nicht existierenden Befüllung von `AuditEvent.household_id` (siehe `docs/architecture/audit-log.md`, „Bekannte Grenzen").
- CSRF-/Rate-Limit-Tests laufen auf Service-Ebene, nicht über echte HTTP-Routen — es gibt noch keine API-Routen für Login/Sessions (etabliertes „dünne Router folgen später"-Muster).
- Der `security`-Marker ist manuell auf Testdateien gesetzt, nicht automatisch aus Notion-Kategorien abgeleitet — künftige sicherheitsrelevante Testdateien müssen ihn selbst setzen.
