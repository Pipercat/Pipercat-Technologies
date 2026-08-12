# SystemONE Pi MVP v0.3.1

Hardware-sichere Entwicklungs- und Diagnoseversion von SystemONE. Standardmäßig läuft alles in Simulation; das produktive Philips-Hue-System wird nicht angesprochen.

## Sicherheitsregel

```bash
npm start
```

startet im Simulationsmodus. Echte Hue-Kommunikation wird ausschließlich bewusst freigeschaltet:

```bash
HUE_MODE=real npm start
```

## Neu in v0.3.1

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

## API v0.3.1

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

## Aktuelle Selftests

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

## Noch nicht produktionsreif

Vor Kundeneinsatz fehlen weiterhin TLS/Reverse-Proxy-Härtung, echtes Berechtigungsmodell, Geräteidentitäten/Zertifikate, signierte Updates, Rate-Limits, CSRF-/Session-Schutz, vollständige Backup-Migrationen und ein Security-Review. Der echte Hue-Hardwaretest bleibt bewusst für einen späteren Pilot zurückgestellt.

## Danach

- Backup mit Prüfsumme und Versionsmigration härten
- Capability-Layer und Validierung pro Geräteprofil ausbauen
- Automationsvorlagen implementieren
- YouDo-Modul-Hooks ergänzen
- anschließend weitere SystemONE-Module in denselben Simulations-/Diagnoserahmen integrieren

PEET, Pipercat-Control-Plane, Fernzugriff, Pipercat-Push und Kameraaufzeichnung/-KI bleiben außerhalb dieses Pi-MVPs.
