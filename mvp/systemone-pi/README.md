# SystemONE Pi MVP v0.2

Zweite lauffähige lokale Version des SystemONE-Pi-Vertical-Slice aus dem Notion-MVP. v0.2 ersetzt den reinen Hue-Demo-Fluss durch einen echten lokalen Adapter und ergänzt persistente Räume/Gerätenamen sowie Live-State-Synchronisierung.

## Enthalten

- lokale Node.js-API ohne externe npm-Dependencies
- Clear-Theme SystemONE Dashboard
- lokales Admin-Pairing als MVP-Zustand
- Philips-Hue-Discovery per SSDP im lokalen Netzwerk
- optional feste Bridge-IP über `HUE_BRIDGE_IP`
- physischer Hue-Link-Button-Pairing-Flow
- lokale Hue-Credentials getrennt vom normalen Zustand
- echte Hue-Lampen laden, schalten und dimmen
- automatische Zustands-Synchronisierung alle 3 Sekunden
- Offline-/Syncfehler in der Oberfläche
- lokale Gerätenamen und Raumzuweisungen
- neue Räume direkt in der Oberfläche anlegen
- persistente lokale Konfiguration unter `data/`
- Demo-Modus weiterhin über `HUE_MODE=mock`

## Local-first & Datenspeicherung

SystemONE benötigt für diesen MVP keine Pipercat-Cloud. Laufzeitdaten werden standardmäßig unter `mvp/systemone-pi/data/` gespeichert und durch `.gitignore` nicht versioniert.

- `data/state.json` – System-, Raum- und Gerätekonfiguration
- `data/secrets.json` – lokale Hue-Bridge-/Credential-Daten

Die Dateien werden vom Prozess mit restriktiven Dateirechten angelegt. Der Speicherort kann mit `SYSTEMONE_DATA_DIR` geändert werden.

## Start

Voraussetzung: Node.js 20 oder neuer.

```bash
cd mvp/systemone-pi
npm run check
npm start
```

Danach im Browser öffnen:

```text
http://localhost:4170
```

Im LAN ist der Dienst auf `0.0.0.0:4170` erreichbar.

## Echte Philips Hue Bridge koppeln

1. SystemONE Pi und Hue Bridge müssen im selben lokalen Netzwerk erreichbar sein.
2. `npm start` ausführen.
3. In SystemONE auf **Hue suchen** klicken.
4. Wird die Bridge nicht automatisch gefunden, kann ihre lokale IPv4-Adresse gesetzt werden:

```bash
HUE_BRIDGE_IP=192.168.178.42 npm start
```

5. Nach dem Fund die physische Link-Taste auf der Hue Bridge drücken.
6. In SystemONE erneut auf **Link-Taste drücken & koppeln** klicken.
7. Die Lampen werden geladen und anschließend laufend synchronisiert.

Es werden nur private/lokale IPv4-Adressen als Bridge-Ziel akzeptiert.

## Demo ohne Hue-Hardware

```bash
HUE_MODE=mock npm start
```

Damit wird eine lokale Demo-Bridge mit zwei Lampen verwendet. Auch Namen und Raumzuweisungen werden persistent gespeichert.

## API v0.2

- `GET /api/health`
- `GET /api/system`
- `GET /api/state`
- `GET /api/state?sync=1`
- `GET /api/rooms`
- `POST /api/rooms`
- `GET /api/devices`
- `GET /api/integrations/hue/discover`
- `POST /api/integrations/hue/pair`
- `POST /api/integrations/hue/sync`
- `POST /api/onboarding/pair-admin`
- `PATCH /api/devices/:id`

Antwortformat:

```json
{ "success": true, "data": {}, "error": null }
```

## MVP-Stand

### v0.1 – abgeschlossen
- lokales Dashboard
- Mock-Hue-Flow
- Schalten/Dimmen
- Offline-Darstellung

### v0.2 – umgesetzt
- echte lokale Hue-Discovery
- Link-Button-Kopplung
- echte Lichtliste und State-Synchronisierung
- persistente Räume/Gerätenamen
- lokale Credential-Ablage

### v0.3 – als Nächstes
- QR-basiertes Admin-Pairing
- Geräteprofile für Schalter, Sensor, Thermostat und Rollladen
- geführtes „Gerät hinzufügen“
- robustere Netzwerk-/Reconnect-Logik
- erste lokale Backup-/Restore-Funktion

### später
- Clear, Midnight, Compact und Living
- Automationsvorlagen
- YouDo-Modulschalter
- Flutter-App

## Noch nicht produktionsreif

Der MVP ist bewusst ein Entwicklungsstand. Vor Kundeneinsatz fehlen unter anderem TLS/Reverse-Proxy-Härtung, echte Geräteidentitäten/Zertifikate, abgesichertes Admin-Pairing, Berechtigungsmodell, Update-Signaturen, Backup/Restore-Tests und ein vollständiges Security-Review.

## Nicht Teil dieses Pi-MVP

PEET/Sprachsteuerung, Pipercat-Control-Plane, Pipercat-Push, Kameraaufzeichnung/-KI, Import bestehender Home-Assistant-Systeme und garantierter CGNAT-Fernzugriff.
