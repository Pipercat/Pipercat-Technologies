# Ethernet- und WLAN-Ersteinrichtung local-first (Stand 22.08.2026)

> Erledigt den **Software-Anteil** der Notion-Aufgabe `S1V2-02-029 · Ethernet- und WLAN-Ersteinrichtung local-first finalisieren` — siehe „Bekannte Grenzen" für den Hardware-Anteil, der in dieser Sandbox nicht verifiziert werden kann.
> Quelle: „SystemONE-Pi-Netzwerkentscheidung" (Notion, Bereich 06). Implementierung: `apps/customer-backend/app/services/network_setup.py`, `infrastructure/docker-compose/docker-compose.yml`, `apps/customer-backend/Dockerfile`.

## Wichtiger Unterschied zu den bisherigen Hardware-Aufgaben

Diese Aufgabe braucht nicht nur reale Hardware (ein echter Linux-Host mit NetworkManager, echte Netzwerk-Interfaces) für den vollständigen Nachweis — sie brauchte zuerst eine **Architekturentscheidung**, die bei `S1V2-02-022`–`-025` (Zigbee/Matter/Shelly/Hue) nicht nötig war: `apps/customer-backend` läuft als gewöhnlicher Docker-Container (`docker-compose.yml`), der standardmäßig **keinerlei** Zugriff auf die Netzwerkkonfiguration des Host-Systems hat. Netzwerk-Interfaces/WLAN/Hotspot sind ausschließlich Sache von NetworkManager, das auf dem **Host** läuft, nicht im Container.

## Architekturentscheidung: schmalstmöglicher Zugriff, kein `privileged`/`network_mode: host`

Statt des Containers vollen Host-Netzwerkzugriff (`network_mode: host`) oder gar `privileged: true` zu geben (beides deutlich zu breite Berechtigungen für das, was tatsächlich gebraucht wird), bindet `docker-compose.yml` gezielt genau zwei Pfade ein:

- **`/var/run/dbus:/var/run/dbus`** — NetworkManagers Steuerungs-API ist ein D-Bus-Systemdienst, kein Netzwerk-Namespace-Konzept. `nmcli` im Container spricht über diesen Socket mit dem auf dem Host laufenden `NetworkManager`-Daemon.
- **`/etc/NetworkManager/system-connections:/etc/NetworkManager/system-connections`** — dorthin schreibt `network_setup.py` seine Verbindungsprofile (siehe unten), damit NetworkManager sie beim `connection up` findet.

`apps/customer-backend/Dockerfile` installiert zusätzlich das Debian-Paket `network-manager` (liefert `nmcli`) — ohne dieses Paket im Container-Image wäre der Befehl selbst nicht vorhanden, unabhängig von den Volume-Mounts.

## „WLAN-Secrets sicher behandeln": Schlüsseldatei statt Kommandozeilenargument

`nmcli device wifi connect <SSID> password <PASSWORD>` (die naheliegende Variante) würde das Passwort als Klartext-Argument in die Prozessliste (`ps aux`) jedes lokalen Prozesses schreiben. Stattdessen schreibt `NetworkSetupService` ein echtes NetworkManager-Verbindungsprofil (`.nmconnection`-Datei, `0600`-Rechte) und aktiviert es per `nmcli connection up <profil-id>` — das Passwort erscheint nie als Kommandozeilenargument.

**Format gegen den echten NetworkManager-Quellcode verifiziert** (nicht geraten): `gh api` gegen `NetworkManager/NetworkManager`s eigene Testfixture `src/core/settings/plugins/keyfile/tests/keyfiles/Test_New_Wireless_Group_Names` bestätigt exakt die verwendete Struktur (`[connection]`/`[wifi]`/`[wifi-security]`/`[ipv4]`, `key-mgmt=wpa-psk`, `psk=...`).

## Befehlssyntax ebenfalls verifiziert, nicht geraten

`gh api` gegen `NetworkManager/NetworkManager`s eigenen `nmcli`-Quellcode (`src/nmcli/devices.c`) bestätigt:

- `nmcli device wifi hotspot [ifname <ifname>] [con-name <name>] [ssid <SSID>] [band a|bg|6GHz] [channel <channel>] [password <password>]`
- `nmcli device wifi connect <(B)SSID> [password <password>] [ifname <ifname>] [name <name>] [hidden yes|no]`
- Hotspot stoppen: `nmcli connection down <name>` (laut `nmcli`s eigenem Hilfetext: „Use 'connection down' or 'device disconnect' to stop the hotspot.")
- `nmcli -t -f TYPE,STATE device status` — `-t`/`--terse` und `-f`/`--fields` sind reale, aktuelle globale `nmcli`-Optionen (bestätigt in `src/nmcli/nmcli.c`).

`NetworkSetupService` selbst nutzt aus denselben Sicherheitsgründen wie beim WLAN-Connect auch für den Hotspot ein geschriebenes Profil (`mode=ap`, `method=shared` — NetworkManagers Standardmodus für DHCP-Server/NAT bei Hotspots/Tethering) statt `nmcli device wifi hotspot ... password ...` direkt aufzurufen — auch das Hotspot-Passwort landet nie in der Kommandozeile.

## „Ethernet ist bevorzugter Standard, WLAN Fallback"

`current_connectivity()` prüft Ethernet **zuerst** — selbst wenn beide Interfaces zufällig verbunden wären, wird Ethernet gemeldet. `should_start_setup_hotspot()` liefert nur `True`, wenn **weder** eine kabelgebundene **noch** eine bereits verbundene WLAN-Verbindung existiert — der Hotspot ist ausdrücklich der letzte Ausweg, nie der Standardpfad.

## „Temporärer Setup-Hotspot ... zeitlich begrenzt und nach Abschluss deaktiviert"

`start_setup_hotspot()` plant unabhängig von einem expliziten Stopp immer einen automatischen `stop_setup_hotspot()`-Aufruf nach `hotspot_timeout_seconds` (Sicherheitsnetz — „zeitlich begrenzt"). Der Setup-/Kopplungsablauf ruft `stop_setup_hotspot()` zusätzlich explizit auf, sobald die Einrichtung tatsächlich abgeschlossen ist („nach Abschluss deaktiviert") — das storniert auch das noch ausstehende Timeout, kein doppelter/verspäteter Stopp-Versuch danach.

## „Setup darf ohne Internet funktionieren"

Jede Operation in diesem Modul ist lokale NetworkManager-Konfiguration über `nmcli`/D-Bus — nirgendwo ein ausgehender Netzwerkaufruf. Funktioniert identisch, unabhängig davon, ob die entstehende Verbindung tatsächlich das Internet erreicht.

## Tests

`apps/customer-backend/tests/test_network_setup.py` (18 Tests, gefakter `nmcli`-Runner — kein echtes NetworkManager/D-Bus/WLAN-Gerät nötig): Ethernet-Priorität, Hotspot nur bei tatsächlichem Bedarf, WLAN-Profil mit `0600`-Rechten und korrektem Inhalt, Passwort erscheint in keinem einzigen Kommandozeilenaufruf (weder WLAN-Connect noch Hotspot), Hotspot-Profil mit `mode=ap`/`method=shared`, automatischer Timeout-Stopp, expliziter Stopp storniert das ausstehende Timeout, Fehlerfälle (nmcli-Aufruf schlägt fehl) sauber behandelt.

Gesamt `apps/customer-backend`: **356/356 bestanden** (338 aus `S1V2-01-003`–`S1V2-02-028` + 18 neue). `python3 scripts/check-import-boundaries.py`: keine Verletzung. `python3 scripts/check-secrets.py`: kein Fund. `docker compose config`: erfolgreich validiert — bestätigt insbesondere, dass die beiden neuen Bind-Mounts (`/var/run/dbus`, `/etc/NetworkManager/system-connections`) korrekt konfiguriert sind und `customer-backend` **kein** `privileged`/`network_mode: host` bekommen hat.

## Architekturentscheidungen

- Schmalstmöglicher Container-Zugriff (D-Bus-Socket + Profil-Verzeichnis) statt `network_mode: host`/`privileged: true` — deckt sich mit diesem Repos durchgängigem Least-Privilege-Prinzip.
- Schlüsseldatei-Profile statt `nmcli ... password ...`-Kommandozeilenargumente — sowohl für WLAN-Connect als auch für den Setup-Hotspot, aus demselben Grund.
- Alle Fakten (Keyfile-Format, `nmcli`-Befehlssyntax) direkt gegen `NetworkManager/NetworkManager`s eigenen Quellcode verifiziert, nicht aus dem Gedächtnis geraten — dieselbe Disziplin wie bei `S1V2-02-022`/`-023`s HA-Fakten.

## Bekannte Grenzen

- **Hardware-/Host-Nachweis ausstehend**: Diese Sandbox ist macOS ohne NetworkManager, ohne echte Ethernet-/WLAN-Interfaces und ohne Root-Zugriff auf ein Linux-Netzwerk-Stack. Kein einziger `nmcli`-Aufruf in dieser Aufgabe wurde gegen einen echten NetworkManager-Daemon ausgeführt — alle Tests laufen gegen einen gefakten Befehlsrunner. Eine Person mit Zugriff auf einen echten Raspberry Pi (oder eine andere Debian/NetworkManager-Umgebung) muss vor „Done": Neuinstallation per LAN vollständig einrichten, WLAN-Fallback (inkl. Verbindungsprofil-Aktivierung) gegen ein echtes Netzwerk bestätigen, Setup-Hotspot tatsächlich starten/verbinden/stoppen (inkl. Zeitüberschreitung) und bestätigen, dass er nach Abschluss zuverlässig deaktiviert bleibt.
- Kein API-Endpunkt für `NetworkSetupService` — dieselbe „gebaut, aber unverdrahtet"-Konvention wie mehrere andere Services dieser Session; ein echter Erstkopplungs-/Onboarding-Flow (der diesen Service nutzen würde) existiert selbst noch nicht (siehe `docs/architecture/device-pairing.md`s „Bekannte Grenzen").
- Kein automatisiertes WLAN-Scanning/Netzwerkauswahl-UI — `connect_wifi()` nimmt SSID/Passwort entgegen, die der Aufrufer bereits kennt; eine „verfügbare Netzwerke auflisten"-Fähigkeit (`nmcli device wifi list`) wäre eine kleine, separate Erweiterung, hier nicht vorgezogen, da ohne echte WLAN-Hardware nicht sinnvoll verifizierbar.
