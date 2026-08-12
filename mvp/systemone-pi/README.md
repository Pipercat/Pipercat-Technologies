# SystemONE Pi MVP v0.1

Erste lauffähige lokale Version des SystemONE-Pi-Vertical-Slice aus dem Notion-MVP.

## Enthalten

- lokale Node.js-API ohne externe Dependencies
- Clear-Theme SystemONE Dashboard
- lokales Admin-Pairing als MVP-Zustand
- simulierte Philips-Hue-Bridge-Erkennung und -Kopplung
- Räume und Hue-Lampen
- Schalten und Dimmen
- Live-Aktualisierung der Zustände über die API
- verständlicher Offline-Zustand einer Beispiel-Lampe
- Local-first-Hinweise in der UI

## Noch bewusst simuliert

Die Hue-Integration ist in v0.1 ein lokaler Adapter mit Demo-Daten. Es werden noch keine echten Hue-, Home-Assistant- oder Matter-Endpunkte angesprochen. Damit ist der komplette Bedienfluss testbar, bevor Hardwarezugriff, Credentials und Discovery produktiv umgesetzt werden.

## Start

Voraussetzung: Node.js 20 oder neuer.

```bash
cd mvp/systemone-pi
npm start
```

Danach im Browser öffnen:

```text
http://localhost:4170
```

Im LAN ist der Dienst auf `0.0.0.0:4170` erreichbar. Für einen produktiven Pi müssen Firewall, TLS/Reverse-Proxy und Pairing-Sicherheit separat gehärtet werden.

## API v0.1

- `GET /api/health`
- `GET /api/system`
- `GET /api/state`
- `GET /api/rooms`
- `GET /api/devices`
- `GET /api/integrations/hue/discover`
- `POST /api/onboarding/pair-admin`
- `POST /api/integrations/hue/pair`
- `PATCH /api/devices/:id`

Antwortformat:

```json
{ "success": true, "data": {}, "error": null }
```

## Nächste Versionen

### v0.2 – echte Hue Bridge
- mDNS/SSDP bzw. Hue Discovery
- physischer Link-Button-Flow
- sichere lokale Credential-Ablage
- echte Lichtliste und State-Synchronisierung

### v0.3 – Gerätemodell & Räume
- Umbenennen und Raumzuweisung in der UI
- Geräteprofile Licht, Schalter, Sensor, Thermostat, Rollladen
- persistente lokale Konfiguration

### v0.4 – Onboarding & Themes
- QR-basiertes Admin-Pairing
- Clear, Midnight, Compact und Living
- geführtes Gerät-hinzufügen

### v0.5 – Automationen & YouDo-Hooks
- erste einfache Automationsvorlagen
- Modulschalter für YouDo Kalender und Aufgaben
- lokale Backup-/Restore-Grundlage

## Nicht Teil dieses Pi-MVP

PEET/Sprachsteuerung, Pipercat-Control-Plane, Pipercat-Push, Kameraaufzeichnung/-KI, Import bestehender Home-Assistant-Systeme und garantierter CGNAT-Fernzugriff.
