# Zigbee über Home Assistant produktiv integrieren (Stand 21.08.2026)

> Erledigt den **Software-Anteil** der Notion-Aufgabe `S1V2-02-022 · Zigbee über Home Assistant produktiv integrieren` — siehe „Bekannte Grenzen" für den Hardware-Anteil, der in dieser Sandbox nicht verifiziert werden kann.
> Quelle: „SystemONE-Pi-Zigbee-Entscheidungen" (Notion, Bereich 06). Implementierung: `services/home-assistant-adapter/home_assistant_adapter/adapter.py`, `apps/customer-backend/app/services/{ha_device_adapter,zigbee_pairing}.py`.

## Wichtiger Hinweis vorab: Definition of Done nicht vollständig erfüllbar

Diese Aufgabe verlangt explizit: *„Mindestens ein reales freigegebenes Zigbee-Gerät lässt sich koppeln, steuern, entfernen und nach Neustart wiederfinden."* Das Wort „reales" ist hier keine Formsache — es bedeutet einen echten Sonoff Zigbee 3.0 USB Dongle Plus plus mindestens ein echtes Zigbee-Gerät, physisch an einem System angeschlossen. Diese Sandbox hat **keinen** Hardwarezugriff. Der komplette **Software-Anteil** (Pairing anstoßen, Gerät steuern über den bereits bestehenden Gerätebefehlspfad, Gerät entfernen, Fortschritt darstellen) ist unten vollständig implementiert und mit Fakes getestet — der **Hardware-Nachweis selbst** kann hier nicht erbracht werden und muss von einer Person mit dem echten Dongle nachgeholt werden, bevor diese Aufgabe in Notion auf „Done" gesetzt werden darf.

## Keine geratenen Fakten — alles gegen die echte Home-Assistant-Quelle geprüft

Um nicht wie schon einmal in diesem Projekt gewarnt („nicht raten, sondern als nicht unterstützt markieren") unverifizierte Annahmen über Home Assistants ZHA-Integration als Fakt zu verkaufen, wurden alle unten verwendeten Service-/Befehlsnamen direkt gegen den echten Quellcode von `home-assistant/core` geprüft (`gh api repos/home-assistant/core/contents/homeassistant/components/zha/...`), nicht aus dem Gedächtnis geraten:

- **`zha.permit`** (Service, Domain `zha`, Feld `duration`, Default 60s) — aus `homeassistant/components/zha/services.yaml`.
- **`zha.remove`** (Service, Domain `zha`, Pflichtfeld `ieee`) — dieselbe Quelle.
- **`zha/devices`** (einmaliger WebSocket-Befehl, gibt eine Liste von `ZHADeviceInfo`-Objekten zurück, mindestens mit `ieee`) — aus `homeassistant/components/zha/websocket_api.py::websocket_get_devices`.
- **USB-Erkennung des Sonoff-Dongles**: `homeassistant/components/zha/manifest.json`s `usb`-Matcher-Tabelle listet zwei Hardware-Revisionen — `vid=10C4/pid=EA60` (v1, CP2102-Chip) und `vid=1A86/pid=55D4` (v2, CH9102-Chip), beide über den Description-Glob `*sonoff*plus*` gematcht.

Diese letzte Erkenntnis führte zu einer wichtigen Architekturentscheidung (siehe unten): **SystemONE erkennt den USB-Dongle nicht selbst** — Home Assistants eigene `usb`-Integration tut das bereits zuverlässig, und ein zweiter, paralleler Erkennungspfad in Python würde ADR-0002s Prinzip verletzen, dass Home Assistant die *einzige* Hardware-Integrationsgrenze ist.

## Was gebaut wurde: reine Wiederverwendung bestehender Bausteine

Kein einziger neuer Low-Level-Protokoll-Mechanismus war nötig — `zha.permit`/`zha.remove` sind **normale Home-Assistant-Services**, genau wie `light.turn_on` oder `lock.lock`, die `HomeAssistantClient.call_service()` (seit `S1V2-02-016`) bereits unverändert unterstützt:

- `HomeAssistantAdapter.zha_permit_join(duration_seconds)` / `.zha_remove_device(ieee)` / `.zha_list_devices()` — drei schmale, feste Methoden (kein generischer „rufe irgendeinen Service auf"-Durchgriff, der das Whitelist-Sicherheitsmodell aus `S1V2-02-019` unterlaufen würde).
- `TranslatingHomeAssistantAdapter.start_zigbee_pairing()`/`.remove_zigbee_device()`/`.list_zigbee_gateway_devices()` — dieselbe Fehlerübersetzung wie jede andere Methode dieser Klasse.
- `ZigbeePairingService` (`apps/customer-backend/app/services/zigbee_pairing.py`, neu): `start_pairing()` (Berechtigung, Geräte-Schnappschuss vor dem Pairing, Audit), `discover_new_devices()` (Diff gegen den Schnappschuss — liefert normale `DomainDevice`s, **keinen** Zigbee-spezifischen Typ), `remove_device()` (Berechtigung, Audit).

## „Geräte erscheinen nach Pairing über reguläres Device Model" — praktisch geschenkt

Ein frisch gepairtes Zigbee-Gerät ist für Home Assistant einfach eine weitere Entity. Sobald ZHA sie anlegt, taucht sie in `/api/states` auf und durchläuft die bereits bestehende `list_devices()`/Mapping-Pipeline (`S1V2-02-016`/`-018`) ganz ohne Zigbee-spezifischen Code. `discover_new_devices()` diffed nur eine Schnappschussmenge von IDs — es erfindet kein Parallelmodell.

## „Fortschritt ... darstellen": Poll-basiert, nicht Stream-basiert

`websocket_permit_devices` in Home Assistants eigenem Quellcode zeigt, dass `zha/devices/permit` (der WebSocket-Befehl, nicht der hier verwendete `zha.permit`-Service) laufende Events über dieselbe Nachrichten-ID zurückschiebt — ein Abo-Mechanismus mit unklarem, nur gegen eine echte Zigbee-Koordinator-Instanz verifizierbarem Payload-Format (das separate `zha`-PyPI-Paket definiert die genaue Form, nicht `home-assistant/core` selbst). Statt hier zu raten, nutzt SystemONE bewusst den einfacheren, bereits vollständig getesteten `zha.permit`-**Service** plus Polling: `start_pairing()` nimmt einen Schnappschuss, `discover_new_devices()` wird vom Aufrufer während des Pairing-Fensters wiederholt aufgerufen — passt zu diesem Repos etablierter „immer live abfragen, nie cachen"-Philosophie (`DeviceService`, `S1V2-02-002`).

## Kein direkter Zigbee-Stack in Flutter

Backend-seitig bereits strukturell erzwungen: `apps/customer-app` (Flutter) hat keinen Grund, je `home_assistant_adapter`/ZHA-Vokabular zu sehen — `ZigbeePairingService`s öffentliche Methoden sprechen ausschließlich in SystemONE-Begriffen (`Actor`, `DomainDevice`, `ieee` als reiner String-Parameter). Es gibt aktuell keine API-Route, die diese Methoden aufruft (siehe „Bekannte Grenzen") — Flutter kann also schon allein deshalb nicht direkt zugreifen.

## Tests

- `services/home-assistant-adapter/tests/test_adapter_mock.py` (4 neue Tests): `zha_permit_join`/`zha_remove_device` rufen exakt die reale Home-Assistant-Service-Signatur auf, `zha_list_devices` reicht Rohdaten unverändert durch.
- `apps/customer-backend/tests/test_ha_device_adapter.py` (5 neue Tests): Fehlerübersetzung für alle drei neuen Methoden.
- `apps/customer-backend/tests/test_zigbee_pairing.py` (neu, 12 Tests): Berechtigungsprüfung, Audit bei Erfolg/Fehlschlag für Pairing-Start und Geräteentfernung, Schnappschuss-Diff liefert nur tatsächlich neue `DomainDevice`s.

Gesamt `apps/customer-backend`: **278/278 bestanden**. `services/home-assistant-adapter`: **49/49 bestanden, 6 übersprungen** (Docker-HA-Integrationstests unverändert). `python3 scripts/check-import-boundaries.py`: keine Verletzung. `python3 scripts/check-secrets.py`: kein Fund. `docker compose config`: erfolgreich validiert.

## Architekturentscheidungen

- **Kein SystemONE-seitiger USB-Geräte-Scan.** Home Assistants eigene `usb`-Integration erkennt den Dongle bereits zuverlässig (siehe Matcher-Tabelle oben) — ein zweiter Erkennungspfad würde ADR-0002s „Home Assistant ist die einzige Hardware-Integrationsgrenze" verletzen und die bereits durch HA gelöste USB-Erkennung duplizieren.
- **`zha.permit`/`zha.remove` als normale HA-Services statt der `zha/devices/permit`-WebSocket-Subscription.** Nutzt ausschließlich bereits existierende, bereits getestete Low-Level-Mechanik (`call_service()`); vermeidet, eine neue Streaming-Abstraktion auf einem Payload-Format aufzubauen, das nur mit echter Hardware verifizierbar wäre.
- **`zha_list_devices()`/`list_zigbee_gateway_devices()` bleiben rohe Durchreichungen**, nicht in einen SystemONE-Typ normalisiert — `ZHADeviceInfo`s genaue verschachtelte Feldstruktur lebt im separaten `zha`-PyPI-Paket, nicht in `home-assistant/core`; ein Parser darauf wäre vor echter Hardware-Verifikation reine Spekulation.
- **`ieee` als reiner, vom Aufrufer übergebener String-Parameter** statt einer SystemONE-internen `device_id → ieee`-Auflösung. Eine solche Auflösung bräuchte `zha_list_devices()`s genaue Feldform — siehe vorherigen Punkt.

## Bekannte Grenzen

- **Hardware-Nachweis der Definition of Done aussstehend** (siehe Hinweis oben) — Kopplung, Steuerung, Entfernung und Wiederauffindung nach Neustart mit einem echten Sonoff Zigbee 3.0 USB Dongle Plus und mindestens einem echten Zigbee-Gerät müssen von einer Person mit Zugriff auf diese Hardware durchgeführt und bestätigt werden, bevor diese Notion-Aufgabe auf „Done" gesetzt wird. „Nach Neustart wiederfinden" ist strukturell bereits durch bestehende Bausteine abgedeckt (ZHAs eigene Geräte-Registrierung liegt im persistenten `ha-config`-Volume aus `S1V2-02-021`, `list_devices()` fragt immer live ab) — aber auch das sollte am Ende gegen echte Hardware bestätigt werden, nicht nur angenommen.
- **`device_id → ieee`-Auflösung nicht gebaut** (s. o.) — `remove_device()` benötigt aktuell eine vom Aufrufer bereits bekannte `ieee`-Adresse. Ein `SystemONE-device_id`-basierter Entfernungsweg ist eine spätere Erweiterung, sobald `ZHADeviceInfo`s Feldform an echter Hardware verifiziert werden kann.
- **Keine API-Route** für `ZigbeePairingService` — die Methoden sind vollständig gebaut und getestet, aber (noch) an keine `/api/v1/*`-Route angebunden; das ist eine separate, spätere Aufgabe (dieselbe „gebaut, aber unverdrahtet"-Konvention wie `app/diagnostics.py` und `HomeAssistantSupervisor.export_diagnostics()` aus `S1V2-02-021`).
- **Kein automatisiertes Erst-Setup der ZHA-Integration selbst** (Config-Flow-Bestätigung, Koordinator-Auswahl) — diese Aufgabe setzt voraus, dass ZHA in der laufenden Home-Assistant-Instanz bereits eingerichtet ist; die Config-Flow-Automatisierung selbst wurde bewusst nicht nachgebaut (siehe „Kein SystemONE-seitiger USB-Geräte-Scan").
