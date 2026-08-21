# Shelly-Geräte lokal über Home Assistant integrieren und testen (Stand 21.08.2026)

> Notion-Aufgabe `S1V2-02-024 · Shelly-Geräte lokal über Home Assistant integrieren und testen` — **reine Hardware-Verifikationsaufgabe, kein neuer Code nötig.**
> Quelle: „Bestehender Kompatibilitätsplan".

## Warum hier nichts Neues gebaut wird

Anders als Zigbee (`S1V2-02-022`) und Matter (`S1V2-02-023`) hat Shelly **kein eigenes Pairing-/Commissioning-Protokoll**, das SystemONE orchestrieren müsste. Home Assistants Shelly-Integration erkennt Geräte per mDNS/lokalem Netzwerk und legt sie als ganz normale `switch`/`light`/`cover`/`sensor`-Entities an — genau die Domains, die `services/home-assistant-adapter/home_assistant_adapter/mapping.py::_SUPPORTED_DOMAINS` bereits seit `S1V2-02-018` abdeckt. Sobald ein Shelly-Gerät in Home Assistant eingerichtet ist, durchläuft es dieselbe `list_devices()`/Capability-Mapping-Pipeline wie jedes andere Gerät, ganz ohne Sonderfall.

„Zustände, Schalten" ist damit bereits durch `S1V2-02-002`/`-016`/`-018`/`-019` abgedeckt. „Reconnect und Geräteausfall" ist bereits durch `HomeAssistantClient`s Reconnect-Logik (`S1V2-02-016`, mit dem Bugfix aus `S1V2-02-020`) und die bestehende `TransientDeviceError`-Übersetzung abgedeckt — ein einzelnes Gerät, das offline geht, zeigt sich als fehlendes/`unavailable` Entity in `/api/states`, kein Sonderfall auf SystemONE-Seite. „Keine unnötige Cloudabhängigkeit" ist bereits durch die Architektur selbst erfüllt — `HomeAssistantAdapter` spricht ausschließlich mit der lokalen HA-Instanz, nie mit einer Shelly-Cloud.

## Was tatsächlich noch fehlt: reine Hardware-Verifikation

Diese Aufgabe ist im Notion-Datenmodell als **„Typ: Test"** markiert, nicht „Implementierung" — folgerichtig, denn es gibt nichts zu implementieren. Was fehlt, ist ausschließlich:

1. Ein echtes Shelly-Testgerät an eine laufende Home-Assistant-Instanz anschließen/einrichten (lokale Discovery, kein Cloud-Konto nötig).
2. Bestätigen: Zustand lesen, Schalten, Live-Zustandsänderung (`S1V2-02-020`s Resync-Mechanismus), Verhalten bei Trennung vom Netzwerk (Reconnect) und bei Geräteausfall (Entity wird `unavailable`, keine Exception, die SystemONE zum Absturz bringt).
3. Das getestete Modell (genaue Bezeichnung, z. B. „Shelly Plus 1PM") und seine tatsächlich beobachteten Capabilities hier dokumentieren.

## Bekannte Grenzen

- **Hardware-Nachweis ausstehend** — kein Zugriff auf ein echtes Shelly-Gerät in dieser Sandbox. Diese Aufgabe bleibt auf „In progress", bis eine Person mit echter Hardware Schritt 2 oben durchführt und das Ergebnis hier (bzw. in einer Aktualisierung dieses Dokuments) einträgt.
- Das volle dreistufige Certified/Compatible/Beta-Freigabemodell („nur getestete Modelle als freigegeben markieren") ist ausdrücklich `S1V2-02-026`s Aufgabe (bereits so in `docs/architecture/capability-mapping.md` festgehalten) — diese Aufgabe hier liefert nur die Dokumentation des einen getesteten Modells als Vorstufe dazu.
