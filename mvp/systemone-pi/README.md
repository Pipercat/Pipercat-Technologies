# SystemONE Pi Core v0.4.0

Local-first Core mit normalisiertem Device Model. Standardmäßig läuft alles in Simulation; das produktive Philips-Hue-System wird nicht angesprochen.

## Neu in v0.4.0

- herstellerunabhängiges Device Model mit `profile`, `availability`, `compatibility`, `capabilities` und `diagnostics`
- Capability-Layer mit profilbezogener Validierung und Wertebegrenzung
- gemeinsames Adapter-Interface für Discovery, Pairing, Geräteliste und Befehle
- Hue- und Simulation-Adapter liefern dasselbe normalisierte Modell
- zentrale Geräte-Registry mit Geräteereignissen
- API und Weboberfläche verwenden ausschließlich normalisierte Capabilities wie `power` und `brightness`
- automatische Migration vorhandener v0.3.1-Geräte beim Laden
- interne Adapterdaten werden nicht über Geräte-Endpunkte ausgegeben
- 17 hardwarefreie Selftests

## Backup Schema v2

- SHA-256 über kanonisch serialisierte Backup-Daten
- Schema- und Systemversion sowie Erstellzeitpunkt
- strikte Größen-, Raum-, Geräte- und Capability-Validierung vor Restore
- automatische Migration des bisherigen v1-Formats
- transaktionaler Restore mit Rollback des In-Memory- und Dateizustands
- explizite Allowlist: nur Räume, Simulationsgeräte und Theme; keine Hue-Geräte, Credentials oder Tokens

## Automation Engine v1

- lokales Modell mit Geräte-Trigger, optionalen Bedingungen und Geräteaktionen
- typsichere Operatoren `equals`, `notEquals`, `above` und `below`
- drei einfache Vorlagen: Sensor schaltet Licht, Temperatur steuert Thermostat, Gerät ausschalten
- Aktivieren, Pausieren und Löschen über API und Clear-UI
- Aktionen laufen durch denselben Adapter- und Capability-Layer wie manuelle Befehle
- letzter Lauf und strukturierter Aktionsfehler bleiben sichtbar und persistent
- Schutz vor rekursiver Ausführung derselben Automation

## Robuste lokale Persistenz

- atomare Schreibvorgänge mit eindeutiger temporärer Datei und Rename
- `fsync` für Datei und – soweit vom Dateisystem unterstützt – Datenverzeichnis
- letzte gültige Version als `.bak`-Recovery-Datei
- automatische Wiederherstellung bei beschädigtem JSON
- strukturierte Diagnosen `STORAGE_RECOVERED`, `STORAGE_READ_FAILED` und `STORAGE_WRITE_FAILED`
- fehlgeschlagene Schreibvorgänge räumen ihre temporären Dateien auf

## Automation Scheduler v1

- tägliche lokale Uhrzeit-Trigger im Format `HH:MM`
- idempotente Ausführung: eine Regel läuft höchstens einmal pro Minute
- Scheduler arbeitet ohne Internet und ohne Cloud-Zeitdienst
- Sonnenauf-/Sonnenuntergang als injizierbare lokale Provider-Abstraktion vorbereitet
- Sonnenereignisse bleiben ohne konfigurierten Standortprovider sicher inaktiv
- Offset von bis zu zwölf Stunden vor oder nach einem Sonnenereignis
- lokales Hausmodell mit Name, Breiten- und Längengrad
- Sonnenzeiten werden direkt auf SystemONE Pi berechnet; keine Standortdaten verlassen das Gerät

## Sicherheitsregel

```bash
npm start
```

startet im Simulationsmodus. Echte Hue-Kommunikation wird ausschließlich bewusst freigeschaltet:

```bash
HUE_MODE=real npm start
```

## Aus v0.3.1 übernommen

- Reconnect-Zustandsmaschine mit `idle`, `connected`, `backoff` und `reconnecting`
- exponentieller Retry-Backoff mit Jitter statt aggressiver Endlosschleifen
- manueller Reconnect-Endpunkt und sichtbarer Reconnect-Status
- deutlich erweiterte Diagnosematrix für Netzwerk, SSDP, Bridge, Auth, Geräte, Pairing, Backup und Speicher
- echter lokal erzeugter QR-Code für Admin-Pairing
- 5 Minuten gültiger Token plus 6-stelliger Bestätigungscode
- lokaler QR-Scan-Simulator, damit der Pairing-Flow ohne mobile App vollständig testbar ist
- geführter Setup-Assistent mit sechs Prüfschritten
- 10 hardwarefreie Selftests

## Bereits enthalten

- Hue-Simulation für Discovery, Pairing, Schalten und Dimmen
- simulierbare Fehler: `not-found`, `link-button`, `timeout`, `auth`, `offline`, `command`
- Geräteprofile Licht, Schalter/Steckdose, Sensor, Thermostat und Rollladen/Jalousie
- persistente Räume und Simulationsgeräte
- lokale Backup-/Restore-Grundlage ohne Secrets
- echte Hue-Integration weiterhin hinter `HUE_MODE=real`

## Start

```bash
cd mvp/systemone-pi
npm install
npm run check
npm test
npm start
```

Browser: `http://localhost:4170`

## Fehler simulieren

```bash
HUE_SIM_FAULT=not-found npm start
HUE_SIM_FAULT=link-button npm start
HUE_SIM_FAULT=timeout npm start
HUE_SIM_FAULT=auth npm start
HUE_SIM_FAULT=offline npm start
HUE_SIM_FAULT=command npm start
```

## API v0.4.0

- `GET /api/health`
- `GET /api/diagnostics`
- `GET /api/setup`
- `GET /api/state`
- `GET /api/profiles`
- `GET /api/rooms`
- `POST /api/rooms`
- `GET /api/devices`
- `POST /api/devices/simulate`
- `PATCH /api/devices/:id`
- `GET /api/integrations/hue/discover`
- `POST /api/integrations/hue/pair`
- `POST /api/integrations/hue/sync`
- `POST /api/integrations/hue/reconnect`
- `POST /api/onboarding/pair-admin/session`
- `POST /api/onboarding/pair-admin/complete`
- `GET /api/backup`
- `POST /api/backup/restore`
- `GET /api/automations`
- `GET /api/automations/templates`
- `POST /api/automations`
- `POST /api/automations/from-template`
- `PATCH /api/automations/:id`
- `DELETE /api/automations/:id`
- `GET /api/automations/scheduler`
- `GET /api/home`
- `PATCH /api/home`

## Aktuelle Core-Selftests

1. kein Zugriff auf eine echte Bridge im Simulationsmodus
2. Bridge nicht gefunden
3. Link-Button fehlt
4. Timeout
5. Auth-Fehler
6. Offline-Gerät
7. Befehlsfehler
8. Persistenz
9. Reconnect wechselt in Backoff
10. erfolgreicher Reconnect setzt Backoff zurück
11. Capability-Normalisierung
12. Abweisung profilfremder Capabilities
13. Migration alter Geräte
14. Redaktion interner Adapterdaten
15. Registry-Ereignisse
16. normalisierte Simulation
17. normalisierte Hue-Simulation
18. gültige Backup-v2-Prüfsumme
19. Erkennung manipulierter Backups
20. Migration von Backup v1
21. Ausschluss von Hue-Geräten und Secrets
22. typsichere Automationsvergleiche
23. Erzeugung aus Vorlage
24. Abweisung unpassender Geräteprofile
25. lokale Geräteaktion
26. deaktivierte Automation
27. diagnostizierbarer Aktionsfehler
28. letzte gültige Storage-Sicherung
29. Recovery beschädigter Zustandsdatei
30. Diagnose nicht behebbarer Lesefehler
31. Zeitvorlage
32. Abweisung ungültiger Uhrzeit
33. einmalige Ausführung pro Minute
34. Ignorieren nicht fälliger Zeit
35. Sonnenereignis mit lokalem Provider
36. sicher inaktives Sonnenereignis ohne Provider
37. Standortvalidierung
38. lokale Sonnenzeitberechnung

## Noch nicht produktionsreif

Vor Kundeneinsatz fehlen weiterhin TLS/Reverse-Proxy-Härtung, echtes Berechtigungsmodell, Geräteidentitäten/Zertifikate, signierte Updates, Rate-Limits, CSRF-/Session-Schutz, vollständige Backup-Migrationen und ein Security-Review. Der echte Hue-Hardwaretest bleibt bewusst für einen späteren Pilot zurückgestellt.

## Danach

- Backup Schema v2 mit SHA-256, Validierung, Migration und atomarem Restore
- Zeit-/Sonnenereignisse und erweitertes Bedingungsmodell ergänzen
- YouDo-Modul-Hooks ergänzen
- anschließend weitere SystemONE-Module in denselben Simulations-/Diagnoserahmen integrieren

PEET, Pipercat-Control-Plane, Fernzugriff, Pipercat-Push und Kameraaufzeichnung/-KI bleiben außerhalb dieses Pi-MVPs.
