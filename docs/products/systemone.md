# SystemONE

SystemONE ist die zentrale Plattform von Pipercat Technologies. Sie soll Kundensysteme zusammenstellen, provisionieren, registrieren, überwachen, aktualisieren, sichern und fernwarten.

## Zielprozess

Kunde anlegen → Hardware wählen → Module wählen → Konfiguration prüfen → Installation erzeugen → Gerät registrieren → Kunde bestätigt Installation oder Update → Monitoring aktivieren.

## Grundprinzipien

- lokale Kundendaten als Standard
- keine zentrale Speicherung von NAS-, Kamera- oder Smart-Home-Inhalten
- nur notwendige Verwaltungsmetadaten zentral speichern
- Updates nur nach Kundenfreigabe
- Fernwartung transparent und protokolliert
- Backup und Rollback vor riskanten Änderungen
- Geräteidentitäten und verschlüsselte Verbindungen

## Hardwareklassen

### SystemONE Pi
Für Home Assistant, Pi-hole, VPN, Monitoring und kleinere Dienste.

### SystemONE Mini
Für mehrere Container, NAS, Jellyfin, Backups und kleinere lokale KI-Anwendungen.

### SystemONE Server
Für VMs, große Speicherlösungen, Kameras, lokale KI und zentrale Backups.

### SystemONE Rack
Für projektierte Business- und Premium-Infrastruktur mit Compute, Storage, Netzwerk, USV und optionaler GPU-Hardware.

## Modulbaukasten

Home, Network, Storage, Backup, Media, Security, Monitoring, Remote, AI, Automation, Identity, Updates, Marketplace und Provisioning.

## MVP

1. registrierte Geräte
2. Kunden- und Standortzuordnung
3. Modulprofile
4. signierte Updatepakete
5. Kundenfreigabe für Updates
6. Status und Audit-Logs
7. sicherer Supportzugang
8. Backup vor Updates
9. Rollback

## Offene Entscheidungen

- genaue Virtualisierungs- und Containerstrategie
- Agent versus agentenlose Verwaltung
- zentrale Steuerung ohne zentrale Kundendatenspeicherung
- Geräteidentität und Zertifikatsverwaltung
- Update-Signierung und Releasekanäle
- bevorzugte Fernwartungstechnik
