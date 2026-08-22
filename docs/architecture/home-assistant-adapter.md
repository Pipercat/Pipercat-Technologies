# HomeAssistantAdapter: einzige produktive Smart-Home-Integrationsgrenze (Stand 18.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-016 · HomeAssistantAdapter als einzige produktive Smart-Home-Integrationsgrenze implementieren`.
> Quellen: `DEC-7`, `DEC-20`. Implementierung: `services/home-assistant-adapter/home_assistant_adapter/`.

## Ausgangslage

`services/home-assistant-adapter` enthielt bisher nur ein ABC-Interface-Skeleton (`import_devices`/`apply_capability`/`subscribe_state_events`, 2 reine ABC-Mechanik-Tests, keinerlei HA-Netzwerkcode) — ein bewusst separates, mit dem tatsächlichen Domain-Port `apps/customer-backend/app/domain/adapter_port.py::DeviceAdapterPort` (`list_devices`/`apply_command`) nicht übereinstimmendes Interface. `docs/architecture/domain-device-model.md` benennt explizit den Akzeptanzpunkt dieser Aufgabe: „nur die Zeile `_device_adapter = SimulationDeviceAdapter()` wird durch die reale Adapterinstanz ersetzt" — d. h. der neue Adapter muss strukturell exakt `DeviceAdapterPort` erfüllen.

## Architektur

`HomeAssistantAdapter` (`home_assistant_adapter/adapter.py`) erfüllt `DeviceAdapterPort` strukturell (`list_devices`/`apply_command`, gleiche Methodennamen — Python-Protocols prüfen keine exakten Rückgabetypen, siehe unten) und stellt zusätzlich `list_areas()`/`subscribe_events()` bereit — die vom Notion-Task explizit geforderten „Areas"/„Live-Events", für die `DeviceAdapterPort` (noch) keine eigene Methode kennt.

Drei Schichten:

- **`ha_client.py`** — reiner Protokoll-Client: REST (`GET /api/states`, `POST /api/services/<domain>/<service>`) über `httpx`, WebSocket (`/api/websocket`, Auth-Handshake, Kommando/Ergebnis-Korrelation per `id`, `subscribe_events`) über `websockets`. Kapselt Auth (Long-Lived-Token als `Authorization: Bearer`), Timeout (`httpx`-Timeout + eigene `TransientDeviceError`) und Reconnect (`subscribe_events()` verbindet bei Verbindungsabbruch automatisch mit exponentiellem Backoff neu — für den Aufrufer unsichtbar, kein Ausnahme-Leck bei einem bloßen Netz-Hänger).
- **`mapping.py`** — reine Übersetzungsfunktionen HA-Entity ↔ SystemONE-Device-Dict, ohne Netzwerk, isoliert unit-testbar.
- **`adapter.py`** — verbindet beides zur öffentlichen `HomeAssistantAdapter`-Klasse.

## HA-IDs nie als öffentliche SystemONE-Primärschlüssel

`mapping.py::derive_device_id()` — jede zurückgegebene `device["id"]` ist `uuid5(NAMESPACE, entity_id)`, nie der rohe `entity_id`-String. Automatisiert getestet (`test_device_id_is_never_the_raw_entity_id`, plus gegen eine echte HA-Instanz: `test_list_devices_discovers_real_demo_entities` prüft explizit `"." not in device["id"]`). Der echte `entity_id` steht ausschließlich in `manufacturer_metadata` — deckungsgleich mit der bereits bestehenden Regel in `apps/customer-backend/app/domain/device.py`.

**Bewusst noch keine persistente Zuordnung**: Die Ableitung ist deterministisch, aber nicht in einer Datenbank verankert — ein Wechsel des `entity_id` in Home Assistant (z. B. durch manuelle Umbenennung) würde eine neue `device_id` erzeugen. Eine stabile, persistente Geräteregistrierung ist ausdrücklich Aufgabe von `S1V2-02-017` (siehe „Bewusst nicht Teil dieser Aufgabe").

## Warum `list_devices`/`apply_command` `dict`, nicht `DomainDevice`/`CapabilityState` zurückgeben

`services/home-assistant-adapter` hat laut `docs/architecture/repo-structure.md` **keine internen Abhängigkeiten** — es darf `app.domain.device.DomainDevice` (ein Pydantic-Modell in `apps/customer-backend`) nicht importieren. `typing.Protocol` prüft zur Laufzeit nur Methodennamen, keine exakten Rückgabetypen — die bereits im ursprünglichen Skeleton gewählte Lösung (`import_devices() -> list[dict[str, Any]]`) wird hier fortgeführt und auf die tatsächlichen Methodennamen (`list_devices`/`apply_command`) übertragen. Die zurückgegebenen Dicts sind feldgleich zu `DomainDevice`/`CapabilityState` aufgebaut — FastAPIs `response_model`-Validierung würde sie beim späteren Verdrahten automatisch in die echten Pydantic-Modelle koerzieren.

Aus demselben Grund kann der Adapter auch nicht die Fehlerklassen aus `app/domain/errors.py` werfen (Import-Grenze) — `home_assistant_adapter/errors.py` definiert eigene, namensgleiche Klassen (`DeviceNotFoundError`, `CapabilityNotSupportedError`, `TransientDeviceError`). Wer den Adapter künftig in `apps/customer-backend` verdrahtet, muss diese an der einen Verdrahtungsstelle in die Domain-Fehlerklassen übersetzen — als „Bekannte Grenze" unten dokumentiert, nicht stillschweigend übergangen.

## Auth/Connection/Reconnect/Timeout

- **Auth**: Long-Lived Access Token (Home-Assistant-Standardmechanismus für programmatischen Zugriff), als `Authorization: Bearer` sowohl bei REST als auch beim WebSocket-Handshake.
- **Timeout**: `httpx`-Timeout (Standard 10 s, konfigurierbar) für REST; WS-Verbindungsaufbau über `asyncio.wait_for` mit demselben Timeout. Timeout → `TransientDeviceError`, keine Endlos-Hänger.
- **Reconnect**: Nur `subscribe_events()` hält eine langlebige Verbindung — bricht sie ab, wird mit Backoff (2 s → verdoppelnd, gedeckelt bei 30 s) automatisch neu verbunden/authentifiziert. `list_areas()`/einzelne Befehle nutzen bewusst je eine kurzlebige, frische WS-Verbindung statt eine gehaltene Verbindung wiederzuverwenden — einfacher, kein Zustand zwischen seltenen Aufrufen zu pflegen.

## Direkte Herstelleradapter nur Dev-/Fallback-Pfad

Diese Aufgabe fügt ausschließlich `HomeAssistantAdapter` hinzu — kein einziger direkter Hersteller-/Protokolladapter (Zigbee/Matter/Shelly/Hue) wurde gebaut. Der reguläre Produktweg führt ab jetzt strukturell nur über diesen einen Adapter; ADR-0002s befristete Hue-Fallback-Klausel (Zeile 129 ff.) bleibt unverändert eine eigene, gesondert zu dokumentierende Ausnahme, nicht Teil dieser Aufgabe.

## Import-Grenze: Domain importiert keine HA-Bibliotheken direkt

Neue Regel in `scripts/check-import-boundaries.py`: `apps/customer-backend/app/domain/` darf `httpx`, `websockets` oder `home_assistant_adapter` nicht importieren. Automatisiert geprüft, aktuell keine Verletzung — die Domain-Schicht (`device.py`, `capabilities.py`, `service.py`, `adapter_port.py`, `errors.py`, `simulation_adapter.py`) bleibt vollständig adapter-agnostisch.

## `main.py`-Verdrahtung bewusst NICHT geändert

`app/main.py`s `_device_adapter = SimulationDeviceAdapter()` bleibt unverändert. Ein unbedingtes Umstellen auf `HomeAssistantAdapter()` würde bei jedem Prozessstart eine echte Netzwerkverbindung zu einer konfigurierten Home-Assistant-Instanz voraussetzen — das widerspricht dem lokalen „lokal-first"-Prinzip (Kundensystem muss auch ohne laufende/erreichbare Integration funktionieren) und setzt eine Möglichkeit voraus, Verbindungsdaten (Basis-URL, Token) zur Laufzeit aus einer konfigurierten `Integration`+`SecretStore`-Kombination (`S1V2-02-013`) zu lesen — die noch nicht existiert. Diese eigentliche Verdrahtung ist konsistent mit den bereits im alten Skeleton vorhandenen Verweisen auf „S1V2-02-017 ff." eine spätere, eigene Aufgabe.

## Tests (Definition of Done)

**Mock-Integrationstest**: `services/home-assistant-adapter/tests/test_adapter_mock.py` (7 Tests) — `HomeAssistantClient` durch eine Fake-Implementierung ersetzt, prüft `HomeAssistantAdapter`s eigene Logik (ID-Ableitung, Entity-Lookup-Cache, Kommando-Mapping) ohne Netzwerk.

**Echter HA-Integrationstest**: `tests/test_real_ha_integration.py` (5 Tests) — läuft gegen eine echte, per Docker gestartete Home-Assistant-Instanz mit aktivierter `demo:`-Plattform. `tests/ha_conftest.py` fährt den Onboarding-REST-Flow programmatisch (Admin-Benutzer anlegen, OAuth-Access-Token beziehen — Home Assistant hat keinen nicht-interaktiven „gib mir einfach einen Token"-Pfad). Deckt REST-Discovery, einen echten `light.turn_on`/`turn_off`-Service-Aufruf, den WebSocket-Auth-Handshake (`list_areas()`), und einen Live-Event-Roundtrip (Licht schalten → Event über die eigene WebSocket-Subscription empfangen) ab.

Lokal gestartet mit:
```bash
docker run -d --name ha-test -v "$(pwd)/ha-config:/config" -p 8123:8123 homeassistant/home-assistant:stable
# ha-config/configuration.yaml enthält nur: default_config: / demo:
HOME_ASSISTANT_URL=http://localhost:8123 pytest -q
```

**Mapping-Unit-Tests**: `tests/test_mapping.py` (13 Tests), rein, kein Netzwerk.

Gesamt `services/home-assistant-adapter`: **25 Tests bestanden** (13 Mapping + 7 Mock + 5 echte HA-Integration), alle grün gegen eine per Docker gestartete, frische Home-Assistant-Instanz.

**Betriebshinweis (gefundener Stolperstein):** Bei sehr langen Venv-Pfaden (z. B. `.../services/home-assistant-adapter/.venv312/bin/pytest`) generiert `pip` ein `/bin/sh`-Wrapper-Skript statt eines direkten Python-Shebangs (Shebang-Zeilenlängenlimit des Betriebssystems überschritten) — dieser Wrapper löst `python3` teils über `PATH` statt über das eigentliche venv auf, wodurch das venv-installierte Paket nicht gefunden wird (`ModuleNotFoundError: No module named 'home_assistant_adapter'`). Umgangen durch `python3.12 -m pytest` statt `pytest` direkt aufzurufen — funktioniert unabhängig von der Shebang-Länge.

**Betriebshinweis (gefundener Stolperstein):** `rm -rf verzeichnis/*` löscht in der Shell keine Punktdateien — beim Versuch, ein HA-Config-Verzeichnis zwischen Testläufen zurückzusetzen, überlebte `.storage/auth` (der Onboarding-Zustand) dadurch unbeabsichtigt, was einen frischen Container fälschlich als „bereits onboarded" erscheinen ließ. Richtig: das ganze Verzeichnis löschen und neu anlegen (`rm -rf verzeichnis && mkdir verzeichnis`), nicht nur seinen Inhalt per Glob.

## Bekannte Grenzen / offene Punkte

- Keine persistente Geräteregistrierung — `device_id` ist rein aus `entity_id` abgeleitet, nicht in einer Datenbank verankert (folgt mit `S1V2-02-017`).
- `home_assistant_adapter.errors.*` sind eigene Klassen, keine Wiederverwendung von `app.domain.errors.*` (Import-Grenze) — die Übersetzung an der Verdrahtungsstelle ist noch zu bauen, sobald diese existiert.
- `main.py` verdrahtet den Adapter noch nicht — siehe Begründung oben.
- Keine Area-/Room-Zuordnung (`room_id` ist immer `None`) — folgt mit der Areas-Verdrahtung in einer späteren Aufgabe.
- Reconnect-Backoff ist einfach (fest verdoppelnd, gedeckelt), kein Jitter — für den hier verlangten Zweck ausreichend, keine hochfrequente Parallel-Client-Situation zu erwarten (ein Adapter pro Kundensystem).
