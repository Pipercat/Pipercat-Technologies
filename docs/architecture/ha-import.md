# Home-Assistant-Geräte/Entities/Areas importieren, stabil zuordnen (Stand 18.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-017 · Home-Assistant-Geräte, Entitäten und Räume importieren und stabil zuordnen`.
> Quellen: `DEC-6`, `DEC-7`. Implementierung: `apps/customer-backend/app/services/ha_import.py`.

## Stabile Zuordnung statt Neuanlage bei jedem Import

`HomeAssistantImportService` (neu) importiert HA-Areas als `Room`-Zeilen und HA-Entities als `Device`-Zeilen — jeweils per `external_id` (HA `area_id`/`entity_id`) gegen bereits importierte Zeilen abgeglichen, nicht blind neu angelegt:

- **Areas → Rooms**: `Room` bekommt zwei neue Spalten `integration_id`/`external_id` (Migration `0004`, partieller Unique-Index nur wenn `external_id` gesetzt ist — von Hand angelegte Räume bleiben `external_id = NULL` und sind von der Eindeutigkeitsprüfung unberührt). `import_areas()` sucht per `RoomRepository.get_by_external_id()`; existiert die Area schon, wird bei Namensänderung nur `update_name()` aufgerufen (**gleiche** `room_id`), sonst wird eine neue Zeile angelegt.
- **Entities → Devices**: `Device.external_id` existierte bereits (`S1V2-02-001`/`-003`) — `import_devices()` nutzt dasselbe `get_by_external_id()`-Muster wie `DeviceRegistrationService`, jetzt aber mit einer neuen `DeviceRepository.update(device_id, name=..., room_id=...)`-Methode für Umbenennung/Raumwechsel am **bestehenden** Datensatz.

## Räume korrekt zuordnen: Entity- und Device-Registry korrelieren

Home Assistants `/api/states` (REST, von `list_devices()` genutzt) enthält **keine** Area-Zuordnung. Die reale Area-Zuordnung lebt in zwei WebSocket-Registries, die `HomeAssistantAdapter` jetzt zusätzlich bereitstellt (`list_entity_registry()`, `list_device_registry()`, beide über `config/entity_registry/list`/`config/device_registry/list`):

- Eine Entity hat entweder eine eigene `area_id`, **oder**
- sie erbt die `area_id` ihres übergeordneten HA-Geräts (Standardverhalten der meisten HA-Integrationen: das Gerät trägt die Area, nicht jede einzelne Entity).

`_resolve_entity_area_ids()` in `ha_import.py` bildet genau diese Auflösung (eigene Area zuerst, sonst die des Parent-Geräts) und übergibt das Ergebnis an `import_devices()`, das den zugehörigen `Room` per `external_id` nachschlägt. Ist die Area (noch) nicht importiert, bekommt das Gerät schlicht `room_id = None` — kein Fehler.

## Umbenennung/Room-Wechsel/temporär offline — kontrolliert, nie automatisch löschend

Alle drei DoD-Szenarien laufen über denselben Mechanismus:

- **Umbenennung** (Area oder Entity): `external_id` bleibt gleich → derselbe Datensatz wird gefunden → nur `name` ändert sich, keine neue Zeile.
- **Room-Wechsel**: dieselbe Entity, andere `area_id` → derselbe Device-Datensatz wird gefunden → nur `room_id` ändert sich.
- **Temporär offline**: eine Entity, die HA im aktuellen Import-Lauf nicht meldet, wird schlicht **nicht** in der Iteration besucht — ihr bestehender Datensatz bleibt exakt so, wie er war. Es gibt bewusst **keinen** Löschpfad für „nicht mehr gemeldete" Geräte/Räume in diesem Service — „kontrolliert behandeln" wird hier als „nie automatisch-still löschen" ausgelegt, nicht als „sofort löschen, sobald nicht mehr gesehen". Eine echte Entfernungslogik (z. B. nach einer definierten Karenzzeit) wäre eine bewusste, separate künftige Entscheidung, kein impliziter Nebeneffekt dieses Imports.

## Reihenfolge: Areas vor Devices

`sync_household()` importiert immer erst Areas, dann Devices — ein Gerät, dessen Area gerade neu importiert wurde, findet den zugehörigen Room sofort. Wer beide Schritte einzeln aufruft, muss diese Reihenfolge selbst einhalten (dokumentiert in `import_devices()`s Docstring).

## Architekturentscheidungen

- `HomeAssistantImportPort` ist ein lokales, minimales `Protocol` in `ha_import.py` (nicht der Import von `home_assistant_adapter.HomeAssistantAdapter`) — der Service ist damit ohne `httpx`/`websockets` als Testabhängigkeit unit-testbar, obwohl `apps/customer-backend` `services/home-assistant-adapter` laut Importgrenzen-Tabelle durchaus importieren dürfte.
- `Room.external_id` ist nullable und nur bei importierten Räumen gesetzt — von Kunden manuell angelegte Räume bleiben unverändert möglich und sind von der Uniqueness-Prüfung ausgenommen (partieller Index `WHERE external_id IS NOT NULL`).
- `DeviceRepository.update()`/`RoomRepository.update_name()` verlangen die vollständigen Zielwerte (kein Teil-Update mit Sentinel-Semantik) — der einzige Aufrufer (dieser Import-Service) kennt bei jedem Lauf ohnehin den vollständigen aktuellen HA-Zustand, „Teil-Update" hätte keinen echten Anwendungsfall.

## Gefundener Bug (nicht Teil dieser Aufgabe, im Vorbeigehen behoben)

Der volle Testlauf deckte einen latenten Zeit-Bug in `test_household_pin.py::test_reset_lockout_succeeds_once_admin_freshly_unlocked` auf (aus `S1V2-02-011`): der Test entsperrte den Admin-Bereich mit einem fest verdrahteten `now=t` (12:00 Uhr UTC, 18.08.2026), aber `HouseholdPinService.reset_lockout()` reichte gar kein `now` an die anschließende `AdminAreaService.require_unlocked()`-Prüfung durch — die lief also gegen die echte Wanduhrzeit. Der Test bestand nur so lange die reale Uhrzeit zufällig innerhalb des 5-Minuten-Fensters ab 12:00 Uhr lag; er schlug fehl, sobald die echte Zeit an genau diesem Kalendertag über 12:05 Uhr hinauslief — was während dieser sehr langen Session tatsächlich eintrat. Behoben durch ein neues optionales `now`-Parameter auf `reset_lockout()`, konsistent an `require_unlocked()` durchgereicht; der Test übergibt jetzt `now=t` an beiden Stellen.

## Tests (Definition of Done)

`apps/customer-backend/tests/test_ha_import.py` (14 Tests): Areas/Devices werden bei Neuimport angelegt, wiederholter Import ist idempotent (keine Duplikate), Umbenennung aktualisiert dieselbe Zeile, Room-Wechsel aktualisiert dieselbe Zeile, ein temporär nicht gemeldetes Gerät bleibt unverändert erhalten (weder gelöscht noch dupliziert), Raumzuordnung über eigene Entity-Area und über die Parent-Geräte-Area, unbekannte Area führt zu `room_id=None` statt Fehler, `sync_household()` importiert in der richtigen Reihenfolge, Berechtigungs-/Datenisolationsprüfungen.

`services/home-assistant-adapter/tests/test_adapter_mock.py`: 2 neue Tests für `list_entity_registry()`/`list_device_registry()`. `services/home-assistant-adapter/tests/test_real_ha_integration.py`: 1 neuer Test, der beide Registries gegen eine echte HA-Instanz abfragt.

Gesamt `apps/customer-backend`: **207/207 bestanden** (193 aus `S1V2-01-003`–`S1V2-02-015` + 14 neue Tests). `services/home-assistant-adapter`: **26/26 bestanden** (25 aus `S1V2-02-016` + 1 neuer Registry-Test), Mock/Mapping lokal verifiziert, echter Registry-Test gegen eine Docker-HA-Instanz verifiziert. `python3 scripts/check-import-boundaries.py`: keine Verletzung. `python3 scripts/check-secrets.py`: kein Fund. `docker compose config`: erfolgreich validiert.

## Bekannte Grenzen / offene Punkte

- Keine automatische Entfernung von Geräten/Räumen, die HA nicht mehr meldet — bewusst, siehe oben; eine künftige Aufgabe müsste eine explizite Karenzzeit-/Bestätigungslogik definieren.
- `HomeAssistantImportService` ist noch nicht über eine API-Route oder einen Scheduler aufrufbar — nur als Service-Methode nutzbar (etabliertes „dünne Router folgen später"-Muster).
- Capabilities/Zustände selbst werden bei diesem Import nicht aktualisiert (nur `name`/`room_id`) — das ist weiterhin `DeviceService.list_devices()`s/`apply_command()`s Aufgabe zur Laufzeit, nicht dieses Registrierungs-Imports.
