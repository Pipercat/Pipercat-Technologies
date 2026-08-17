# Domain Layer: Device Model & Capabilities (Stand 17.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-002 · Domain Layer für Haushalt, Räume, Geräte und Capabilities implementieren`.
> Quellen: `DEC-6`, `DEC-7`, `DEC-12`. Implementierung: `apps/customer-backend/app/domain/`.

## Zweck

SystemONE darf nicht direkt von Home-Assistant-Entity-Semantik (`entity_id`, `domain.service`-Aufrufe, HA-spezifische Attribute) abhängen. Der Domain Layer ist die Grenze: alles oberhalb davon (API, künftige Automationen) kennt nur SystemONEs eigenes, stabiles Vokabular.

## Bausteine

- **`capabilities.py`** — `CapabilityType`-Enum (`on_off`, `brightness`, `position`, `temperature`) und dazu je ein typisierter Pydantic-`State` und, wo sinnvoll, ein typisierter `Command` (diskriminierte Unions über `type`). `temperature` ist bewusst nur lesbar — es gibt kein `SetTemperatureCommand`, ein Versuch, es zu kommandieren, ist ein Domänenfehler.
- **`device.py`** — `DomainDevice`: `id`, `name`, `room_id`, `device_type`, `capabilities` (typisiert), `manufacturer_metadata` (freies Dict — der **einzige** Ort für Herstellerdetails, für Domänenlogik undurchsichtig).
- **`adapter_port.py`** — `DeviceAdapterPort`, ein `typing.Protocol` (strukturelle Typisierung, keine ABC-Vererbung). Das ist bewusst so gewählt: `services/home-assistant-adapter`s `HomeAssistantAdapter` kann diesen Port rein durch passende Methodensignaturen erfüllen, **ohne** `apps/customer-backend` zu importieren — vermeidet eine Rückwärtsabhängigkeit, die die Importgrenzen aus `docs/architecture/repo-structure.md` verletzen würde („home-assistant-adapter darf keine App importieren").
- **`service.py`** — `DeviceService`: die einzige Stelle, die mit einem `DeviceAdapterPort` spricht. Prüft Geräteexistenz selbst nach (`DeviceNotFoundError`), verlässt sich nicht darauf, dass jeder Adapter das sauber macht.
- **`simulation_adapter.py`** — `SimulationDeviceAdapter`: Dev-/Test-Implementierung von `DeviceAdapterPort`, im Geiste des bestehenden Node-Piloten (`mvp/systemone-pi/lib/simulation.js`), aber im SystemONE-eigenen typisierten Modell statt Ad-hoc-JSON.
- **`errors.py`** — `DeviceNotFoundError`, `CapabilityNotSupportedError` — Domänenfehler, in `app/main.py` auf HTTP 404/400 mit den üblichen `ApiError`-Codes abgebildet (`DEVICE_NOT_FOUND`, `CAPABILITY_NOT_SUPPORTED`).

## API-Anbindung (Beweis für die Definition of Done)

`app/main.py` verdrahtet `SimulationDeviceAdapter` + `DeviceService` als Modul-Singleton (mit einer simulierten Lampe vorbelegt) hinter zwei Endpunkten:

- `GET /api/v1/devices` — Geräteliste.
- `POST /api/v1/devices/{id}/commands` — typisierter Befehl (`{"type": "on_off", "is_on": true}` usw.), Antwort ist der neue, typisierte Zustand.

**Wenn `S1V2-02-016` (`HomeAssistantAdapter`) landet, ändert sich an diesen beiden Routen nichts** — nur die Zeile `_device_adapter = SimulationDeviceAdapter()` wird durch die reale Adapterinstanz ersetzt. Das ist der konkrete Beweis für „simulierte Lampe kann über dieselbe SystemONE-API gelesen/gesteuert werden wie später echte Hardware".

## Tests

- `tests/test_domain_device.py` (7 Tests) — **reine Domänentests, kein FastAPI, kein HTTP, keine Zeile Home-Assistant-Code** im gesamten Testmodul. Deckt ab: Ausgangszustand, Befehl ändert Zustand, ungültiger Wertebereich wird bereits vom typisierten Command abgelehnt (Pydantic-Validierung, nicht erst Adapter-Logik), unbekanntes Gerät → `DeviceNotFoundError`, nicht unterstütztes Capability → `CapabilityNotSupportedError`, Herstellermetadaten vorhanden aber nicht Teil der Domänenprüfung.
- `tests/test_devices_api.py` (4 Tests) — dieselbe simulierte Lampe über die echten HTTP-Endpunkte gelesen/gesteuert; Fehlerfälle (unbekanntes Gerät, ungültiger Wertebereich) liefern die erwarteten Envelope-Fehlercodes bzw. `422`.
- Gesamt `apps/customer-backend`: **48/48 Tests bestanden** (Python 3.12, siehe `docs/architecture/data-model.md` für den Python-3.14-Sandbox-Hinweis, der weiterhin gilt).

## Bewusst nicht Teil dieser Aufgabe

- Persistenz der Domain-Objekte in PostgreSQL (Mapping `DomainDevice` ↔ `app/db/models.py::Device` — das ist die Service-/Repository-Schicht aus `S1V2-02-003`).
- Reale Home-Assistant-Anbindung (`S1V2-02-016` ff.).
- Weitere Capability-Typen (Farbe/Farbtemperatur, Thermostat-Modus) — werden bei Bedarf nach demselben Muster ergänzt (neuer `CapabilityType`-Wert + `State`/`Command`-Paar), keine Strukturänderung nötig.
