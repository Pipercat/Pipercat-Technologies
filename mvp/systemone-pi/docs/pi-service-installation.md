# SystemONE Pi – systemd-Installation

Status: versionierte Installationsgrundlage; physische Abnahme auf dem Ziel-Pi bleibt offen.

## Voraussetzungen

- Unterstütztes Raspberry-Pi-OS mit systemd und Node.js 20 oder neuer.
- Anwendung vollständig unter `/opt/systemone-pi`; dieses Verzeichnis bleibt im Betrieb schreibgeschützt.
- Keine Portweiterleitung und keine öffentliche IP. Zugriff nur aus dem privaten lokalen Netz.
- Release-/Commit-ID und Prüfsumme des installierten Artefakts vor der Aktivierung dokumentieren.

## Installation

```bash
sudo install -d -o root -g root -m 0755 /opt/systemone-pi
sudo install -d -o root -g root -m 0700 /etc/systemone-pi
sudo install -o root -g root -m 0644 deploy/systemd/systemone-pi.service /etc/systemd/system/systemone-pi.service
sudo install -o root -g root -m 0600 deploy/systemd/systemone.env.example /etc/systemone-pi/systemone.env
sudo systemctl daemon-reload
sudo systemctl enable --now systemone-pi.service
```

Der eigentliche, zuvor mit `npm ci --omit=dev` und `npm run verify` geprüfte Release-Inhalt wird atomar nach `/opt/systemone-pi` übertragen. Abhängigkeiten werden nicht als root zur Laufzeit nachinstalliert.

## Prüfung

```bash
systemctl status systemone-pi.service
curl --fail --silent http://127.0.0.1:4171/api/v1/health
sudo systemctl restart systemone-pi.service
journalctl -u systemone-pi.service --since today
```

Nach Restart müssen Räume, Geräte und Automationen erhalten sein. Das Log darf keine Secrets, Tokens oder Recovery-Codes enthalten. `systemctl stop` muss innerhalb `TimeoutStopSec=15s` mit `SystemONE beendet: SIGTERM` abschließen und Port 4171 freigeben.

## Sicherheitsmodell

Die Unit nutzt einen dynamischen, nicht anmeldbaren Benutzer, eine private StateDirectory mit Modus 0700, UMask 0077, leere Linux-Capability-Sets, schreibgeschütztes System/Home und begrenzte Netzwerk-Adressfamilien. Die Environment-Datei gehört root und hat Modus 0600. Kamera, Pi-hole, YouDo und reale Hue-Hardware bleiben standardmäßig deaktiviert.

Der Start ist **fail-closed**: ungültiger Port, unbekannte Modi, andere Boolean-Werte als exakt `true`/`false`, nur ein gesetzter TLS-Pfad, fehlende TLS-/Update-Schlüsseldateien, öffentliche Hue-IP oder realer Govee-Modus stoppen den Prozess mit verständlichem Fehler. Insbesondere fällt eine unvollständige TLS-Konfiguration niemals still auf HTTP zurück.

USB-/NAS-Backupziele benötigen eine separat geplante systemd-Mount-Unit und einen ausdrücklich freigegebenen Pfad in `SYSTEMONE_EXPORT_ROOTS`. Keine Lockerung von `ProtectSystem`, Capabilities oder Dateirechten ohne dokumentierten Risikonachweis.

## Rückbau

```bash
sudo systemctl disable --now systemone-pi.service
sudo rm /etc/systemd/system/systemone-pi.service
sudo systemctl daemon-reload
```

Die Daten unter `/var/lib/systemone-pi` und Secrets unter `/etc/systemone-pi` werden erst nach geprüftem Backup und ausdrücklicher Rückbaubestätigung entfernt. Diese Anleitung autorisiert keine automatische Datenlöschung.
