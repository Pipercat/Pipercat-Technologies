# HA-Entities auf SystemONE-Capabilities mappen (Stand 18.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-018 · HA-Entities auf SystemONE-Capabilities und Zustände mappen`.
> Quellen: `DEC-6`, `DEC-12`. Implementierung: `apps/customer-backend/app/domain/capabilities.py`, `services/home-assistant-adapter/home_assistant_adapter/mapping.py`.

## Drei neue Capability-Typen

`app/domain/capabilities.py` (aus `S1V2-02-002`, dort bereits als „weitere Typen nach demselben Muster ergänzbar" angekündigt) bekommt drei neue `CapabilityType`-Werte, jeweils mit typisiertem `State`, wo sinnvoll auch `Command`:

| Typ | State | Command | Kommandierbar |
|---|---|---|---|
| `lock` | `LockState.is_locked: bool` | `SetLockCommand` | ✅ |
| `climate` | `ClimateState.target_celsius, mode` | `SetClimateCommand` | ✅ |
| `camera_stream` | `CameraStreamState.is_available: bool` | — | ❌ (read-only, wie `temperature`) |

`ClimateMode` ist bewusst ein enges Enum (`off`/`heat`/`cool`/`auto`) — HA-Modi außerhalb dieser Menge (`dry`, `fan_only`, `heat_cool`) werden nicht auf den nächstliegenden Wert geraten, sondern führen dazu, dass die Climate-Capability für diese Entity schlicht fehlt. Ein `SetClimateCommand` mit einem nicht normalisierten Modus wird bereits von Pydantic mit `ValidationError` abgelehnt, bevor irgendeine Domänenlogik läuft — dasselbe Muster wie das bestehende `SetBrightnessCommand`, das Werte außerhalb 0–100 ablehnt.

`camera_stream` meldet ausschließlich, **ob** ein Live-Feed existiert — nie eine Stream-URL, ein Token oder sonstigen Zugriffsdetail. Der tatsächliche Kamerazugriff (Ansicht/Aufnahme) ist eine eigene, sicherheitskritische künftige Aufgabe (voraussichtlich eine „geschützte Aktion" nach dem Muster aus `S1V2-02-012`), hier bewusst nicht vorweggenommen.

## HA-Entity → SystemONE-Capability

`services/home-assistant-adapter/home_assistant_adapter/mapping.py::_capabilities_for()` erweitert um:

- **Lock**: HA-Zustände `locked`/`unlocked` → `is_locked`. Übergangszustände (`locking`/`unlocking`/`jammed`) werden **nicht** geraten — die Capability fehlt schlicht, bis ein eindeutiger Endzustand erreicht ist.
- **Climate**: `attributes.hvac_mode` (Fallback: der State-String selbst) + `attributes.temperature` → `ClimateState`. Nur normalisierte Modi (s. o.) werden gesetzt.
- **Camera**: jeder State außer `unavailable`/`unknown`/`None` → `is_available: true`.

`command_to_service_call()` entsprechend erweitert: `lock`/`unlock`-Service-Aufrufe für Locks, `set_temperature` (mit `hvac_mode`) für Climate. Für `camera_stream` existiert bewusst kein Zweig — ein Kommandoversuch wirft `CapabilityNotSupportedError`, dieselbe Fehlerklasse wie jede andere nicht unterstützte Kombination.

## „Nicht erraten, sondern als nicht unterstützt markieren"

Jedes Device-Dict trägt jetzt ein `compatibility`-Feld: `"supported"`, wenn die HA-Domain der Entity zu den bekannten Domains gehört (`light`, `switch`, `cover`, `sensor`, `climate`, `lock`, `camera`), sonst `"unsupported"`. `binary_sensor` ist **bewusst ausgeschlossen**: sein boolescher Zustand bedeutet je nach `device_class` etwas anderes (Bewegung/Tür/Anwesenheit/…) und ist nicht dasselbe wie ein kommandierbares `on_off` — das auf `on_off` abzubilden wäre exakt das Raten, das diese Aufgabe verbietet. Bis eine eigene Boolean-Sensor-Capability existiert, bleibt `binary_sensor` `"unsupported"`.

Das volle dreistufige Certified/Compatible/Beta-Modell ist ausdrücklich `S1V2-02-026`s Aufgabe — dieses `compatibility`-Feld ist nur das binäre Signal, das die hiesige Definition of Done verlangt.

## „UI/API sehen nur SystemONE-Capabilities"

Automatisiert bewiesen (`test_device_dict_never_leaks_ha_vocabulary_outside_manufacturer_metadata`): für mehrere Entity-Fixtures (Light, Lock, Climate, Camera) wird geprüft, dass jeder Capability-Schlüssel und jedes `type`-Feld ausschließlich aus der bekannten `CapabilityType`-Menge stammt — nirgendwo außerhalb von `manufacturer_metadata` taucht ein roher HA-Begriff (`entity_id`, `hvac_mode`, `current_position` usw.) auf.

## Tests (Definition of Done)

**Fixture-Tests mit verschiedenen HA-Entitytypen**: `services/home-assistant-adapter/tests/test_mapping.py` — neue Tests für Lock (inkl. Übergangszustände), Climate (inkl. nicht normalisierter Modi), Camera (inkl. `unavailable`), `compatibility`-Markierung für alle sieben unterstützten Domains sowie explizit für `binary_sensor` und eine unbekannte Domain, plus die Vokabular-Leck-Prüfung. `command_to_service_call()`-Tests für Lock/Climate/die Ablehnung von Camera-Kommandos.

**Domain-seitige Modell-Tests**: `apps/customer-backend/tests/test_capabilities_extended.py` (neu, 8 Tests) — reine Pydantic-Validierung der drei neuen Typen über die diskriminierten Unions, `ClimateMode`-Validierung, `COMMANDABLE_TYPES`-Zugehörigkeit.

Gesamt `apps/customer-backend`: **215/215 bestanden** (207 aus `S1V2-01-003`–`S1V2-02-017` + 8 neue). `services/home-assistant-adapter`: Mapping-/Mock-Tests **41/41 bestanden** (echter HA-Integrationstest nicht Teil dieser Aufgabe erneut ausgeführt, da keine HA-Client-/Protokolländerung — nur die reine Mapping-Schicht betroffen). `python3 scripts/check-import-boundaries.py`: keine Verletzung. `python3 scripts/check-secrets.py`: kein Fund. `docker compose config`: erfolgreich validiert.

## Architekturentscheidungen

- Neue Capability-Typen nach exakt demselben Muster wie die bestehenden vier (`CapabilityType`-Wert + `State`/optional `Command`, discriminierte Pydantic-Union) — keine Strukturänderung, wie in `S1V2-02-002`s Doku bereits vorgesehen.
- `SimulationDeviceAdapter` bewusst **nicht** um Lock/Climate/Camera erweitert — außerhalb des Aufgabenumfangs (diese Aufgabe betrifft die HA-Mapping-Schicht, nicht den Simulationsadapter); bei Bedarf nach demselben Muster nachrüstbar.
- `compatibility` als eigenes Top-Level-Feld statt implizit aus leeren `capabilities` abgeleitet — macht „wir kennen diese Entity nicht" von „wir kennen sie, aber sie hat gerade keine auslesbare Capability" (z. B. ein Feuchtigkeitssensor) unterscheidbar.

## Bekannte Grenzen / offene Punkte

- Volles Certified/Compatible/Beta-Modell folgt mit `S1V2-02-026`.
- `binary_sensor` bleibt unterstützungslos, bis eine eigene Boolean-Sensor-Capability entworfen wird.
- Tatsächlicher Kamera-Stream-Zugriff (Ansicht/Aufnahme/Zugangsdaten) ist explizit nicht Teil dieser Aufgabe — nur die Existenz-Meldung.
- `SimulationDeviceAdapter` unterstützt die neuen Typen noch nicht.
- Farbe/Farbtemperatur bei Lichtern weiterhin nicht abgebildet (wie bereits in `S1V2-02-002` als bewusste Lücke dokumentiert) — bei Bedarf nach demselben Muster ergänzbar.
