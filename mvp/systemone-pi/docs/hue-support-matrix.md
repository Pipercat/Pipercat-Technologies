# Philips-Hue-Supportmatrix · SystemONE Pi MVP

Stand: 13.08.2026 · Bearbeitet von: Pipercat Technologies

## Freigabestatus

| Komponente | Modell/Firmware | Geprüfte Funktionen | Ergebnis | SystemONE-Klasse |
|---|---|---|---|---|
| Hue-Adapter, Simulation | SystemONE Testadapter v0.4.0 | Discovery, Pairing, Laden, Schalten, Dimmen, Offline, Timeout, Paketverlust, Auth, Backoff, Reconnect | 104/104 Core-Tests bestanden | Experimental |
| Philips Hue Bridge | Noch nicht am Zielgerät erfasst | Keine physische Prüfung | Nicht getestet | Experimental |
| Philips Hue Lampe(n) | Noch nicht am Zielgerät erfasst | Keine physische Prüfung | Nicht getestet | Experimental |

Kein reales Hue-Modell ist derzeit **SystemONE Certified**. Eine Freigabe erfolgt ausschließlich pro protokollierter Kombination aus Bridge-Modell, Bridge-Firmware, Lampenmodell und Lampenfirmware.

## Bekannte Einschränkungen

- Erforderlich sind eine physische Hue Bridge, Zugriff auf deren Link-Taste und dasselbe private Ziel-LAN wie der SystemONE Pi.
- Es wird ausschließlich die lokale Hue-Bridge-API verwendet; Hue-Cloud und Fernzugriff gehören nicht zum MVP.
- Discovery akzeptiert nur private IPv4-Ziele und verifiziert eine Hue-/Signify-Gerätebeschreibung.
- Ein Wechsel der Bridge-Identität verwirft die alte lokale Anmeldung, statt Credentials wiederzuverwenden.
- Bis zum physischen Nachweis bleiben Hue-Geräte und die Integration als **Experimental** gekennzeichnet.

## Wiederholbares Hardwareprotokoll

1. Aktuellen Simulationslauf mit `npm run verify` dokumentieren.
2. Bridge-Modell, Seriennummer (im vertraulichen lokalen Prüfbericht), Bridge-Firmware und Ziel-LAN erfassen.
3. System ausschließlich für diesen Test mit `HUE_MODE=real HUE_BRIDGE_IP=<private-ip> npm start` starten.
4. Discovery ausführen und Bridge-ID sowie private IP bestätigen.
5. Link-Taste drücken, Pairing einmalig abschließen und lokalen Credential-Neustart prüfen.
6. Für jedes Lampenmodell Modell/Firmware erfassen; Laden, Ein/Aus, 1/50/100 % Dimmen und Erreichbarkeit testen.
7. Timeout, kurzzeitigen Paketverlust, stromloses Leuchtmittel und manuellen Reconnect kontrolliert prüfen.
8. Erholung ohne Serverneustart sowie exponentiellen Backoff belegen.
9. Diagnosebericht auf Secret-Redaktion prüfen; keine Credentials oder Benutzernamen veröffentlichen.
10. Server wieder ohne `HUE_MODE=real` starten und bestätigen, dass Simulation der Standard ist.

## Vorlage je Hardwarekombination

- Prüfdatum / Bearbeiter:
- Bridge-Modell / Firmware:
- Lampenmodell / Firmware:
- Discovery / Link-Taste / Neustart-Persistenz:
- Laden / Schalten / Dimmen:
- Offline / Timeout / Paketverlust / Auth / Reconnect:
- Bekannte Einschränkungen:
- Ergebnis: Bestanden / Teilweise / Nicht bestanden
- Freigabeklasse: Experimental / Compatible / Certified
- Nachweis (Commit, Diagnosebericht, Foto oder lokaler Testlauf):
