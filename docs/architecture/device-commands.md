# Gerätebefehle sicher über HA ausführen (Stand 18.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-019 · Gerätebefehle sicher über Home Assistant ausführen`.
> Quellen: `DEC-6`, `DEC-9`, `DEC-12`. Implementierung: `apps/customer-backend/app/services/device_commands.py`, `apps/customer-backend/app/services/ha_device_adapter.py`, `apps/customer-backend/app/domain/service.py`, `apps/customer-backend/app/domain/device.py`.

## Drei Schichten, drei unabhängige Prüfungen

Ein Gerätebefehl durchläuft, bevor er HA erreicht:

1. **`DeviceCommandService.send_command()`** (neu, `app/services/device_commands.py`) — `require_permission(actor, "devices:control")`. Ohne diese Berechtigung bricht der Aufruf ab, bevor irgendetwas anderes passiert (kein Audit-Eintrag für einen von vornherein verweigerten Versuch — es gibt nichts zu protokollieren, was tatsächlich versucht wurde).
2. **`ProtectedActionGuard.authorize_action()`** (aus `S1V2-02-012`, wiederverwendet) — nur für sensible Capability-Typen (`lock`, `camera_stream`): eine frische PIN- oder Biometrie-Prüfung für genau diesen Befehl, nichts wird über Aufrufe hinweg zwischengespeichert — exakt dieselbe „keine Freischaltsession"-Garantie wie bei jeder anderen geschützten Aktion.
3. **`DeviceService.send_command()`** (`app/domain/service.py`, S1V2-02-002, hier um eine explizite Prüfung ergänzt) — lädt das Gerät neu und prüft `command.type in device.capabilities`, bevor der Adapter überhaupt aufgerufen wird. `CapabilityNotSupportedError`/`DeviceNotFoundError` sind damit verlässliche Domänen-Verträge, unabhängig davon, wie gründlich der jeweilige Adapter selbst prüft.

Keine dieser drei Prüfungen vertraut darauf, dass eine der anderen bereits gelaufen ist — das ist bewusst redundant, nicht nur einmal zentral geprüft.

`SENSITIVE_CAPABILITY_TYPES = {"lock", "camera_stream"}` — genau die beiden Typen, die die Notion-Aufgabe explizit nennt („Locks/Kameras … durch Haushalts-PIN-Policy schützen"). `climate`/`on_off`/`brightness`/`position` bleiben ohne zusätzliche Freigabe kommandierbar (reine Komfortfunktionen, keine physische Sicherheitsgrenze).

## Fehlerübersetzung an der Grenze: `TranslatingHomeAssistantAdapter`

`services/home-assistant-adapter` hat keine internen Abhängigkeiten (siehe `docs/architecture/repo-structure.md`s Import-Grenzen-Tabelle) und kann daher `app.domain.errors`/`app.domain.capabilities` nicht importieren — seine `errors.py`/`mapping.py` definieren stattdessen eigenständige, strukturell ähnliche Fehlertypen und rohe Dicts. `apps/customer-backend` ist die einzige Stelle, die `services/home-assistant-adapter` direkt importieren darf — also auch die einzige Stelle, die diese Übersetzung leisten kann.

`app/services/ha_device_adapter.py::TranslatingHomeAssistantAdapter` ist genau dieser Übersetzungspunkt:

| `home_assistant_adapter.errors.*` | → | `app.domain.errors.*` |
|---|---|---|
| `HomeAssistantConnectionError` | → | `TransientDeviceError` |
| `HomeAssistantAuthError` | → | `TransientDeviceError` |
| `TransientDeviceError` | → | `TransientDeviceError` |
| `DeviceNotFoundError` | → | `DeviceNotFoundError` |
| `CapabilityNotSupportedError` | → | `CapabilityNotSupportedError` |

Verbindungs-, Auth- und Timeout-Fehler landen alle auf demselben `TransientDeviceError` — aus Sicht des Aufrufers bedeuten sie dasselbe: „die Anfrage ist nicht durchgekommen, ein späterer Versuch könnte funktionieren" (so bereits in `app/domain/errors.py` definiert).

Rohe Dicts von `HomeAssistantAdapter.list_devices()`/`apply_command()` werden über `pydantic.TypeAdapter` in echte `DomainDevice`/`CapabilityState`-Modelle gezwungen. Oberhalb dieses Moduls — `DeviceService`, `DeviceCommandService`, künftige API-Routen — sieht nie irgendjemand einen `home_assistant_adapter`-spezifischen Typ.

`DomainDevice` bekommt dabei zusätzlich das `compatibility`-Feld aus `S1V2-02-018` explizit deklariert (statt es Pydantics `extra="ignore"`-Standardverhalten stillschweigend verwerfen zu lassen) — sonst wäre dieses Feld beim Durchreichen durch `TypeAdapter(DomainDevice)` verloren gegangen.

## „Manipulierte Service-/Entityangaben können keine beliebigen HA-Services auslösen"

Drei voneinander unabhängige Gründe, warum das strukturell nicht möglich ist:

1. **Geschlossene Eingabe**: `TranslatingHomeAssistantAdapter.apply_command()` nimmt ausschließlich ein bereits validiertes `CapabilityCommand` entgegen — eine diskriminierte Pydantic-Union mit fester Typmenge. Ein erfundener `type`-Wert wird von Pydantic abgelehnt, bevor überhaupt Domänenlogik läuft (`test_apply_command_cannot_bypass_command_type_validation`).
2. **Feste Service-Whitelist**: `home_assistant_adapter.mapping.command_to_service_call()` (aus `S1V2-02-016`/`-018`) ist eine feste if/elif-Kette aus (Capability-Typ, HA-Domain) → (Service-Domain, Service-Name) ohne Fallback-Zweig — jede nicht gelistete Kombination wirft `CapabilityNotSupportedError`, direkt gegen die eigene Whitelist getestet in `services/home-assistant-adapter/tests/test_mapping.py` (`test_command_to_service_call_rejects_unsupported_combination`, `test_command_to_service_call_rejects_camera_stream_commands`).
3. **Kein client-kontrollierter `entity_id`**: `HomeAssistantAdapter.apply_command()` (S1V2-02-016) löst die HA-`entity_id` ausschließlich über die eigene, aus `list_devices()` befüllte `_entity_id_by_device_id`-Zuordnung auf — eine unbekannte oder manipulierte `device_id` ergibt `DeviceNotFoundError`, nie eine geratene oder beliebige Entity.

`apps/customer-backend/tests/test_ha_device_adapter.py` verifiziert, dass diese drei Garantien den vollen Übersetzungsweg unbeschädigt durchlaufen (u. a. `test_apply_command_only_forwards_the_validated_commands_own_fields`, `test_apply_command_rejects_unsupported_capability_even_when_ha_reports_success_shaped_error`, `test_apply_command_device_id_not_in_ha_registry_is_reported_as_not_found`).

## Tests (Definition of Done)

- **Capability-Hardening / Rechteprüfung / PIN-Schutz** (`apps/customer-backend/tests/test_device_commands.py`, 8 Tests): nicht-sensible Befehle ohne Credential, Lock-Befehl ohne Credential abgelehnt, Lock mit korrekter/falscher PIN, zwei aufeinanderfolgende Lock-Befehle benötigen je eine frische PIN, fehlende `devices:control`-Berechtigung, Audit-Eintrag bei Erfolg/Fehlschlag.
- **Fehlerübersetzung + Manipulationsresistenz** (`apps/customer-backend/tests/test_ha_device_adapter.py`, 12 Tests): alle fünf Fehlerübersetzungen (mock-basiert, kein echtes HA nötig), Dict→Domänenmodell-Koerzierung für Geräte und Zustände, die drei Whitelist-Garantien oben.
- Ein echter Docker-HA-Integrationstest für diese Schicht ist nicht Teil dieser Aufgabe: `TranslatingHomeAssistantAdapter` selbst enthält keine HA-Protokolllogik (die liegt vollständig in `HomeAssistantClient`/`HomeAssistantAdapter`, bereits durch `S1V2-02-016`s optionalen Docker-HA-Integrationstest abgedeckt — hier unverändert, daher nicht erneut ausgeführt) — diese Aufgabe fügt ausschließlich die Übersetzungs- und Sicherheitsschicht *davor* hinzu, mit einem Test-Double statt eines echten Adapters getestet.

Gesamt `apps/customer-backend`: **235/235 bestanden** (215 aus `S1V2-01-003`–`S1V2-02-018` + 20 neue). `services/home-assistant-adapter`: **41/41 bestanden, 6 übersprungen** (Docker-HA-Integrationstests, unverändert seit `S1V2-02-016`). `python3 scripts/check-import-boundaries.py`: keine Verletzung. `python3 scripts/check-secrets.py`: kein Fund. `docker compose config`: erfolgreich validiert.

## Architekturentscheidungen

- Sicherheitslogik (Permission, PIN) bewusst **nicht** in `DeviceService` (Domänenschicht, `S1V2-02-002`s Design hat dort explizit kein Actor-/Sicherheitskonzept), sondern in einer neuen Use-Case-Schicht `DeviceCommandService` (`app/services/`) — spiegelt, wie `RoomService`/`DeviceRegistrationService` bereits Repository-Zugriff mit `require_permission` umhüllen, statt Autorisierung in die Persistenzschicht zu verlegen.
- `TranslatingHomeAssistantAdapter` als einzige Stelle, die sowohl `app.domain.errors` als auch `home_assistant_adapter.errors` importieren darf — die einzige laut Import-Grenzen-Tabelle zulässige Übersetzungsposition.
- Editable-Install von `services/home-assistant-adapter` in `apps/customer-backend`s eigenes venv statt eines formalen PEP-508-Abhängigkeitseintrags — die beiden Pakete haben unabhängige `pyproject.toml`s ohne gemeinsamen Workspace-Manager; ein relativer Pfad in einem Abhängigkeitsstring wäre fragil. Siehe „Bekannte Grenzen" für eine wichtige Einschränkung dieses Ansatzes in dieser konkreten Entwicklungsumgebung.

## Bekannte Grenzen / offene Punkte

- **iCloud-synchronisierte Arbeitsverzeichnisse + Python-3.12-`.pth`-Verarbeitung**: Dieses Repository liegt unter einem iCloud-Drive-synchronisierten `Documents`-Ordner. macOS/iCloud setzt auf frisch erzeugten Dateien vorübergehend das `UF_HIDDEN`-Flag (sichtbar via `ls -lO`/`stat -f%f`), und Python 3.12s `site.py` überspringt `.pth`-Dateien mit gesetztem `UF_HIDDEN` explizit (`Skipping hidden .pth file`, sichtbar mit `python -v`). Das führte dazu, dass `pip install -e "../../services/home-assistant-adapter"` zwar `Successfully installed` meldete, das Paket aber **nicht tatsächlich importierbar war** — der `.pth`-Eintrag wurde bei jedem Interpreterstart stillschweigend übersprungen, und das Flag wurde von iCloud auch nach manuellem `chflags nohidden` innerhalb von Sekunden wieder gesetzt (kein zuverlässiger Fix). Tragfähige Lösung: `PYTHONPATH="../../services/home-assistant-adapter"` explizit setzen, wenn `apps/customer-backend`s Tests/Server laufen — das umgeht die `.pth`-Verarbeitung vollständig. Das `pip install -e` bleibt zusätzlich bestehen (liefert korrekte Metadaten/Abhängigkeitsauflösung), ist aber in dieser Umgebung **nicht ausreichend** für die tatsächliche Importierbarkeit. Diese Einschränkung betrifft nur die lokale Entwicklungsumgebung dieses Rechners, nicht CI/Produktion (dort keine iCloud-Synchronisation zu erwarten) — aber jede Person, die dieses Repo unter einem iCloud-Ordner klont, wird dasselbe Verhalten erleben.
- `device_id` in `DeviceService.send_command()` ist weiterhin adapter-abgeleitet, nicht die persistierte DB-`Device.id` aus `S1V2-02-017`s Registry — die Vereinheitlichung des Live-Adapter-Gerätepfads mit dem persistierten, haushaltsgebundenen `Device`/`Room`-Bestand ist eine separate, noch offene architektonische Lücke. Kein Haushalts-Zugehörigkeitscheck auf dieser Schicht. Im aktuellen Local-First-Deployment-Modell (eine Instanz pro Haushalt) kein akutes Sicherheitsleck (dieselbe Begründung wie bereits bei `SecretStore` in `S1V2-02-013` dokumentiert), aber eine offene Grenze, die hier bewusst benannt statt stillschweigend übergangen wird.
- `SimulationDeviceAdapter` weiterhin nicht um Lock/Climate/Camera erweitert (aus `S1V2-02-018` übernommene, bewusste Lücke) — `test_device_commands.py` bringt deshalb eine eigene minimale `_FakeDeviceAdapter` mit.
- Kein echter Docker-HA-Integrationstest speziell für `TranslatingHomeAssistantAdapter` (siehe Tests-Abschnitt oben für die Begründung).
