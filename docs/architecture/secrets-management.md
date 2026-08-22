# Secrets- und Schlüsselmanagement für Kundensysteme (Stand 18.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-013 · Secrets- und Schlüsselmanagement für Kundensysteme aufbauen`.
> Quelle: `DEC-118`. Implementierung: `apps/customer-backend/app/secret_store.py`, `apps/customer-backend/app/diagnostics.py`, `scripts/check-secrets.py`.

## Möglichst nicht speichern, sonst verschlüsselt und getrennt

`SecretStore` (`app/secret_store.py`) ist der einzige Ort im Kundensystem, an dem Integrationszugangsdaten (z. B. ein Home-Assistant-Langzeit-Token) persistiert werden dürfen. Bewusst getrennt von `Integration.config` (allgemeine, nicht-geheime Konfiguration, siehe dessen Docstring in `app/db/models.py`) — ein eigenes Modell `IntegrationSecret` mit ausschließlich `ciphertext` (nie Klartext), verschlüsselt mit Fernet (`cryptography`-Bibliothek, authentifizierte symmetrische Verschlüsselung). Der Schlüssel kommt ausschließlich aus der Umgebungsvariable `SECRETS_ENCRYPTION_KEY` (`app/secret_store.py::load_fernet_from_env`), nie aus einer eingecheckten Datei — dasselbe Muster wie bereits `DATABASE_URL` (`app/db/session.py`).

Zugriff ist restriktiv: `set_secret()`/`revoke_secret()` verlangen `require_permission(actor, "integrations:manage")` (neue Permission, vergeben an `owner`/`administrator` in `app/roles.py`, analog zu `users:manage`). `get_secret()` ist für interne System-Aufrufe (z. B. ein künftiger Integrationsadapter, der sich verbindet) ohne Actor, aber dennoch vollständig auditiert — dasselbe Muster wie `HouseholdPinService.verify_pin()`.

„Getrennt pro Kunde/System": jedes Kundensystem läuft als eigene, vollständig separate Instanz mit eigener Datenbank (local-first, siehe `docs/product-manifest.md`) — Trennung „pro Kunde" ist damit strukturell durch die Deployment-Architektur gegeben, nicht durch zusätzliche Mandantentrennung in dieser Aufgabe. Innerhalb eines Systems ist jedes Secret zusätzlich strikt pro `integration_id` skaliert (`UniqueConstraint(integration_id, key)`) — ein Secret einer Integration ist unter einer anderen `integration_id` nicht sichtbar, auch nicht bei gleichem `key`-Namen (automatisiert getestet).

## Rotation/Widerruf

`set_secret()` überschreibt einen bestehenden Wert für `(integration_id, key)` bedingungslos — das ist zugleich die Rotation, im selben „neu setzen statt wiederherstellen"-Stil wie bereits bei der Haushalts-PIN (`S1V2-02-011`). `revoke_secret()` löscht die Zeile vollständig (kein Soft-Delete, kein Tombstone) — „möglichst nicht speichern" bedeutet, dass nichts verbleibt, sobald ein Secret nicht mehr gebraucht wird.

## Log-/Diagnose-Redaction

Zwei unabhängige Schutzschichten:

1. **Laufende Logs**: bereits aus `S1V2-01-005` vorhanden (`app/observability.py::redact()`, automatisch auf jede Logzeile des `"systemone"`-Loggers angewendet) — unverändert, hier nur wiederverwendet/bestätigt.
2. **Diagnoseexporte** (neu, `app/diagnostics.py::export_household_integrations()`): liest ausschließlich `Integration`-Zeilen (id/type/status/config — bereits als nicht-geheim dokumentiert) und rührt `IntegrationSecret`/`SecretStore` überhaupt nicht an. Es gibt dadurch **keinen Codepfad**, über den ein Secret-Wert — verschlüsselt oder entschlüsselt — in einen Diagnoseexport gelangen könnte. Als zusätzliches Sicherheitsnetz laufen `config`-Werte zusätzlich durch `redact()`, falls dort durch einen Bedienfehler doch einmal ein secret-förmiger String landen sollte (automatisiert getestet: `test_diagnostic_export_redacts_secret_shaped_config_values`).

## Keine Produktionssecrets in Images/Repository

`scripts/check-secrets.py` (neu): durchsucht das gesamte Repository nach credential-förmigen Mustern (AWS-Keys, GitHub-/Slack-/Stripe-Tokens, PEM-Private-Key-Blöcke, JWT-förmige Strings) sowie nach versehentlich eingecheckten `.env`-Dateien. Bewusst **nicht** generisch nach den Wörtern „password"/„secret" — die eigene Testsuite enthält legitim kurze Fixture-Werte wie `hash_password("admin-password")` in etlichen bereits bestehenden Tests; ein Scanner, der das anschlägt, wäre reines Rauschen statt eines echten Gates. Als neuer Job `secret-scan` in `.github/workflows/systemone-core-neubau.yml` verdrahtet.

```bash
python3 scripts/check-secrets.py
```

Aktueller Repository-Stand: **keine Funde**.

## Tests (Definition of Done)

- **Repository-Secret-Scan**: `scripts/check-secrets.py`, oben beschrieben, läuft sauber gegen den aktuellen Stand.
- **Diagnoseexporte enthalten Testsecrets nicht**: `apps/customer-backend/tests/test_diagnostics.py` (4 Tests) — ein über `SecretStore` gesetztes Test-Secret taucht nachweislich in keinem Feld des Exports auf (`json.dumps(export)`-Substring-Check), während die nicht-geheimen Integrationsdaten weiterhin enthalten sind (kein leerer/kaputter Export).
- Zusätzlich `apps/customer-backend/tests/test_secret_store.py` (13 Tests): Roundtrip, Nie-Klartext-in-der-DB (Direktabfrage), Berechtigungsprüfung (`set_secret`/`revoke_secret`), unbekannte Integration, Rotation, Widerruf, pro-Integration-Trennung, vollständiger Audit-Trail, fehlender/vorhandener Verschlüsselungsschlüssel aus der Umgebung.

Gesamt `apps/customer-backend`: **172/172 Tests bestanden** (155 aus `S1V2-01-003`–`S1V2-02-012` + 17 neue Tests aus dieser Aufgabe).

## Architekturentscheidungen

- `SecretStore` nutzt einen eigenen `session_factory`, außerhalb der UnitOfWork-/Repository-Schicht — dieselbe Begründung wie bei `AuditRecorder` (`app/audit.py`): ein sicherheitskritisches, querschnittliches Anliegen bekommt eine eigene, schmale, auditierbare Oberfläche statt über allgemeine Repositories zu laufen.
- Fernet (symmetrische, authentifizierte Verschlüsselung aus der `cryptography`-Bibliothek) statt einer selbstgebauten AES-GCM-Lösung — Standardwerkzeug für genau diesen Anwendungsfall, keine eigene Krypto-Implementierung nötig.
- Verschlüsselungsschlüssel ausschließlich aus der Umgebung, injizierbar über einen `fernet_factory`-Parameter (Tests verwenden einen fest generierten Testschlüssel statt echter Umgebungsvariablen) — konsistent mit dem bestehenden `DATABASE_URL`-Muster.

## Bekannte Grenzen / offene Punkte

- Der neue `secret-scan`-CI-Job ist im bestehenden Workflow `systemone-core-neubau.yml` verdrahtet, dessen Pfad-Trigger auf `apps/**`, `services/**`, `packages/**`, `infrastructure/**` sowie die beiden Check-Skripte beschränkt sind. Ein Secret, das ausschließlich in `docs/**` oder anderswo eingecheckt würde, löst diesen CI-Lauf aktuell **nicht automatisch** aus — nur ein lokaler/manueller Aufruf von `scripts/check-secrets.py` (der das gesamte Repository durchsucht) deckt das ab. Eine Anpassung der Trigger-Pfade auf das gesamte Repository wäre eine eigene CI-Hygiene-Entscheidung, bewusst nicht Teil dieser Aufgabe.
- API-Routen für `set_secret`/`revoke_secret` noch nicht verdrahtet (etabliertes Muster: dünne Router folgen später).
- Kein echter Integrationsadapter existiert bisher, der `get_secret()` tatsächlich aufruft (folgt mit `S1V2-02-017`+) — der Abrufpfad ist fertig und getestet, aber noch unbenutzt.
- Keine Versionshistorie für rotierte Secrets (bewusst wie bei der PIN: „neu setzen statt wiederherstellen", kein Audit-Trail alter Werte über die Audit-Events hinaus, die selbst keine Werte enthalten).
