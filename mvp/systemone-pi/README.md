# SystemONE Pi MVP v0.3

v0.3 ist eine hardware-sichere Entwicklungs- und Diagnoseversion. Sie ist dafür gedacht, SystemONE theoretisch und reproduzierbar zu testen, **ohne das produktive Philips-Hue-System anzufassen**.

## Sicherheitsregel

`npm start` läuft standardmäßig im **Simulationsmodus**. In diesem Modus werden weder SSDP-Anfragen an das Heimnetz gesendet noch Hue-HTTP-Endpunkte aufgerufen.

Echte Hue-Kommunikation ist nur nach bewusster Freigabe möglich:

```bash
HUE_MODE=real npm start
```

Damit kann die private Installation bis zu einem späteren Hardware-Pilot unverändert bleiben.

## v0.3 enthält

- Diagnose-Engine mit strukturierten Fehlercodes, Schweregrad und Handlungsempfehlung
- `/api/health` und `/api/diagnostics`
- Fehlerprotokoll ohne Ausgabe von Tokens/Credentials
- Hue-Simulation mit Bridge-Fund, Pairing, Lampen, Schalten und Dimmen
- künstliche Fehlerfälle: Bridge nicht gefunden, Link-Button fehlt, Timeout, Auth-Fehler, Gerät offline und Befehlsfehler
- fünf Geräteprofile: Licht, Steckdose/Schalter, Sensor, Thermostat und Rollladen/Jalousie
- simuliertes „Gerät hinzufügen“ über die Oberfläche
- persistente Räume und simulierte Geräte
- zeitlich begrenzte Admin-Pairing-Sitzung mit Token, 6-stelligem Code und vorbereitetem `systemone://pair`-Payload für späteres QR-Pairing
- lokale Backup-/Restore-API für Räume und Simulationsgeräte; Secrets werden nicht exportiert
- echte Hue-Integration bleibt hinter `HUE_MODE=real` vorhanden

## Start und Prüfung

```bash
cd mvp/systemone-pi
npm run check
npm test
npm start
```

Browser:

```text
http://localhost:4170
```

## Fehler simulieren

```bash
HUE_SIM_FAULT=not-found npm start
HUE_SIM_FAULT=link-button npm start
HUE_SIM_FAULT=timeout npm start
HUE_SIM_FAULT=auth npm start
HUE_SIM_FAULT=offline npm start
HUE_SIM_FAULT=command npm start
```

Diese Varianten bleiben im Simulationsmodus und sprechen keine echte Hue Bridge an.

## Automatischer Selftest

`npm test` prüft derzeit acht hardwarefreie Szenarien:

1. Simulationsmodus verwendet nur `127.0.0.1`
2. Bridge nicht gefunden
3. Link-Button-Fehler
4. Timeout
5. ungültige Hue-Authentifizierung
6. Offline-Lampe
7. fehlgeschlagener Steuerbefehl
8. lokale Persistenz

## API v0.3

- `GET /api/health`
- `GET /api/diagnostics`
- `GET /api/system`
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
- `POST /api/onboarding/pair-admin/session`
- `POST /api/onboarding/pair-admin/complete`
- `GET /api/backup`
- `POST /api/backup/restore`

## Noch nicht produktionsreif

Kein Kundeneinsatz: TLS/Reverse-Proxy-Härtung, echtes Berechtigungsmodell, Geräteidentitäten/Zertifikate, signierte Updates, vollständige Backup-Validierung, Rate-Limits, CSRF-/Session-Schutz und Security-Review fehlen noch. Ein echter Hue-Hardwaretest wird bewusst erst später gemacht.

## Nächste Entwicklungsstufe

- Diagnosematrix weiter ausbauen und Reconnect-Zustandsmaschine ergänzen
- QR-Darstellung für das vorbereitete Admin-Pairing
- Geräteprofil-Validierung und Capability-Layer ausbauen
- geführten Einrichtungsassistenten vervollständigen
- Backup/Restore mit Prüfsumme und Versionsmigration härten
- danach Automationsvorlagen und YouDo-Modul-Hooks

PEET, Pipercat-Control-Plane, Fernzugriff, Pipercat-Push und Kameraaufzeichnung/-KI bleiben außerhalb dieses Pi-MVPs.
