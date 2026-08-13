# SystemONE Pi – systemd-Installation

Status: versionierte Installationsgrundlage; physische Abnahme auf dem Ziel-Pi bleibt offen.

## Voraussetzungen

- Unterstütztes Raspberry-Pi-OS mit systemd und Node.js 20 oder neuer.
- Anwendung in zwei unveränderlichen Slots unter `/opt/systemone-pi/slots/A` und `/opt/systemone-pi/slots/B`; `/opt/systemone-pi/current` zeigt ausschließlich auf den aktiven Slot.
- Keine Portweiterleitung und keine öffentliche IP. Zugriff nur aus dem privaten lokalen Netz.
- Release-/Commit-ID und Prüfsumme des installierten Artefakts vor der Aktivierung dokumentieren.

## Installation

```bash
sudo install -d -o root -g root -m 0755 /opt/systemone-pi/slots/A /opt/systemone-pi/slots/B
sudo install -d -o root -g root -m 0700 /etc/systemone-pi
sudo install -o root -g root -m 0644 deploy/systemd/systemone-pi.service /etc/systemd/system/systemone-pi.service
sudo install -o root -g root -m 0600 deploy/systemd/systemone.env.example /etc/systemone-pi/systemone.env
sudo ln -sfn /opt/systemone-pi/slots/A /opt/systemone-pi/current.next
sudo mv -Tf /opt/systemone-pi/current.next /opt/systemone-pi/current
sudo systemctl daemon-reload
sudo systemctl enable --now systemone-pi.service
```

Der eigentliche, zuvor mit `npm ci --omit=dev` und `npm run verify` geprüfte Release-Inhalt wird vollständig in Slot A installiert, bevor der `current`-Symlink atomar per `mv -T` aktiviert wird. Abhängigkeiten werden nicht als root zur Laufzeit nachinstalliert. Slot B bleibt bis zum ersten signierten, lokal freigegebenen Update leer.

Ein späteres Update schreibt ausschließlich den inaktiven Slot. Erst nach Paket-/Hashprüfung und lokaler Adminfreigabe darf ein temporärer `current.next`-Symlink erzeugt und atomar auf `current` verschoben werden. Der vorherige Symlinkwert wird als bestätigter Rollbackslot protokolliert. Direkte Änderungen im aktiven Slot oder ein `current`-Ziel außerhalb `slots/A|B` sind unzulässig.

## Prüfung

```bash
systemctl status systemone-pi.service
curl --fail --silent http://127.0.0.1:4171/api/v1/health
sudo systemctl restart systemone-pi.service
journalctl -u systemone-pi.service --since today
```

Nach Restart müssen Räume, Geräte und Automationen erhalten sein. Das Log darf keine Secrets, Tokens oder Recovery-Codes enthalten. `systemctl stop` muss innerhalb `TimeoutStopSec=15s` mit `SystemONE beendet: SIGTERM` abschließen und Port 4171 freigeben.

Zusätzlich müssen `readlink -f /opt/systemone-pi/current`, gespeicherter `activeSlot` und gestartete Versionsnummer denselben Slot belegen. Bei fehlgeschlagenem Candidate-Healthcheck wird der Symlink atomar auf den zuvor bestätigten Slot zurückgesetzt und der Dienst neu gestartet. Die getrennte Datenpartition `/var/lib/systemone-pi` wird dabei weder verschoben noch ersetzt.

## Sicherheitsmodell

Die Unit nutzt einen dynamischen, nicht anmeldbaren Benutzer, eine private StateDirectory mit Modus 0700, UMask 0077, leere Linux-Capability-Sets, schreibgeschütztes System/Home und begrenzte Netzwerk-Adressfamilien. Die Environment-Datei gehört root und hat Modus 0600. Kamera, Pi-hole, YouDo und reale Hue-Hardware bleiben standardmäßig deaktiviert.

Der Start ist **fail-closed**: ungültiger Port, unbekannte Modi, andere Boolean-Werte als exakt `true`/`false`, nur ein gesetzter TLS-Pfad, fehlende TLS-/Update-Schlüsseldateien, öffentliche Hue-IP oder realer Govee-Modus stoppen den Prozess mit verständlichem Fehler. Insbesondere fällt eine unvollständige TLS-Konfiguration niemals still auf HTTP zurück. `ExecStartPre` führt denselben Check vor der Initialisierung aus. Konfigurationsfehler enden mit standardisiertem `EX_CONFIG`-Exitcode 78; `RestartPreventExitStatus=78` verhindert eine systemd-Neustartschleife. Nach der Korrektur wird der Dienst bewusst mit `systemctl restart systemone-pi` erneut gestartet.

USB-/NAS-Backupziele benötigen eine separat geplante systemd-Mount-Unit und einen ausdrücklich freigegebenen Pfad in `SYSTEMONE_EXPORT_ROOTS`. Keine Lockerung von `ProtectSystem`, Capabilities oder Dateirechten ohne dokumentierten Risikonachweis.

## Rückbau

```bash
sudo systemctl disable --now systemone-pi.service
sudo rm /etc/systemd/system/systemone-pi.service
sudo systemctl daemon-reload
```

Die Daten unter `/var/lib/systemone-pi` und Secrets unter `/etc/systemone-pi` werden erst nach geprüftem Backup und ausdrücklicher Rückbaubestätigung entfernt. Diese Anleitung autorisiert keine automatische Datenlöschung.
