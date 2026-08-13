# SystemONE Pi: Geräte- und Herstellermatrix

Stand: 13. August 2026

Diese Matrix ist die verbindliche Freigabegrundlage für den geschlossenen Pilot. „Implementiert“ ist nicht gleichbedeutend mit „hardwarefreigegeben“.

## Kompatibilitätsklassen

- **SystemONE Certified:** vollständig gegen festgelegtes Modell, Firmware und Fehlerfälle getestet; normaler Einrichtungsablauf.
- **SystemONE Compatible:** Kernfunktionen getestet; bekannte Einschränkungen werden angezeigt.
- **Experimentell / Beta:** bewusste Aktivierung erforderlich; keine vollständige Funktions- oder Supportgarantie.
- **Nicht unterstützt:** nicht im normalen Einrichtungsablauf verfügbar.

## Aktuelle Matrix

| Integration / Hersteller | Profile | Aktueller Stand | Pilot | Cloud | Nächster Freigabenachweis |
|---|---|---|---|---|---|
| SystemONE Simulation | Licht, Schalter, Sensor, Thermostat, Rollladen | Experimentell; 50+ Selftests | Ja, Entwicklung | keine | bleibt Testwerkzeug, keine Hardwarefreigabe |
| Philips Hue Bridge | Licht | Experimentell; Adapter und Fehlermatrix hardwarefrei | Ja | keine Hue-Cloud | reale Bridge, Modell/Firmware, Pairing, Neustart, IP-Wechsel, Offline und Reconnect |
| Govee LAN | Licht | Nicht unterstützt | Nein | nur lokale Modelle vorgesehen | Simulation, danach konkrete lokale Modelle |
| Matter | fünf Kernprofile | Nicht unterstützt | Nein | keine Pflicht-Cloud | Controller-, Fabric-, Modell- und Fehlerpfad |
| Shelly LAN | Licht, Schalter, Sensor | Nicht unterstützt | Nein | nur lokale APIs | konkrete Modelle/Firmware und Ausfallmatrix |
| Zigbee | fünf Kernprofile | Nicht unterstützt | Nein | keine | freigegebener Stick, Koordinator/Firmware und Modellmatrix |
| IKEA Home smart | Licht, Schalter, Sensor, Rollladen | Nicht unterstützt | Nein | keine | erst nach freigegebenem Zigbee-Pfad |

## Pilotregel

Der geschlossene Pilot darf nur Philips-Hue-Modelle als reale Geräte anbieten, die in Aufgabe 25 mit Hardwareprotokoll mindestens als **SystemONE Compatible** veröffentlicht wurden. Bis dahin zeigt der normale Geräteassistent ausschließlich die Simulation; `HUE_MODE=simulation` bleibt Standard.

## Pflichtfelder jeder späteren Modellfreigabe

- Hersteller, Modellnummer und Hardwareversion
- getestete Firmwareversion oder unterstützter Bereich
- Integration und Geräteprofil
- unterstützte Capabilities
- lokale beziehungsweise Cloud-Abhängigkeiten
- Testdatum, Testumgebung und verantwortliche Person
- Discovery-, Pairing-, Steuer-, Neustart-, Offline- und Recovery-Ergebnis
- bekannte Einschränkungen und Supporthinweis
- zugewiesene Kompatibilitätsklasse

Die maschinenlesbare Pilotmatrix liegt in `mvp/systemone-pi/lib/compatibility.js` und wird über `GET /api/compatibility` ausgegeben.
