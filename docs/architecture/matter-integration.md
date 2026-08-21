# Matter-Integration über Home Assistant implementieren und validieren (Stand 21.08.2026)

> Erledigt den **Software-Anteil** der Notion-Aufgabe `S1V2-02-023 · Matter-Integration über Home Assistant implementieren und validieren` — siehe „Bekannte Grenzen" für den Hardware-Anteil, der in dieser Sandbox nicht verifiziert werden kann.
> Quelle: „Bestehender SystemONE-Geräteplan". Implementierung: `services/home-assistant-adapter/home_assistant_adapter/adapter.py`, `apps/customer-backend/app/services/{ha_device_adapter,matter_commissioning}.py`.

## Wichtiger Hinweis vorab: Definition of Done nicht vollständig erfüllbar

Wie schon bei `S1V2-02-022` (Zigbee): die Definition of Done verlangt explizit *„mindestens ein reales Matter-Gerät wird eingebunden und über SystemONE gesteuert; Entfernen/Re-Pairing getestet"*. Diese Sandbox hat keinen Zugriff auf ein echtes Matter-Gerät oder einen Matter-Controller. Der komplette Software-Anteil ist unten implementiert und mit Fakes getestet — der Hardware-Nachweis selbst muss von einer Person mit echter Matter-Hardware nachgeholt werden, bevor diese Aufgabe auf „Done" gesetzt wird.

## Alle Fakten gegen den echten Home-Assistant-Quellcode geprüft

Dieselbe Sorgfalt wie bei `S1V2-02-022`: alle unten verwendeten WebSocket-Befehle wurden direkt gegen `home-assistant/core`s Quellcode geprüft (`gh api repos/home-assistant/core/contents/homeassistant/components/matter/api.py`), nicht geraten:

- **`matter/commission`** — Felder `code` (Pflicht, der Matter-Pairing-Code/QR-String), `network_only` (optional, Default `true`). Ruft intern `matter_client.commission_with_code()` auf.
- **`matter/commission_on_network`** — Felder `pin` (Pflicht, numerisch), `ip_addr` (optional) — für Geräte, die bereits im lokalen Netzwerk erreichbar sind.
- **`matter/remove_matter_fabric`** — Felder `device_id` (Home Assistants **eigene** Geräte-Registry-ID, nicht `entity_id`!) und `fabric_index` (Pflicht, numerisch) — entfernt die Matter-Fabric-Zugehörigkeit eines Geräts.
- **`matter/node_diagnostics`** — Feld `device_id` (dieselbe HA-Geräte-ID) — liefert u. a. die aktuellen Fabric-Zuordnungen, aus denen der für `remove_matter_fabric` nötige `fabric_index` ermittelt wird.

Anders als ZHA gibt es **keinen** `matter.commission`-Service — Commissioning läuft ausschließlich über diese WebSocket-Befehle, alle als einmalige Anfrage/Antwort (nicht wie ZHAs `zha/devices/permit` ein abonnierender Mechanismus mit laufenden Zwischennachrichten) — das vereinfacht die Anbindung erheblich gegenüber dem ursprünglich für Zigbee erwogenen Streaming-Ansatz.

## `device_id → HA-Geräte-ID`: diesmal lösbar, nicht nur ein `ieee`-String

Anders als bei Zigbee (wo die `ieee`-Adresse nur über das separate, nicht verifizierbare `zha`-PyPI-Paket auflösbar wäre) verwendet Matters `remove_matter_fabric`/`node_diagnostics` Home Assistants **eigene** Geräte-Registry-ID — genau das Feld, das `list_entity_registry()` (bereits aus `S1V2-02-017`, dort für die Raumzuordnung gebaut) bereits zurückgibt. `HomeAssistantAdapter.resolve_ha_device_id(device_id)` (neu) korreliert: SystemONE-`device_id` → `entity_id` (aus dem bereits bestehenden `_entity_id_by_device_id`-Cache) → HA-Geräte-ID (aus `list_entity_registry()`). Reine Wiederverwendung bereits existierender, bereits getesteter Bausteine — kein neuer Korrelationsmechanismus.

## Was gebaut wurde

- `HomeAssistantAdapter.matter_commission_with_code()`/`.matter_commission_on_network()`/`.matter_remove_fabric()`/`.matter_node_diagnostics()`/`.resolve_ha_device_id()`.
- `TranslatingHomeAssistantAdapter.start_matter_commissioning_with_code()`/`.start_matter_commissioning_on_network()`/`.remove_matter_device()`/`.get_matter_node_diagnostics()` — `remove_matter_device()`/`get_matter_node_diagnostics()` nehmen einen SystemONE-`device_id` entgegen und lösen intern zur HA-Geräte-ID auf (werfen `DeviceNotFoundError`, falls nicht auflösbar) — Aufrufer müssen den Unterschied zwischen den beiden ID-Räumen nie kennen.
- `MatterCommissioningService` (neu, `apps/customer-backend/app/services/matter_commissioning.py`) — spiegelt `ZigbeePairingService`s Form (Berechtigung, Geräte-Schnappschuss-Diff, Audit), bewusst eine eigene, nicht mit Zigbee geteilte Klasse (siehe Architekturentscheidungen).

## „Geräte erscheinen über reguläres Device Model" / „Fortschritt darstellen"

Identisch zu `S1V2-02-022`s Begründung: ein neu commissioniertes Matter-Gerät ist für Home Assistant einfach eine weitere Entity, durchläuft die bestehende `list_devices()`-Pipeline ohne Sonderfall. `discover_new_devices()` diffed nur eine Schnappschussmenge von IDs.

## „Nicht unterstützte Fabric-/Cloud-Sonderfälle klar melden"

Keine erfundene Fehlertaxonomie: eine abgelehnte Commissioning-Anfrage (falscher Code, ein Gerät, das eine Cloud-/Hersteller-App-Voreinrichtung braucht, die Home Assistants `matter`-Integration nicht unterstützt) erreicht den Aufrufer bereits als `TransientDeviceError` mit Home Assistants eigenem Fehlertext (`HomeAssistantClient.send_command()`s bestehende Behandlung nicht erfolgreicher WS-Antworten) — ein echtes, ausreichendes Signal, ohne Matter-spezifische Fehlerunterarten zu raten, die nur an einem echten Matter-Controller korrekt aufzählbar wären.

## Tests

- `services/home-assistant-adapter/tests/test_adapter_mock.py` (8 neue Tests): alle vier Matter-Befehle rufen exakt die reale Befehlssignatur auf, `resolve_ha_device_id()` findet die HA-Geräte-ID über die Entity-Registry bzw. liefert `None` für ein nie entdecktes Gerät.
- `apps/customer-backend/tests/test_ha_device_adapter.py` (8 neue Tests): Fehlerübersetzung, `DeviceNotFoundError` bei nicht auflösbarer HA-Geräte-ID.
- `apps/customer-backend/tests/test_matter_commissioning.py` (neu, 13 Tests): Berechtigungsprüfung, Audit bei Erfolg/Fehlschlag für beide Commissioning-Wege und Geräteentfernung, Schnappschuss-Diff liefert nur tatsächlich neue `DomainDevice`s.

Gesamt `apps/customer-backend`: **299/299 bestanden**. `services/home-assistant-adapter`: **57/57 bestanden, 6 übersprungen** (Docker-HA-Integrationstests unverändert). `python3 scripts/check-import-boundaries.py`: keine Verletzung. `python3 scripts/check-secrets.py`: kein Fund. `docker compose config`: erfolgreich validiert.

## Architekturentscheidungen

- **Kein gemeinsamer Basistyp mit `ZigbeePairingService`** trotz ähnlicher Form — die beiden Integrationen unterscheiden sich in den tatsächlich wichtigen Details (Pairing-Code/PIN vs. Permit-Dauer; aufgelöste HA-Geräte-ID vs. vom Aufrufer übergebene `ieee`), eine vorzeitige gemeinsame Abstraktion würde diese Unterschiede verstecken statt sie sichtbar zu halten.
- **`resolve_ha_device_id()` wiederverwendet `list_entity_registry()`** statt eines neuen Korrelationsmechanismus — bereits existierender, bereits getesteter Code aus `S1V2-02-017`.
- **Kein neuer Fehlertaxonomie-Code für „Fabric-/Cloud-Sonderfälle"** — die bestehende `TransientDeviceError`-Übersetzung mit erhaltenem HA-Fehlertext ist ausreichend und spekuliert nicht über unverifizierbare Matter-Fehlerarten.

## Bekannte Grenzen

- **Hardware-Nachweis der Definition of Done ausstehend** (siehe Hinweis oben) — Einbindung, Steuerung, Entfernen und Re-Pairing mit einem echten Matter-Gerät müssen von einer Person mit Zugriff auf diese Hardware durchgeführt und bestätigt werden, bevor diese Notion-Aufgabe auf „Done" gesetzt wird.
- **Keine API-Route** für `MatterCommissioningService` — vollständig gebaut und getestet, aber (noch) an keine `/api/v1/*`-Route angebunden, dieselbe Konvention wie `ZigbeePairingService`/`app/diagnostics.py`.
- **`matter/node_diagnostics`s genaue verschachtelte Antwortform** (insbesondere wie Fabric-Einträge dort exakt aufgelistet sind) bleibt unverarbeitete Rohdaten — das genaue Format lebt im separaten `python-matter-server`-Client, nicht in `home-assistant/core` selbst, und ist ohne echten Matter-Controller nicht verifizierbar.
- Kein automatisiertes Erst-Setup der `matter`-Integration selbst (Matter-Server-Addon-Installation, Config-Flow-Bestätigung) — setzt eine bereits eingerichtete `matter`-Integration voraus.
