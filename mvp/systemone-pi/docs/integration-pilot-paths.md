# Getrennte Pilotpfade: Matter, Shelly und Zigbee

Die verbindliche Reihenfolge lautet **Hue → Govee → Matter → Shelly → Zigbee**. Kein späterer Pfad wird vorgezogen und keine Integration wird ohne vollständig ausgefüllte Hardwarematrix als unterstützt markiert. Herstellerprotokolle und Rohdaten enden jeweils im eigenen Adapter; der Core sieht ausschließlich normalisierte Capabilities.

## Matter

- Matrix: Raspberry-Pi-Controller, Thread-/Ethernet-Pfad, Gerätemodell, Firmware, Commissioning, Neustart, Recovery.
- Sicherheit: Codes und Fabric-Schlüssel nur lokal; IPv6/mDNS strikt lokal; kein Herstellercloud-Zwang.
- Abbruch: nicht reproduzierbares Commissioning, Cloudpflicht oder unklare Fabric-Recovery.

## Shelly

- Matrix: Gen1 und Gen2 getrennt, Modell, Firmware, HTTP/RPC, Auth, Offline/Timeout, Neustart.
- Sicherheit: nur private LAN-IPs; Credentials geschützt; Schreiboperationen capability-validiert.
- Abbruch: uneindeutige Modell-/Firmwareerkennung, Cloudpflicht oder nicht begrenzbarer Schreibzugriff.

## Zigbee

- Matrix: exakt definierter Koordinator, dessen Firmware, Gerätehersteller/-modell, Pairing, Rejoin, Stromausfall und Reichweite.
- Sicherheit: Netzwerkschlüssel lokal; Koordinator exklusiv; Permit-Join zeitlich begrenzt und sichtbar.
- Abbruch: nicht reproduzierbarer Koordinator, dauerhaft offenes Join oder Herstellerdaten außerhalb des Adapters.

`lib/integration-pilots.js` stellt die maschinenlesbare Matrix bereit. Alle Zeilen beginnen mit `not-tested` und `supported=false`; eine spätere Freigabe verlangt praktische Evidenz und dokumentierte Fehlerfälle.
