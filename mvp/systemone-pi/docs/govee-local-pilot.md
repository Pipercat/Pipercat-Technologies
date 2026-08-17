# Lokaler Govee-Pilot

SystemONE beginnt Govee ausschließlich simulationsbasiert. Der Adapter implementiert Discovery, Pairing, Geräteliste und normalisierte Licht-Capabilities für Power, Helligkeit, Farbe und Farbtemperatur. Timeout, Offline-Gerät und abgewiesener Befehl besitzen strukturierte Fehler.

Die Pilot-Allowlist enthält `H6008` und `H605C`. Beide Modelle sind im offiziellen Govee-Produktkatalog beziehungsweise in offiziellen Capability-Beispielen dokumentiert; Govee dokumentiert außerdem, dass lokale Steuerung nur bei sichtbarem und aktiviertem „LAN Control“-Schalter verfügbar ist. Deshalb bleiben beide Einträge `experimental` und `hardwareReleased: false`, bis Modell, Firmware und LAN-Schalter praktisch geprüft wurden.

Quellen:

- https://developer.govee.com/docs/support-product-model
- https://developer.govee.com/reference/control-you-devices
- https://desktop.govee.com/user-manual/faq

Ausgeschlossen sind alle Modelle außerhalb der Allowlist, Geräte ohne sichtbare LAN-Control-Option und sämtliche Funktionen, die Govee OpenAPI, API-Key oder ein Cloudkonto benötigen. `GOVEE_MODE=real` hebt diese Grenze nicht auf: reale Discovery wird bis zum Hardware-Nachweis explizit mit `GOVEE_HARDWARE_NOT_RELEASED` abgewiesen.
