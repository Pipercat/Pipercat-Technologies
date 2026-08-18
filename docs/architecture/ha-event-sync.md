# Home-Assistant-Live-Events robust mit SystemONE-Zuständen synchronisieren (Stand 18.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-020 · Home-Assistant-Live-Events robust mit SystemONE-Zuständen synchronisieren`.
> Quellen: `DEC-6`, `DEC-7`. Implementierung: `services/home-assistant-adapter/home_assistant_adapter/{ha_client,adapter}.py`, `apps/customer-backend/app/services/{ha_device_adapter,ha_event_ingestion}.py`.

## Ein Resync-Signal statt eines zweiten Mechanismus

„Initialer Snapshot plus Live-Deltas" und „Reconnect und Resync durchführen" klingen nach zwei verschiedenen Dingen, sind hier aber **ein und derselbe Mechanismus**: `HomeAssistantClient.subscribe_events()` (`services/home-assistant-adapter/home_assistant_adapter/ha_client.py`) gibt bei jeder (Wieder-)Herstellung einer Subscription — **einschließlich der allerersten** — zuerst `{"kind": "connected"}` zurück, bevor irgendein `{"kind": "event", "event": ...}`-Item folgt. Der erste Verbindungsaufbau eines Prozesses und eine Wiederverbindung nach einem Netzausfall sind aus Sicht dieses Signals ununterscheidbar — beide bedeuten exakt dasselbe: „hier beginnt eine frische, lückenlose Sicht auf den aktuellen Zustand; alles, was du vorher zu wissen glaubtest, könnte veraltet sein."

`HomeAssistantAdapter.subscribe_events()` normalisiert das zu `{"kind": "resync"}` bzw. `{"kind": "device_changed", "deviceId", "entityId", "device"}`. `TranslatingHomeAssistantAdapter.subscribe_events()` (`apps/customer-backend/app/services/ha_device_adapter.py`, an derselben Übersetzungsgrenze wie schon in `S1V2-02-019`) koerziert das rohe `device`-Dict zu einem echten `DomainDevice`.

## Warum kein separater „initialer Snapshot"-Code

`HomeAssistantEventIngestionService` (`apps/customer-backend/app/services/ha_event_ingestion.py`) hat **keinen** eigenen Startup-Sonderfall für „hole einmal alle Geräte". Stattdessen behandelt `_resync()` jedes `resync`-Item identisch: vollständige `list_devices()`-Abfrage, Diff gegen den zuletzt bekannten Stand (`self._known_devices`), ein `device.state_changed`-Event pro tatsächlich geändertem Gerät. Beim allerersten `resync` ist „zuletzt bekannt" leer, also wird für jedes vorhandene Gerät einmal published — das *ist* der initiale Snapshot, ohne eigenen Pfad. Nach einem Wiederverbindungs-`resync` ist „zuletzt bekannt" der Stand vor dem Verbindungsabbruch — der Diff findet exakt die Änderungen, die während der Störung passiert sind und nie als `device_changed`-Event ankommen konnten, weil dafür schlicht keine Verbindung bestand.

Geräte, die zwischen zwei Resyncs verschwunden sind (z. B. in Home Assistant entfernt, während die Verbindung unterbrochen war), lösen ein `device.removed`-Event aus.

## Warum kein persistenter Zustand repariert werden muss

`DeviceService.list_devices()`/`get_device()` (`app/domain/service.py`, `S1V2-02-002`) fragen den Adapter bei **jedem** Aufruf live ab — es gibt keinen In-Memory- oder DB-Cache, den ein Reconnect „reparieren" müsste. Die `Device`-Tabelle (`S1V2-02-001`/`-017`) speichert Identität und Raumzuordnung, keinen Zustand. „Konsistenter SystemONE-Zustand nach Wiederverbindung" ist deshalb kein Datenbankreparatur-Problem, sondern ein **Ereignis-Vollständigkeits-Problem**: `AutomationEngine.on_device_event()` (`S1V2-02-005`) und jeder künftige ereignisgetriebene Konsument müssen irgendwann ein Event pro tatsächlicher Zustandsänderung sehen — auch für Änderungen, die während der Störung passiert sind und nie als einzelnes `state_changed`-Event ankommen konnten. `HomeAssistantEventIngestionService`s eigener `self._known_devices`-Stand ist ausschließlich internes Diffing-Hilfsmittel, nie ein Cache, den irgendetwas anderes liest.

## Robustheit auf Client-Ebene

Zwei Eigenschaften von `HomeAssistantClient.subscribe_events()` bereits aus `S1V2-02-016`, in diesem Umfang jetzt erstmals direkt unit-getestet (`services/home-assistant-adapter/tests/test_ha_client_subscribe_events.py`, ohne echte HA-Instanz — die Auth-Handshake-Korrektheit selbst bleibt `test_real_ha_integration.py`s Aufgabe):

- **Exponentielles Reconnect-Backoff** bei Verbindungsfehlern (`HomeAssistantConnectionError`/`HomeAssistantAuthError`), gedeckelt bei `MAX_RECONNECT_BACKOFF_SECONDS`, zurückgesetzt nach jeder erfolgreichen (Wieder-)Subscription.
- **Ein während dieser Aufgabe behobener Bug**: eine von Home Assistant abgelehnte `subscribe_events`-Anfrage (`TransientDeviceError`) wurde bisher *nicht* vom Reconnect-`except`-Block abgefangen — sie hätte den gesamten Event-Generator beendet, statt wie jeder andere transiente Fehler einen Wiederverbindungsversuch auszulösen. Jetzt: `except (ConnectionClosed, OSError, TransientDeviceError): continue`.

## Event-Reihenfolge

Ein einzelner `async for`-Konsument verarbeitet Items strikt sequenziell — ein `resync`-Item wird immer vollständig verarbeitet (inklusive der `list_devices()`-Abfrage), bevor das nächste Item aus dem Strom gelesen wird. Ein `device_changed`-Event, das während eines laufenden Resyncs eintrifft, wartet also einfach in der Warteschlange, statt mit dem Resync zu wettlaufen — keine zusätzliche Sperre nötig.

## Tests (Definition of Done)

- **Client-Ebene** (`services/home-assistant-adapter/tests/test_ha_client_subscribe_events.py`, 4 Tests, gefakte `_connect_and_authenticate` statt echtem WebSocket): `connected`-Marker vor dem ersten Event, ein Verbindungsabbruch führt zu einem frischen `connected`-Marker nach der Wiederverbindung, eine abgelehnte Subscription wird wiederholt statt den Strom zu beenden, ein Verbindungsfehler löst das erwartete Backoff aus.
- **Adapter-Ebene** (`services/home-assistant-adapter/tests/test_adapter_mock.py`, angepasst + 1 neuer Test): `resync`-Marker vor jedem normalisierten Geräte-Update.
- **Ingestion-Ebene** (`apps/customer-backend/tests/test_ha_event_ingestion.py`, 7 Tests, gefakter `TranslatingHomeAssistantAdapter`): initialer Snapshot published für jedes Gerät, leerer initialer Snapshot published nichts, inkrementelles Update published nur bei tatsächlicher Änderung, **Resync nach simuliertem Verbindungsabbruch findet eine währenddessen verpasste Änderung** (der Kernbeweis der Aufgabe), Resync ohne tatsächliche Änderung published nichts, entferntes Gerät löst `device.removed` aus.

Gesamt `apps/customer-backend`: **242/242 bestanden** (235 aus `S1V2-01-003`–`S1V2-02-019` + 7 neue). `services/home-assistant-adapter`: **45/45 bestanden, 6 übersprungen** (41 + 4 neue Client-Tests; ein bestehender Adapter-Test umbenannt/erweitert statt hinzugefügt; Docker-HA-Integrationstests unverändert). `python3 scripts/check-import-boundaries.py`: keine Verletzung. `python3 scripts/check-secrets.py`: kein Fund. `docker compose config`: erfolgreich validiert.

## Architekturentscheidungen

- Resync-Signal auf Client-Ebene erzeugt (`ha_client.py`), Diff-/Publish-Logik erst in `apps/customer-backend` (`ha_event_ingestion.py`) — `services/home-assistant-adapter` bleibt frei von jeglichem SystemONE-Domänenwissen (Zero-Dependency-Grenze, unverändert seit `S1V2-02-016`); der Client weiß nur „hier beginnt eine frische Sicht", nicht warum das wichtig ist.
- Ein Signal für „initial" und „nach Reconnect" statt zweier getrennter Codepfade — ein leerer `_known_devices`-Stand behandelt den Erstfall bereits korrekt als „alles ist neu".
- `HomeAssistantEventIngestionService` ist bewusst **nicht** in `app/main.py`s Standard-Startup verdrahtet — dieselbe, bereits in `docs/architecture/mqtt-eventbus.md`s „Bewusst nicht Teil dieser Aufgabe" getroffene Entscheidung: `main.py` bleibt bei `SimulationDeviceAdapter`/`InMemoryEventBus`, die Umstellung auf die echten Implementierungen (inkl. FastAPI-Lifespan-Start/Stop für den Ingestion-Hintergrund-Task) ist eine eigene, noch ausstehende Verdrahtungsaufgabe.

## Bekannte Grenzen / offene Punkte

- **Nicht in `main.py` verdrahtet** (s. o.) — `HomeAssistantEventIngestionService` existiert, ist vollständig getestet, läuft aber in der Produktion erst, sobald eine spätere Aufgabe `main.py`s Lifespan um Start/Stop dieses Hintergrund-Tasks (plus echte HA-Zugangsdaten aus dem Secret-Store, `S1V2-02-013`) erweitert.
- Kein Sequenz-/Versionszähler auf Event-Ebene — Verlässlichkeit kommt ausschließlich aus dem Resync-Diff (vollständiger Neuabgleich), nicht aus Lückenerkennung einzelner Events. Für dieses System ausreichend, da `DeviceService` ohnehin nie auf Event-Historie statt Live-Zustand vertraut.
- `EventBus.publish()` (`InMemoryEventBus`/`MqttEventBus`) hat bereits eigene Duplikat-Toleranz (`S1V2-02-004`) — ein durch einen Resync erzeugtes, inhaltlich identisches Event zu einem bereits zuvor gesendeten würde dort nicht dedupliziert, da `HomeAssistantEventIngestionService` selbst schon verhindert, dass unveränderte Zustände überhaupt ein Event auslösen (Diff vor Publish). Kein zusätzlicher Schutz nötig.
- Kein eigener Docker-HA-Integrationstest speziell für das Resync-Verhalten (nur für den Grundmechanismus „ein reales `state_changed`-Event kommt an", unverändert seit `S1V2-02-016`) — das Reconnect-Verhalten selbst gegen eine echte, hart neugestartete HA-Instanz zu verifizieren wäre ein separater, deutlich aufwändigerer Test (Container-Neustart mitten im Testlauf, ähnlich `S1V2-02-004`s Mosquitto-Neustart-Test) und ist hier bewusst durch die gefakte Client-Ebene ersetzt.
